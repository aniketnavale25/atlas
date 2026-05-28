# 🧭 Atlas

> An agentic AI trip planner that *actually plans*. Give it a natural-language brief and it autonomously orchestrates real flight, hotel, weather, activity, and restaurant APIs — with a self-evaluating revision loop and multi-turn refinement.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Try%20Atlas-b85c38?style=for-the-badge)](https://YOUR-DEPLOY-URL.streamlit.app)
[![Built with OpenAI](https://img.shields.io/badge/Built%20with-OpenAI%20Tool%20Use-4a6741?style=for-the-badge)](https://platform.openai.com/docs/guides/function-calling)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-1a1d2e?style=for-the-badge)](https://streamlit.io)

---

## What it does

Tell Atlas where you want to go in plain English:

> *"Plan a 4-day Lisbon trip from June 15 to June 19 for 2 people. Departing from BOS. Budget $2500. Vegetarian-friendly restaurants only. Must include a day trip to Sintra."*

It autonomously:

1. **Extracts your constraints** (dates, budget, dietary needs, must-includes)
2. **Calls 5 real APIs in parallel** — flights, hotels, weather, activities, restaurants
3. **Makes real decisions** — picks the cheapest non-stop, the best-value hotel, the top-rated vegetarian spots
4. **Builds a day-by-day itinerary** with concrete prices and a running total
5. **Self-evaluates** against your constraints; if the plan misses, a separate evaluator agent sends it back to revise
6. **Lets you refine** — *"swap the hotel for something beachfront"* — and it updates the plan in place

---

## Why this is agentic (not a chatbot)

Most "AI travel planner" demos are chatbots that generate prose. Atlas is built on the **agentic loop**: the LLM decides which tool to call, runs it, observes the result, and decides what to do next — without a hardcoded workflow.

Specifically:

- **Real tool use** — every search hits a live API (SerpAPI Google Flights, Google Hotels, Google Maps, OpenWeatherMap). No mock data. Failed searches return structured `status: "unavailable" | "error" | "over_budget"` responses so the agent can reason about gaps instead of fabricating.
- **Parallel tool calls** — the model can request hotels + weather + activities in a single turn (OpenAI's `parallel_tool_calls`), cutting latency.
- **Autonomous decisions** — the agent picks airlines, hotels, restaurants based on the brief, not a template. Tradeoffs are surfaced explicitly.
- **Self-correction** — a separate evaluator agent grades each plan against the brief and triggers up to 2 revisions if it falls short. Bounded so it can't loop forever.
- **Multi-turn refinement** — caller-owned conversation history (à la Claude/ChatGPT) lets users iteratively shape the plan instead of starting over.
- **Honest tool surfaces** — when SerpAPI returns flights that are all over budget, the tool returns them anyway with `status: "over_budget"` and the real market price. The agent never pretends "no flights exist" when they do.

---

## Architecture

```
                  ┌─────────────────┐
   User brief ──▶ │  PLANNER AGENT  │ ◀── system prompt + tool schemas
                  │   (gpt-4o-mini) │
                  └────────┬────────┘
                           │
              ┌────────────┼─────────────┬────────────┬──────────────┐
              ▼            ▼             ▼            ▼              ▼
         flights       hotels        weather      activities    restaurants
         (SerpAPI)    (SerpAPI)   (OpenWeather)   (SerpAPI)     (SerpAPI)
              │            │             │            │              │
              └────────────┴──────┬──────┴────────────┴──────────────┘
                                  │ tool results (parallel)
                                  ▼
                          (loop until done)
                                  │
                                  ▼
                          PROPOSED PLAN
                                  │
                                  ▼
                  ┌─────────────────────┐
                  │  EVALUATOR AGENT    │  (JSON mode, no tools)
                  └─────────┬───────────┘
                            │
                   ┌────────┴────────┐
                   ▼                 ▼
                 pass             fail (≤2 revisions)
                   │                 │
                   ▼                 │
              FINAL PLAN  ◀──────────┘ revision guidance fed back
                   │
                   ▼
             USER REFINES?  ──▶ refine_plan(history, change request)
                                       │
                                       ▼
                          (full loop runs again with context)
```

### Files

| File          | Role                                                       |
| ------------- | ---------------------------------------------------------- |
| `app.py`      | Streamlit UI — cartographic editorial design, two modes (default + dev) |
| `agent.py`    | The agent loop. `plan_trip()` + `refine_plan()`. ~250 lines |
| `tools.py`    | Tool schemas + real API implementations + structured error responses |
| `prompts.py`  | Planner and evaluator system prompts (dynamic, with current date injected) |
| `config.py`   | API keys, model selection, agent loop guardrails           |

---

## Quickstart

### Prerequisites
- Python 3.10+
- An OpenAI API key
- A SerpAPI key (free tier — 100 searches/month covers ~15 full agent runs)
- *(Optional)* An OpenWeatherMap key for weather forecasts within 5 days

### Setup

```bash
git clone https://github.com/YOUR_USERNAME/atlas.git
cd atlas

python -m venv .venv
# Mac/Linux:
source .venv/bin/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Configure API keys

Copy the example file and add your real keys:

```bash
cp .env.example .env
```

Edit `.env`:

```
OPENAI_API_KEY=sk-...
SERPAPI_KEY=...
OPENWEATHER_API_KEY=    # optional
```

### Run

```bash
# Full UI
streamlit run app.py

# Or quick CLI test
python agent.py "Plan a 4-day Lisbon trip in June for 2 people, $2500 budget"
```

---

## Design choices worth calling out

### 1. Stateless agent, caller-owned conversation
The agent itself is pure: `plan_trip()` and `refine_plan()` both take all state as arguments and yield events. The UI persists the conversation in session state and passes it back. This is the same pattern Claude and ChatGPT use; it makes the agent trivially testable and lets the UI replay or fork conversations cleanly.

### 2. Planner + Evaluator as separate agents
A single agent grading its own output tends to rationalize. Splitting the planner (who builds) from the evaluator (who judges, using JSON mode for guaranteed parseable verdicts) creates honest tension and catches real failure modes — missing flights, fabricated restaurants, no concrete total cost.

### 3. Honest tool surfaces
Every tool returns one of `ok` / `no_results` / `unavailable` / `over_budget` / `error`. The agent reasons differently about each. Critically, **filters never silently drop results** — if all 10 hotels in Lisbon are over your $80/night cap, the tool returns them anyway with `status: "over_budget"` and the cheapest market price. This prevents the agent from confidently telling you "no hotels found" when reality is "hotels exist, just expensive."

### 4. Bounded everything
2 revisions max, 10 iterations per turn max, 25 total tool calls per run max. Without these caps, the agent will thrash for 10+ minutes on impossible briefs (e.g. a Lisbon trip on a $500 budget). With them, every run completes in under 90 seconds with a clear outcome.

### 5. Dynamic date injection
LLMs are time-blind unless you tell them. The planner prompt is generated per request with the actual current date and worked examples (*"User says 'May 25' → use 2026-05-25 if upcoming, else 2027-05-25"*). This eliminated a class of bugs where the agent would pick dates from its training distribution (2023, 2024) and fail every flight call with a "past date" error.

### 6. Developer mode toggle
Default UI is product-grade: clean timeline with plain-English status ("Searching round-trip flights from Boston to Lisbon", "Best value: Lisbon Poets Inn · $76/night · ★ 4.5"). Toggle dev mode in the top-right and the same run shows raw tool calls, JSON payloads, source attribution, and metrics. This solves the design tension between "beautiful demo" and "prove it's actually agentic."

---

## Demo scenarios

Three example briefs included in the UI dropdown:

- **Lisbon — tight budget** — typical happy path with real constraints
- **Tokyo — foodie focus** — long brief, multiple cultural preferences
- **Miami — impossible budget** — designed to fail the first plan and trigger the revision loop visibly

Try the Miami one — it's the best showcase of the self-correction behavior.

---

## What's missing / future work

Honest list of limitations:

- **Read-only tools** — Atlas plans but doesn't book. Real production agents (Manus, ChatGPT Agent) can actually click buttons and complete transactions. Adding a "draft itinerary email" or real booking handoff would close this gap.
- **No persistent memory across sessions** — preferences (favorite airlines, dietary defaults) reset every visit. A SQLite + embeddings layer would solve this.
- **No evals harness** — every prompt change is verified by manual testing. A proper eval suite (canonical briefs + expected behaviors + automated regression checks) would catch breakages before they ship.
- **Limited observability** — the dev mode is good for debugging individual runs but there's no aggregate view (latency distributions, tool failure rates, cost per run).
- **Single-shot per turn** — the model can't ask clarifying questions mid-plan; it makes assumptions and surfaces them.

These gaps are intentional — Atlas is a portfolio demonstration of the core agentic loop, not a production booking system.

---

## Built with

- **OpenAI** — `gpt-4o-mini` for both planner and evaluator (chosen for higher rate limits and faster runs over `gpt-4o`)
- **SerpAPI** — Google Flights, Google Hotels, Google Maps engines
- **OpenWeatherMap** — 5-day weather forecasts
- **Streamlit** — UI and deployment
- **Python 3.11+**

---

## License

MIT — do whatever you want, but no warranty.

---

*Built by [Aniket Navale](https://github.com/YOUR_USERNAME) as a portfolio demonstration of agentic AI architecture patterns.*