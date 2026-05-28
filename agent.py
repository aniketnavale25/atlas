"""
agent.py
--------
The heart of ATLAS: the agent loop, built on OpenAI's chat completions
+ tool calling API.

There are two loops here, nested:

  OUTER (revision loop):
    planner builds plan -> evaluator checks -> if fail, revise -> repeat

  INNER (tool loop):
    LLM thinks -> requests tool calls -> we run them -> feed results back ->
    repeat until LLM stops asking for tools

OpenAI tool-calling specifics (different from Anthropic):
  - System prompt goes in the messages list as {"role": "system", ...}
  - Tool calls appear in message.tool_calls (a list, possibly parallel)
  - Tool results are appended as {"role": "tool", "tool_call_id": ..., "content": ...}
  - Finish reason "tool_calls" means more work; "stop" means done
  - The assistant message must be appended back to history with its tool_calls

This is the core pattern. Once you internalize it, every framework
(LangChain, LangGraph, Assistants API) is just sugar on top.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Iterator, Any

from openai import OpenAI

from config import CONFIG
from prompts import planner_system_prompt, EVALUATOR_SYSTEM_PROMPT
from tools import TOOL_SCHEMAS, run_tool


# ---------------------------------------------------------------------------
# EVENT TYPES - streamed back to the UI so the user sees the agent thinking
# ---------------------------------------------------------------------------

@dataclass
class AgentEvent:
    """A single observable step in the agent's reasoning."""
    kind: str            # 'thought' | 'tool_call' | 'tool_result' | 'plan' | 'evaluation' | 'revision' | 'done'
    content: Any
    iteration: int = 0
    revision: int = 0


# ---------------------------------------------------------------------------
# AGENT
# ---------------------------------------------------------------------------

