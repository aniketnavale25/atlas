"""
config.py
---------
Centralizes configuration: API keys, model selection, agent loop limits.

Loads secrets from two sources, in order:
  1. Environment variables (set by .env locally, or by the host platform)
  2. Streamlit secrets (set in Streamlit Cloud's "Secrets" UI)

This dual-source design means the same code runs unchanged whether you're
developing locally with a .env file or deployed to Streamlit Community
Cloud. No edits required for deployment.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """
    Read a secret from env first, then Streamlit secrets if available.
    Env wins because it's how local .env loading works and how every
    other host (Fly, Railway, Render) injects config.
    """
    # 1. Environment variable (covers local .env + most cloud hosts)
    value = os.getenv(key)
    if value:
        return value

    # 2. Streamlit secrets (used by Streamlit Community Cloud).
    # We import lazily inside a try block so this module still imports
    # cleanly in environments where streamlit isn't installed (e.g. CLI tests).
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except (ImportError, FileNotFoundError, Exception):
        # FileNotFoundError fires when streamlit can't find secrets.toml,
        # which is the normal local-dev case; not an error.
        pass

    return default


@dataclass(frozen=True)
class Config:
    # --- LLM ---
    openai_api_key: str = _get_secret("OPENAI_API_KEY")

    # Default to gpt-4o-mini: same tool-use API, ~6× higher rate limits
    # (200k TPM vs 30k on the free tier), ~16× cheaper, and noticeably faster.
    # For an agentic planner the speed matters more than the marginal IQ
    # advantage of gpt-4o — you can stack many more tool calls before
    # hitting any throttle. Swap up only if you see quality regress:
    #   - "gpt-4o"          # higher reasoning, lower rate limit
    #   - "gpt-4.1"         # better at long context + tool use (if you have access)
    model: str = "gpt-4o-mini"
    max_tokens_per_turn: int = 4096

    # --- External APIs (all optional; missing keys -> tool returns unavailable) ---
    serpapi_key: str = _get_secret("SERPAPI_KEY")
    openweather_api_key: str = _get_secret("OPENWEATHER_API_KEY")

    # --- Agent loop guardrails ---
    # Hard ceiling on tool-call iterations PER planner turn. A turn is one
    # LLM call + its tool calls. Most plans converge in 3-6 iterations; we
    # cap at 10 to prevent runaway loops on impossible briefs.
    max_agent_iterations: int = 10

    # Max times the constraint-evaluator is allowed to send the agent
    # back to revise. Without this it could loop forever on impossible briefs.
    # Two is enough: first plan + one revision. Three felt like punishing
    # the user with watching the agent thrash on unsatisfiable constraints.
    max_revision_attempts: int = 2

    # Hard ceiling on TOTAL tool calls across all revisions in a single run.
    # This is the safety net for when the agent ignores the prompt and
    # keeps retrying a failing search. Once hit, the run ends with whatever
    # plan exists. Each SerpAPI call also costs us part of the 100/month
    # free tier, so this matters financially too.
    max_total_tool_calls: int = 25

    def require_openai(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Locally: copy .env.example to .env "
                "and set your key. On Streamlit Cloud: add it under "
                "Settings → Secrets."
            )


CONFIG = Config()