class AtlasAgent:
    """
    Multi-turn agent. Each plan_trip() starts a fresh conversation;
    refine_plan() continues an existing one.

    The conversation history is OWNED BY THE CALLER. We yield it via the
    'session' event at the end of each run so the UI (or any other host)
    can persist it and pass it back into refine_plan() on the next turn.
    This keeps the agent itself stateless while supporting multi-turn flow.
    """

    def __init__(self) -> None:
        CONFIG.require_openai()
        self.client = OpenAI(api_key=CONFIG.openai_api_key)

    # -----------------------------------------------------------------
    # Public API: initial trip planning (first turn)
    # -----------------------------------------------------------------
    def plan_trip(self, brief: str) -> Iterator[AgentEvent]:
        """
        Yield AgentEvents as the agent works on the initial brief.

        At the end, yields a 'session' event whose content is the full
        conversation history (list of OpenAI messages). The caller should
        save this and pass it to refine_plan() on follow-up turns.
        """
        # OpenAI puts the system prompt INSIDE messages, unlike Anthropic.
        conversation: list[dict] = [
            {"role": "system", "content": planner_system_prompt()},
            {"role": "user", "content": brief},
        ]
        # Single loop body factored out so both first-turn and refine
        # turns share the same plan -> evaluate -> revise -> done flow.
        yield from self._run_until_done(conversation, brief)

    # -----------------------------------------------------------------
    # Public API: refinement (second turn onward)
    # -----------------------------------------------------------------
    def refine_plan(self, conversation: list[dict],
                    refinement: str) -> Iterator[AgentEvent]:
        """
        Continue an existing conversation with a refinement request.

        `conversation` is the message history yielded by the previous
        plan_trip() or refine_plan() call (via the 'session' event).
        `refinement` is the user's new request (e.g. "make the hotel
        cheaper", "add a beach day").

        The agent sees its prior plan AND the request, so it knows what
        to keep and what to change. It will:
          - Call tools again if the change requires new data
          - Or just re-render the plan with edits if no new data is needed
          - Re-run the evaluator at the end
        """
        # Wrap the refinement so the planner understands it's a follow-up,
        # not a brand-new brief. This framing matters: without it the model
        # sometimes starts over instead of editing.
        refinement_msg = (
            "The user has reviewed your previous plan and wants the "
            "following change. Update the plan accordingly — keep what "
            "still works, change only what the user asked for. Call tools "
            "again if you need fresh data. Respond with the FULL updated "
            "TRIP SUMMARY.\n\n"
            f"User's refinement request: {refinement}"
        )
        # Defensive copy so we don't mutate the caller's history mid-stream
        conversation = list(conversation) + [
            {"role": "user", "content": refinement_msg}
        ]
        yield from self._run_until_done(conversation, refinement)

    # -----------------------------------------------------------------
    # Shared core: plan -> evaluate -> revise -> done
    # -----------------------------------------------------------------
    def _run_until_done(self, conversation: list[dict],
                        latest_user_message: str) -> Iterator[AgentEvent]:
        """
        Run the planner/evaluator/revision flow until the plan passes or
        the revision cap is hit. Yields a 'session' event at the end with
        the final conversation history.
        """
        # Counter shared across all revisions of this run. We use a list
        # as a mutable container so the inner loop can increment it.
        # When this hits CONFIG.max_total_tool_calls we abort the whole
        # run with whatever plan exists. Without this, an agent thrashing
        # on an impossible constraint could burn 30+ API calls and run
        # for 10+ minutes — bad for users and for our quota.
        total_tool_calls = [0]

        for revision in range(CONFIG.max_revision_attempts + 1):
            # ----- INNER LOOP: planner builds (or edits) a plan -----
            final_text = ""
            hit_cap = False
            for event in self._run_planner_loop(conversation, revision, total_tool_calls):
                yield event
                if event.kind == "plan":
                    final_text = event.content
                if event.kind == "tool_cap_reached":
                    hit_cap = True

            # If we hit the safety cap, stop entirely — don't run another
            # revision that would just trigger more thrashing.
            if hit_cap:
                yield AgentEvent(
                    kind="done",
                    content=(
                        final_text
                        + "\n\n---\nNote: Atlas stopped here after "
                        f"{CONFIG.max_total_tool_calls} tool calls to avoid "
                        "an unbounded search. The plan above reflects what "
                        "was found; remaining gaps may indicate the request "
                        "is hard to satisfy with the current constraints "
                        "(e.g. budget too tight for the route or dates)."
                    ),
                    revision=revision,
                )
                yield AgentEvent(kind="session", content=conversation, revision=revision)
                return

            # ----- EVALUATOR: judge the plan against the LATEST request -----
            yield AgentEvent(kind="thought",
                             content="Evaluating plan against constraints...",
                             revision=revision)
            verdict = self._evaluate(latest_user_message, final_text)
            yield AgentEvent(kind="evaluation", content=verdict, revision=revision)

            if verdict.get("passes"):
                yield AgentEvent(kind="done", content=final_text, revision=revision)
                # Hand the conversation back to the caller for next turn
                yield AgentEvent(kind="session", content=conversation, revision=revision)
                return

            # Plan failed. Send the planner back with specific guidance.
            if revision >= CONFIG.max_revision_attempts:
                yield AgentEvent(
                    kind="done",
                    content=(
                        final_text
                        + "\n\n---\nNote: Could not fully satisfy all constraints "
                        f"after {CONFIG.max_revision_attempts} revisions. "
                        f"Remaining issues: {verdict.get('revision_guidance', '')}"
                    ),
                    revision=revision,
                )
                yield AgentEvent(kind="session", content=conversation, revision=revision)
                return

            revision_msg = (
                f"Your plan did not meet the constraints. Specific issue: "
                f"{verdict.get('revision_guidance', '')}. Revise the plan "
                f"and respond with the updated TRIP SUMMARY. You may call "
                f"tools again as needed."
            )
            conversation.append({"role": "user", "content": revision_msg})
            yield AgentEvent(kind="revision", content=revision_msg, revision=revision + 1)

    # -----------------------------------------------------------------
    # Inner loop: the tool-use cycle (OpenAI-style)
    # -----------------------------------------------------------------
    def _run_planner_loop(self, conversation: list[dict], revision: int,
                          total_tool_calls: list[int]) -> Iterator[AgentEvent]:
        """
        Run the LLM in a loop:
          1. Send messages + tools
          2. If response has tool_calls, run them and append results as 'tool' messages
          3. If finish_reason == 'stop', yield final text and return
        """
        for iteration in range(CONFIG.max_agent_iterations):
            response = self.client.chat.completions.create(
                model=CONFIG.model,
                messages=conversation,
                tools=TOOL_SCHEMAS,
                max_tokens=CONFIG.max_tokens_per_turn,
                # parallel_tool_calls=True is the default; lets the model
                # request multiple tool calls in one turn (e.g. hotels + weather
                # together). Saves round-trips and looks great in the demo.
            )

            choice = response.choices[0]
            message = choice.message

            # Append assistant turn to history EXACTLY as returned, including
            # tool_calls. The API needs the tool_call IDs to round-trip when
            # we send the tool results in the next turn.
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": message.content,  # may be None when tool_calls present
            }
            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            conversation.append(assistant_msg)

            # Surface any text the model produced as a "thought" event
            if message.content and message.content.strip():
                yield AgentEvent(
                    kind="thought",
                    content=message.content,
                    iteration=iteration,
                    revision=revision,
                )

            # If the model is done (no tool calls requested), this is the plan
            if choice.finish_reason != "tool_calls" or not message.tool_calls:
                final_text = message.content or ""
                yield AgentEvent(
                    kind="plan",
                    content=final_text,
                    iteration=iteration,
                    revision=revision,
                )
                return

            # Otherwise, execute each tool call (the model may request several
            # in parallel - we run them all before the next API call)
            for tc in message.tool_calls:
                # Hard safety cap: if we've already burned our budget of
                # tool calls for this run, stop here. The outer loop will
                # see the tool_cap_reached event and abort the whole run.
                if total_tool_calls[0] >= CONFIG.max_total_tool_calls:
                    yield AgentEvent(
                        kind="tool_cap_reached",
                        content=(
                            f"Stopped after {total_tool_calls[0]} tool calls "
                            "(safety cap). The agent was likely thrashing on "
                            "an unsatisfiable constraint."
                        ),
                        iteration=iteration,
                        revision=revision,
                    )
                    # Yield a final plan event with whatever text we have
                    yield AgentEvent(
                        kind="plan",
                        content=(message.content or
                                 "(No final plan text produced — tool call cap hit.)"),
                        iteration=iteration,
                        revision=revision,
                    )
                    return

                total_tool_calls[0] += 1
                name = tc.function.name
                # tc.function.arguments is a JSON STRING - must parse it
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                yield AgentEvent(
                    kind="tool_call",
                    content={"name": name, "input": args, "id": tc.id},
                    iteration=iteration,
                    revision=revision,
                )
                result_str = run_tool(name, args)
                yield AgentEvent(
                    kind="tool_result",
                    content={"name": name, "result": json.loads(
                        result_str), "id": tc.id},
                    iteration=iteration,
                    revision=revision,
                )

                # Each tool result is its own message with role='tool'
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

        # Hit the iteration cap. Emit whatever we have.
        yield AgentEvent(
            kind="plan",
            content="(Iteration limit reached. The agent did not converge on a final plan.)",
            iteration=CONFIG.max_agent_iterations,
            revision=revision,
        )

    # -----------------------------------------------------------------
    # Evaluator: a separate, lighter-weight LLM call
    # -----------------------------------------------------------------
    def _evaluate(self, original_brief: str, plan_text: str) -> dict:
        """
        Ask a fresh model instance to grade the plan. No tools - this is
        pure judgment. Uses JSON mode to guarantee parseable output.
        """
        eval_user_msg = (
            f"ORIGINAL BRIEF:\n{original_brief}\n\n"
            f"PROPOSED PLAN:\n{plan_text}\n\n"
            f"Evaluate now. Output JSON only."
        )
        response = self.client.chat.completions.create(
            model=CONFIG.model,
            messages=[
                {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
                {"role": "user", "content": eval_user_msg},
            ],
            max_tokens=1024,
            # JSON mode - forces the response to be valid JSON.
            # Big win over Anthropic for evaluator-type prompts.
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Fail-open: if the evaluator's output is malformed, accept the plan
            # rather than looping forever. Log so we notice.
            return {
                "passes": True,
                "violations": [],
                "revision_guidance": "",
                "_evaluator_parse_error": raw[:200],
            }


# ---------------------------------------------------------------------------
# CLI entrypoint (useful for quick testing without Streamlit)
# ---------------------------------------------------------------------------

def main() -> None:
    import sys
    brief = " ".join(sys.argv[1:]) or (
        "Plan a 4-day Lisbon trip in June for 2 people, $1800 total budget, "
        "must include a day trip to Sintra, vegetarian-friendly restaurants only."
    )
    print(f"\n>>> BRIEF: {brief}\n")
    agent = AtlasAgent()
    for event in agent.plan_trip(brief):
        if event.kind == "thought":
            print(f"[thought] {event.content[:200]}")
        elif event.kind == "tool_call":
            print(
                f"[tool_call] {event.content['name']}({event.content['input']})")
        elif event.kind == "tool_result":
            r = event.content["result"]
            n = len(r.get("results", [])) if isinstance(r, dict) else "?"
            print(
                f"[tool_result] {event.content['name']} -> {n} results (source: {r.get('source', '?')})")
        elif event.kind == "evaluation":
            print(
                f"[evaluation] passes={event.content.get('passes')} guidance={event.content.get('revision_guidance', '')[:120]}")
        elif event.kind == "revision":
            print(f"[REVISION {event.revision}] {event.content[:200]}")
        elif event.kind == "done":
            print("\n========== FINAL PLAN ==========\n")
            print(event.content)


if __name__ == "__main__":
    main()
