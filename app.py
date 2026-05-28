"""
app.py
------
Streamlit UI for ATLAS.

Aesthetic direction: cartographic editorial. Warm parchment palette,
serif display type, decorative coordinates, a compass rose. The agent is
framed as a navigator, not a chatbot. The styling is heavy but the
underlying logic is identical to the CLI — we just present the events
beautifully.

Run with: streamlit run app.py
"""

import json
import streamlit as st

from agent import AtlasAgent


# ============================================================================
# Page config
# ============================================================================

st.set_page_config(
    page_title="Atlas — Agentic Trip Planner",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================================
# The single style block. CSS variables drive the entire palette.
# ============================================================================

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500;9..144,600;9..144,700;9..144,900&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

<style>
    :root {
        --parchment:      #f3ecdc;
        --parchment-deep: #ebe2cc;
        --ivory:          #faf6ec;
        --ink:            #1a1d2e;
        --ink-soft:       #2d3142;
        --ink-muted:      #6c6660;
        --sienna:         #b85c38;
        --sienna-deep:    #8f4527;
        --brass:          #b8893a;
        --brass-pale:     #d4b478;
        --moss:           #4a6741;
        --moss-pale:      #7a9270;
        --burgundy:       #7d2f3b;
        --burgundy-pale:  #a5546c;
        --khaki:          #8a7a52;
        --khaki-pale:     #b5a584;
        --rule:           #d4c8ac;
    }

    /* ====== Background: paper + faint grid ====== */
    .stApp {
        background: var(--parchment);
        background-image:
            radial-gradient(circle at 25% 10%, rgba(184, 92, 56, 0.04) 0%, transparent 50%),
            radial-gradient(circle at 75% 90%, rgba(74, 103, 65, 0.04) 0%, transparent 50%),
            repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(26, 29, 46, 0.025) 39px, rgba(26, 29, 46, 0.025) 40px),
            repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(26, 29, 46, 0.025) 39px, rgba(26, 29, 46, 0.025) 40px);
    }

    /* Tighten Streamlit defaults */
    .block-container { padding-top: 3rem !important; padding-bottom: 3rem !important; max-width: 1400px; }
    [data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer, header { visibility: hidden; }

    /* ====== Typography defaults ====== */
    html, body, [class*="css"], .stMarkdown, p, span, div {
        font-family: 'Instrument Sans', system-ui, sans-serif !important;
        color: var(--ink);
    }

    /* ====== Page-load animation ====== */
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .atlas-fade-1 { animation: fadeUp 0.7s ease-out 0.05s both; }
    .atlas-fade-2 { animation: fadeUp 0.7s ease-out 0.18s both; }
    .atlas-fade-3 { animation: fadeUp 0.7s ease-out 0.32s both; }

    /* ====== HEADER ====== */
    .atlas-hero {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        align-items: center;
        gap: 24px;
        padding: 14px 0 32px;
        border-bottom: 1px solid var(--rule);
        margin-bottom: 36px;
    }
    .atlas-coord {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10.5px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: var(--ink-muted);
        line-height: 1.8;
    }
    .atlas-coord-right { text-align: right; }
    .atlas-coord-bold {
        color: var(--sienna-deep);
        font-weight: 600;
    }
    .atlas-center {
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
    }
    .atlas-wordmark {
        font-family: 'Fraunces', serif !important;
        font-weight: 600;
        font-size: 96px;
        letter-spacing: 14px;
        line-height: 1;
        color: var(--ink);
        text-indent: 14px; /* visual balance for letter-spacing */
        font-variation-settings: "opsz" 144, "SOFT" 100;
    }
    .atlas-tagline {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11px;
        letter-spacing: 4px;
        text-transform: uppercase;
        color: var(--ink-muted);
        padding-top: 4px;
    }
    .atlas-tagline-accent {
        color: var(--sienna);
        font-weight: 600;
    }
    .atlas-rule-decor {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 14px;
        opacity: 0.7;
    }
    .atlas-rule-decor span {
        height: 1px; width: 50px; background: var(--rule);
    }
    .atlas-rule-decor svg {
        width: 10px; height: 10px;
    }

    /* ====== Eyebrow / section labels ====== */
    .atlas-eyebrow {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10.5px;
        font-weight: 500;
        letter-spacing: 3px;
        text-transform: uppercase;
        color: var(--ink-muted);
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .atlas-eyebrow::before {
        content: '';
        width: 22px; height: 1px;
        background: var(--brass);
    }
    .atlas-eyebrow-num {
        color: var(--sienna);
        font-weight: 600;
    }

    /* ====== Brief input area ====== */
    [data-testid="stTextArea"] textarea {
        background: var(--ivory) !important;
        border: 1px solid var(--rule) !important;
        border-radius: 2px !important;
        font-family: 'Fraunces', serif !important;
        font-weight: 400;
        font-size: 17px !important;
        line-height: 1.6;
        color: var(--ink) !important;
        padding: 18px 22px !important;
        box-shadow: 0 1px 0 rgba(26, 29, 46, 0.03);
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stTextArea"] textarea:focus {
        border-color: var(--sienna) !important;
        box-shadow: 0 0 0 3px rgba(184, 92, 56, 0.1) !important;
        outline: none !important;
    }
    [data-testid="stTextArea"] label,
    [data-testid="stSelectbox"] label { display: none !important; }

    /* Selectbox styling */
    [data-testid="stSelectbox"] > div > div {
        background: var(--ivory) !important;
        border: 1px solid var(--rule) !important;
        border-radius: 2px !important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--ink-soft) !important;
    }

    /* ====== Primary button ====== */
    [data-testid="stButton"] button[kind="primary"] {
        background: var(--ink) !important;
        color: var(--parchment) !important;
        border: 1px solid var(--ink) !important;
        border-radius: 2px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        letter-spacing: 3px !important;
        text-transform: uppercase;
        padding: 14px 32px !important;
        transition: all 0.25s ease;
        box-shadow: 0 1px 0 rgba(26, 29, 46, 0.15);
    }
    /* Force color & font on every inner element — Streamlit wraps button text
       in <p>/<div>/<span> tags that pick up our global color: var(--ink) rule */
    [data-testid="stButton"] button[kind="primary"] *,
    [data-testid="stButton"] button[kind="primary"] p,
    [data-testid="stButton"] button[kind="primary"] div,
    [data-testid="stButton"] button[kind="primary"] span {
        color: var(--parchment) !important;
        font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: 3px !important;
    }
    [data-testid="stButton"] button[kind="primary"]:hover:not(:disabled) {
        background: var(--sienna) !important;
        border-color: var(--sienna) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(184, 92, 56, 0.25);
    }
    [data-testid="stButton"] button[kind="primary"]:hover:not(:disabled) *,
    [data-testid="stButton"] button[kind="primary"]:hover:not(:disabled) p {
        color: var(--ivory) !important;
    }
    [data-testid="stButton"] button[kind="primary"]:disabled {
        background: var(--parchment-deep) !important;
        color: var(--ink-muted) !important;
        border-color: var(--rule) !important;
    }
    [data-testid="stButton"] button[kind="primary"]:disabled *,
    [data-testid="stButton"] button[kind="primary"]:disabled p {
        color: var(--ink-muted) !important;
    }

    /* ====== Column headers ====== */
    .atlas-col-head {
        font-family: 'Fraunces', serif !important;
        font-weight: 500;
        font-size: 22px;
        color: var(--ink);
        letter-spacing: -0.3px;
        margin: 0 0 6px;
        font-variation-settings: "opsz" 144;
    }
    .atlas-col-sub {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10px;
        letter-spacing: 2.5px;
        text-transform: uppercase;
        color: var(--ink-muted);
        margin-bottom: 18px;
        padding-bottom: 18px;
        border-bottom: 1px solid var(--rule);
    }

    /* ====== Agent reasoning event cards ====== */
    .event {
        animation: fadeUp 0.4s ease-out both;
        margin: 8px 0;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 12.5px;
        line-height: 1.55;
    }

    /* — Thought (agent reasoning) — */
    .event-thought {
        padding: 10px 14px 10px 18px;
        color: var(--ink-soft);
        font-family: 'Fraunces', serif !important;
        font-size: 14.5px;
        font-style: italic;
        line-height: 1.6;
        border-left: 2px solid var(--brass);
        background: rgba(184, 137, 58, 0.04);
        border-radius: 0 2px 2px 0;
    }
    .event-thought::before {
        content: '◇';
        color: var(--brass);
        margin-right: 8px;
        font-style: normal;
    }

    /* — Tool call (model requests a function) — */
    .event-tool-call {
        background: var(--ink);
        color: var(--parchment);
        padding: 11px 16px;
        border-radius: 2px;
        border-left: 3px solid var(--brass-pale);
    }
    .event-tool-call .tag {
        color: var(--brass-pale);
        font-size: 10px;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-right: 10px;
    }
    .event-tool-call .fn {
        color: var(--ivory);
        font-weight: 600;
    }
    .event-tool-call .args {
        color: var(--parchment-deep);
        opacity: 0.85;
    }

    /* — Tool result OK — */
    .event-ok {
        background: var(--ivory);
        color: var(--ink);
        padding: 11px 16px;
        border-radius: 2px;
        border-left: 3px solid var(--moss);
    }
    .event-ok .tag {
        color: var(--moss);
        font-weight: 600;
        font-size: 10px;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-right: 10px;
    }
    .event-ok .source {
        color: var(--ink-muted);
        font-size: 11px;
        font-style: italic;
    }
    .event-ok details { margin-top: 6px; }
    .event-ok details summary {
        cursor: pointer;
        color: var(--ink-muted);
        font-size: 10px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    .event-ok details pre {
        background: var(--parchment);
        padding: 10px;
        border-radius: 2px;
        margin-top: 6px;
        font-size: 10.5px !important;
        color: var(--ink-soft);
        max-height: 200px;
        overflow: auto;
    }

    /* — Tool result no_results / unavailable — */
    .event-warn {
        background: var(--ivory);
        color: var(--ink-soft);
        padding: 11px 16px;
        border-radius: 2px;
        border-left: 3px solid var(--khaki-pale);
    }
    .event-warn .tag {
        color: var(--khaki);
        font-weight: 600;
        font-size: 10px;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-right: 10px;
    }
    .event-warn .reason {
        display: block;
        margin-top: 4px;
        color: var(--ink-muted);
        font-size: 11px;
        font-family: 'Instrument Sans', sans-serif !important;
        font-style: italic;
    }

    /* — Tool result error — */
    .event-error {
        background: var(--ivory);
        color: var(--burgundy);
        padding: 11px 16px;
        border-radius: 2px;
        border-left: 3px solid var(--burgundy);
    }
    .event-error .tag {
        color: var(--burgundy);
        font-weight: 700;
        font-size: 10px;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-right: 10px;
    }

    /* — Evaluation pass / fail — */
    .event-eval-pass {
        background: var(--moss);
        color: var(--ivory);
        padding: 14px 18px;
        margin: 14px 0;
        font-family: 'Fraunces', serif !important;
        font-size: 14px;
        font-weight: 500;
        letter-spacing: 1px;
        text-transform: uppercase;
        border-radius: 2px;
        box-shadow: 0 2px 0 var(--moss-pale);
    }
    .event-eval-pass::before { content: '✓  '; font-weight: 700; }

    .event-eval-fail {
        background: var(--burgundy);
        color: var(--ivory);
        padding: 14px 18px;
        margin: 14px 0;
        font-family: 'Fraunces', serif !important;
        font-size: 14px;
        font-weight: 500;
        border-radius: 2px;
        box-shadow: 0 2px 0 var(--burgundy-pale);
    }
    .event-eval-fail .head {
        letter-spacing: 1px;
        text-transform: uppercase;
        font-weight: 600;
    }
    .event-eval-fail .head::before { content: '✕  '; font-weight: 700; }
    .event-eval-fail .body {
        display: block;
        margin-top: 6px;
        font-size: 12.5px;
        font-style: italic;
        font-weight: 400;
        opacity: 0.95;
    }

    /* — Revision banner — */
    .event-revision {
        background: var(--sienna);
        color: var(--ivory);
        padding: 14px 18px;
        margin: 18px 0;
        font-family: 'Fraunces', serif !important;
        font-size: 14px;
        font-weight: 500;
        letter-spacing: 1px;
        text-transform: uppercase;
        border-radius: 2px;
        box-shadow: 0 2px 0 var(--sienna-deep);
        position: relative;
    }
    .event-revision::before {
        content: '↻ ';
        margin-right: 8px;
        font-weight: 700;
    }

    /* ====== Final plan card ====== */
    .atlas-plan {
        background: var(--ivory);
        border: 1px solid var(--rule);
        border-radius: 2px;
        padding: 28px 32px;
        font-family: 'Fraunces', serif !important;
        font-size: 15.5px;
        line-height: 1.7;
        color: var(--ink);
        box-shadow: 0 1px 0 rgba(26, 29, 46, 0.04);
    }
    .atlas-plan h1, .atlas-plan h2, .atlas-plan h3 {
        font-family: 'Fraunces', serif !important;
        color: var(--ink);
        font-weight: 600;
        font-variation-settings: "opsz" 144;
    }
    .atlas-plan strong {
        color: var(--sienna-deep);
        font-weight: 600;
    }
    .atlas-plan code {
        background: var(--parchment);
        color: var(--ink-soft);
        padding: 2px 6px;
        border-radius: 2px;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px;
    }
    .atlas-plan-empty {
        background: var(--ivory);
        border: 1px dashed var(--rule);
        padding: 60px 32px;
        text-align: center;
        font-family: 'Fraunces', serif !important;
        font-style: italic;
        color: var(--ink-muted);
        font-size: 15px;
        border-radius: 2px;
    }

    /* ====== Metric footer ====== */
    .atlas-metrics {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0;
        margin-top: 48px;
        padding-top: 28px;
        border-top: 1px solid var(--rule);
    }
    .atlas-metric {
        padding: 6px 24px;
        border-right: 1px solid var(--rule);
    }
    .atlas-metric:last-child { border-right: none; }
    .atlas-metric-label {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10px;
        letter-spacing: 2.5px;
        text-transform: uppercase;
        color: var(--ink-muted);
        margin-bottom: 8px;
    }
    .atlas-metric-value {
        font-family: 'Fraunces', serif !important;
        font-size: 36px;
        font-weight: 500;
        color: var(--ink);
        line-height: 1;
        font-variation-settings: "opsz" 144;
    }
    .atlas-metric-value.accent { color: var(--sienna); }
    .atlas-metric-value.success { color: var(--moss); }

    /* ============================================================
       DEVELOPER MODE TOGGLE — fixed, top-right corner
       ============================================================ */
    .dev-toggle-bar {
        position: fixed;
        top: 18px;
        right: 24px;
        z-index: 1000;
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 14px;
        background: var(--ivory);
        border: 1px solid var(--rule);
        border-radius: 999px;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10px;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: var(--ink-muted);
        box-shadow: 0 2px 6px rgba(26, 29, 46, 0.06);
    }
    /* Style the actual Streamlit toggle so it fits the aesthetic */
    [data-testid="stToggle"] {
        position: fixed !important;
        top: 12px;
        right: 24px;
        z-index: 1001;
        background: var(--ivory);
        border: 1px solid var(--rule);
        border-radius: 999px;
        padding: 6px 14px 6px 18px;
        box-shadow: 0 2px 6px rgba(26, 29, 46, 0.06);
    }
    [data-testid="stToggle"] label {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10px !important;
        letter-spacing: 2px !important;
        text-transform: uppercase !important;
        color: var(--ink-muted) !important;
    }
    [data-testid="stToggle"] label p {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10px !important;
        letter-spacing: 2px !important;
        text-transform: uppercase !important;
        color: var(--ink-muted) !important;
    }

    /* Dev mode "live" indicator pill */
    .dev-on-badge {
        position: fixed;
        top: 56px;
        right: 24px;
        z-index: 999;
        padding: 4px 10px;
        background: var(--sienna);
        color: var(--ivory) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 9px;
        letter-spacing: 2px;
        text-transform: uppercase;
        border-radius: 999px;
        box-shadow: 0 2px 6px rgba(184, 92, 56, 0.3);
        animation: dev-pulse 2s ease-in-out infinite;
    }
    @keyframes dev-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    /* ============================================================
       USER-FACING TIMELINE (default view — no dev mode)
       Single elegant chronological feed of friendly status lines
       ============================================================ */
    .timeline-card {
        background: var(--ivory);
        border: 1px solid var(--rule);
        border-radius: 2px;
        padding: 24px 28px;
        box-shadow: 0 1px 0 rgba(26, 29, 46, 0.04);
    }
    .timeline-item {
        display: flex;
        align-items: flex-start;
        gap: 14px;
        padding: 12px 0;
        border-bottom: 1px solid rgba(212, 200, 172, 0.4);
        animation: fadeUp 0.4s ease-out both;
        font-family: 'Instrument Sans', sans-serif !important;
    }
    .timeline-item:last-child { border-bottom: none; }
    .timeline-marker {
        flex-shrink: 0;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10px;
        font-weight: 700;
        margin-top: 1px;
    }
    .timeline-marker.done {
        background: var(--moss);
        color: var(--ivory);
    }
    .timeline-marker.thinking {
        background: var(--brass-pale);
        color: var(--ink);
    }
    .timeline-marker.warn {
        background: var(--khaki-pale);
        color: var(--ink);
    }
    .timeline-marker.error {
        background: var(--burgundy);
        color: var(--ivory);
    }
    .timeline-marker.live {
        background: var(--sienna);
        color: var(--ivory);
        animation: dev-pulse 1.4s ease-in-out infinite;
    }
    .timeline-marker.eval-pass {
        background: var(--moss);
        color: var(--ivory);
    }
    .timeline-marker.eval-fail {
        background: var(--burgundy);
        color: var(--ivory);
    }
    .timeline-marker.revision {
        background: var(--sienna);
        color: var(--ivory);
    }
    .timeline-body {
        flex: 1;
        min-width: 0;
    }
    .timeline-action {
        font-family: 'Fraunces', serif !important;
        font-size: 15.5px;
        color: var(--ink);
        line-height: 1.45;
        font-weight: 500;
        font-variation-settings: "opsz" 144;
    }
    .timeline-action.muted {
        color: var(--ink-muted);
        font-weight: 400;
    }
    .timeline-detail {
        font-family: 'Instrument Sans', sans-serif !important;
        font-size: 12.5px;
        color: var(--ink-muted);
        margin-top: 3px;
        font-style: italic;
        line-height: 1.4;
    }
    .timeline-detail b {
        color: var(--ink);
        font-weight: 600;
        font-style: normal;
    }
    .timeline-thought {
        padding: 8px 14px;
        margin: 6px 0;
        font-family: 'Fraunces', serif !important;
        font-style: italic;
        font-size: 14px;
        color: var(--ink-soft);
        border-left: 2px solid var(--brass);
        background: rgba(184, 137, 58, 0.04);
        line-height: 1.55;
    }
    .timeline-banner {
        padding: 12px 16px;
        margin: 14px 0;
        font-family: 'Fraunces', serif !important;
        font-size: 14px;
        font-weight: 500;
        letter-spacing: 0.5px;
        border-radius: 2px;
    }
    .timeline-banner.success {
        background: var(--moss);
        color: var(--ivory);
    }
    .timeline-banner.warn {
        background: var(--burgundy);
        color: var(--ivory);
    }
    .timeline-banner.revision {
        background: var(--sienna);
        color: var(--ivory);
    }

    /* ============================================================
       REFINEMENT SECTION — multi-turn chat after plan delivered
       ============================================================ */
    .refine-divider {
        margin: 48px 0 24px;
        padding-top: 32px;
        border-top: 1px solid var(--rule);
    }
    .refine-prompt {
        font-family: 'Fraunces', serif !important;
        font-size: 19px;
        font-weight: 500;
        color: var(--ink);
        line-height: 1.4;
        margin-bottom: 6px;
        font-variation-settings: "opsz" 144;
    }
    .refine-sub {
        font-family: 'Instrument Sans', sans-serif !important;
        font-size: 13.5px;
        color: var(--ink-muted);
        font-style: italic;
        margin-bottom: 18px;
    }
    .refine-chip-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 16px;
    }
    /* Refinement history — turns the user has taken so far */
    .refine-history-card {
        background: var(--ivory);
        border: 1px solid var(--rule);
        border-left: 3px solid var(--brass);
        border-radius: 2px;
        padding: 14px 18px;
        margin-bottom: 18px;
    }
    .refine-history-eyebrow {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10px;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: var(--ink-muted);
        margin-bottom: 10px;
    }
    .refine-history-item {
        font-family: 'Fraunces', serif !important;
        font-style: italic;
        font-size: 14px;
        color: var(--ink-soft);
        padding: 5px 0;
        line-height: 1.5;
    }
    .refine-history-item::before {
        content: '↳ ';
        color: var(--sienna);
        font-style: normal;
        margin-right: 4px;
    }

    /* The actual chat input — restyle Streamlit's chat_input */
    [data-testid="stChatInput"] {
        background: var(--ivory) !important;
        border: 1px solid var(--rule) !important;
        border-radius: 2px !important;
    }
    [data-testid="stChatInput"] textarea {
        background: var(--ivory) !important;
        font-family: 'Fraunces', serif !important;
        font-size: 16px !important;
        color: var(--ink) !important;
        line-height: 1.5 !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        border-color: var(--sienna) !important;
    }

    /* Secondary "Plan a new trip" button */
    [data-testid="stButton"] button[kind="secondary"] {
        background: transparent !important;
        color: var(--ink-muted) !important;
        border: 1px solid var(--rule) !important;
        border-radius: 2px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10.5px !important;
        font-weight: 500 !important;
        letter-spacing: 2px !important;
        text-transform: uppercase;
        padding: 8px 18px !important;
        transition: all 0.2s ease;
    }
    [data-testid="stButton"] button[kind="secondary"]:hover {
        color: var(--ink) !important;
        border-color: var(--ink) !important;
    }
    [data-testid="stButton"] button[kind="secondary"] * {
        color: inherit !important;
        font-family: inherit !important;
        letter-spacing: 2px !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Compass rose SVG — used in the header
# ============================================================================

COMPASS_SVG = '<svg viewBox="0 0 100 100" width="78" height="78" xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto"><defs><radialGradient id="comp-bg" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#faf6ec"/><stop offset="100%" stop-color="#f3ecdc"/></radialGradient></defs><circle cx="50" cy="50" r="48" fill="url(#comp-bg)" stroke="#1a1d2e" stroke-width="0.8"/><circle cx="50" cy="50" r="40" fill="none" stroke="#1a1d2e" stroke-width="0.3" stroke-dasharray="1 2"/><circle cx="50" cy="50" r="32" fill="none" stroke="#b8893a" stroke-width="0.4"/><polygon points="50,8 53,50 50,46 47,50" fill="#b85c38"/><polygon points="50,46 53,50 50,92 47,50" fill="#1a1d2e"/><polygon points="92,50 50,53 54,50 50,47" fill="#1a1d2e" opacity="0.85"/><polygon points="8,50 50,53 46,50 50,47" fill="#1a1d2e" opacity="0.85"/><line x1="22" y1="22" x2="78" y2="78" stroke="#b8893a" stroke-width="0.4"/><line x1="78" y1="22" x2="22" y2="78" stroke="#b8893a" stroke-width="0.4"/><text x="50" y="18" text-anchor="middle" font-family="Fraunces, serif" font-size="7" font-weight="700" fill="#1a1d2e">N</text><text x="84" y="53" text-anchor="middle" font-family="Fraunces, serif" font-size="6" font-weight="500" fill="#6c6660">E</text><text x="50" y="89" text-anchor="middle" font-family="Fraunces, serif" font-size="6" font-weight="500" fill="#6c6660">S</text><text x="16" y="53" text-anchor="middle" font-family="Fraunces, serif" font-size="6" font-weight="500" fill="#6c6660">W</text><circle cx="50" cy="50" r="2.4" fill="#1a1d2e"/><circle cx="50" cy="50" r="1.1" fill="#b8893a"/></svg>'

DIAMOND_SVG = '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg"><polygon points="5,0 10,5 5,10 0,5" fill="#b8893a"/></svg>'


# ============================================================================
# DEVELOPER MODE TOGGLE
# ----------------------------------------------------------------------------
# Fixed top-right. When OFF (default), users see a clean human-readable
# timeline. When ON, they see raw tool calls, JSON payloads, and the full
# agent trace — useful for demos to engineers, debugging, and proving the
# system is genuinely agentic.
# ============================================================================

dev_mode = st.toggle("Developer Mode", value=False, key="dev_mode")
if dev_mode:
    st.markdown('<div class="dev-on-badge">● dev view active</div>',
                unsafe_allow_html=True)


# ============================================================================
# HUMAN-FRIENDLY EVENT TRANSLATION
# ----------------------------------------------------------------------------
# Maps raw tool names and arguments into present-tense action phrases the
# user can read at a glance. This is the difference between
#   "search_flights(origin='JFK', destination='LIS', date='2026-06-15')"
# and
#   "Searching flights from JFK to Lisbon for June 15"
# ============================================================================

# Map IATA codes to friendly city names (common ones; falls back to the code)
_IATA_TO_CITY = {
    "JFK": "New York", "LGA": "New York", "EWR": "Newark",
    "BOS": "Boston", "LAX": "Los Angeles", "SFO": "San Francisco",
    "MIA": "Miami", "ORD": "Chicago", "ATL": "Atlanta", "SEA": "Seattle",
    "LIS": "Lisbon", "MAD": "Madrid", "BCN": "Barcelona",
    "LHR": "London", "LGW": "London", "CDG": "Paris", "ORY": "Paris",
    "AMS": "Amsterdam", "FRA": "Frankfurt", "FCO": "Rome", "MXP": "Milan",
    "NRT": "Tokyo", "HND": "Tokyo", "ICN": "Seoul", "HKG": "Hong Kong",
    "SIN": "Singapore", "DXB": "Dubai", "DEL": "Delhi", "BOM": "Mumbai",
    "SYD": "Sydney", "YYZ": "Toronto", "MEX": "Mexico City",
}


def _city(code: str) -> str:
    """Pretty-print an airport code as a city name when known."""
    if not code:
        return ""
    return _IATA_TO_CITY.get(code.upper(), code.upper())


def describe_tool_call(name: str, args: dict) -> str:
    """Turn a raw tool call into a present-tense user-facing phrase."""
    if name == "search_flights":
        origin = _city(args.get("origin", ""))
        dest = _city(args.get("destination", ""))
        date = args.get("date", "")
        return_date = args.get("return_date")
        if return_date:
            # Round-trip — show it as such, since round-trip pricing is the point
            return f"Searching round-trip flights from {origin} to {dest}"
        return f"Searching flights from {origin} to {dest}" + (f" for {date}" if date else "")
    if name == "search_hotels":
        city = args.get("city", "destination")
        return f"Searching hotels in {city}"
    if name == "get_weather_forecast":
        city = args.get("city", "destination")
        return f"Checking weather in {city}"
    if name == "search_activities":
        city = args.get("city", "destination")
        interest = args.get("interest")
        return f"Finding {interest} in {city}" if interest else f"Finding things to do in {city}"
    if name == "search_restaurants":
        city = args.get("city", "destination")
        dietary = args.get("dietary")
        cuisine = args.get("cuisine")
        qualifier = dietary or cuisine or ""
        prefix = f"{qualifier} " if qualifier else ""
        return f"Finding {prefix}restaurants in {city}".strip()
    return f"Running {name}"


def _pick_cheapest_flight(results: list) -> dict | None:
    """Find the cheapest valid flight in the results list."""
    valid = [r for r in results if isinstance(
        r.get("price_usd"), (int, float))]
    return min(valid, key=lambda r: r["price_usd"]) if valid else None


def _pick_best_value_hotel(results: list) -> dict | None:
    """
    Pick the hotel that best balances rating and price. Score = rating / nightly.
    Falls back to cheapest if no ratings are present.
    """
    valid = [r for r in results if isinstance(
        r.get("nightly_usd"), (int, float))]
    if not valid:
        return None
    rated = [r for r in valid if isinstance(r.get("rating"), (int, float))]
    if rated:
        return max(rated, key=lambda r: r["rating"] / max(r["nightly_usd"], 1))
    return min(valid, key=lambda r: r["nightly_usd"])


def _pick_top_rated(results: list) -> dict | None:
    """Pick the top-rated entry by rating, then by review count as tiebreaker."""
    rated = [r for r in results if isinstance(r.get("rating"), (int, float))]
    if not rated:
        return results[0] if results else None
    return max(rated, key=lambda r: (r["rating"], r.get("reviews") or 0))


def _format_duration(minutes: int | None) -> str:
    if not minutes or not isinstance(minutes, (int, float)):
        return ""
    h, m = divmod(int(minutes), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def describe_tool_result(name: str, args: dict, result: dict) -> tuple[str, str, str]:
    """
    Return (marker_class, headline, detail) for a friendly result line.

    The headline says what was found; the detail surfaces the standout pick
    (cheapest flight, best-value hotel, top-rated activity) so each line
    delivers information the user can act on, not just a count.
    """
    status = result.get("status", "ok")
    results_list = result.get("results", []) or []
    n = len(results_list)

    if status == "ok":
        # ---------- FLIGHTS — surface the cheapest ----------
        if name == "search_flights":
            origin = _city(args.get("origin", ""))
            dest = _city(args.get("destination", ""))
            is_roundtrip = bool(args.get("return_date"))
            kind = "round-trip option" if is_roundtrip else "flight option"
            head = f"Found {n} {kind}{'s' if n != 1 else ''} from {origin} to {dest}"
            pick = _pick_cheapest_flight(results_list)
            if pick:
                price = int(pick["price_usd"])
                airline = pick.get("airline") or "an airline"
                stops = pick.get("stops")
                stops_label = "non-stop" if stops == 0 else (
                    f"{stops} stop" if stops == 1 else
                    f"{stops} stops" if isinstance(stops, int) else ""
                )
                duration = _format_duration(pick.get("total_duration_min"))
                price_label = "Cheapest round-trip" if is_roundtrip else "Cheapest"
                bits = [f"{price_label}: <b>${price}</b> on {airline}"]
                if stops_label:
                    bits.append(stops_label)
                if duration:
                    bits.append(duration)
                return "done", head, " · ".join(bits)
            return "done", head, ""

        # ---------- HOTELS — surface the best-value pick ----------
        if name == "search_hotels":
            city = args.get("city", "the destination")
            head = f"Found {n} hotel{'s' if n != 1 else ''} in {city}"
            pick = _pick_best_value_hotel(results_list)
            if pick:
                rate = int(pick.get("nightly_usd") or 0)
                name_ = pick.get("name") or "a property"
                rating = pick.get("rating")
                bits = [f"Best value: <b>{name_}</b>"]
                bits.append(f"${rate}/night")
                if rating:
                    bits.append(f"★ {rating}")
                return "done", head, " · ".join(bits)
            return "done", head, ""

        # ---------- WEATHER — surface the temperature range ----------
        if name == "get_weather_forecast":
            city = args.get("city", "the destination")
            head = f"Got the weather forecast for {city}"
            if results_list:
                highs = [d.get("high_f")
                         for d in results_list if d.get("high_f") is not None]
                lows = [d.get("low_f")
                        for d in results_list if d.get("low_f") is not None]
                conditions = [d.get("condition")
                              for d in results_list if d.get("condition")]
                if highs and lows:
                    cond_summary = (
                        max(set(conditions), key=conditions.count).lower()
                        if conditions else ""
                    )
                    detail = f"<b>{min(lows)}–{max(highs)}°F</b>"
                    if cond_summary:
                        detail += f", mostly {cond_summary}"
                    return "done", head, detail
            return "done", head, ""

        # ---------- ACTIVITIES — surface the top-rated one ----------
        if name == "search_activities":
            city = args.get("city", "the destination")
            head = f"Found {n} thing{'s' if n != 1 else ''} to do in {city}"
            pick = _pick_top_rated(results_list)
            if pick and pick.get("name"):
                rating = pick.get("rating")
                bits = [f"Top pick: <b>{pick['name']}</b>"]
                if rating:
                    bits.append(f"★ {rating}")
                return "done", head, " · ".join(bits)
            return "done", head, ""

        # ---------- RESTAURANTS — surface the top-rated one ----------
        if name == "search_restaurants":
            city = args.get("city", "the destination")
            head = f"Found {n} restaurant{'s' if n != 1 else ''} in {city}"
            pick = _pick_top_rated(results_list)
            if pick and pick.get("name"):
                rating = pick.get("rating")
                tier = pick.get("price_tier")
                bits = [f"Top pick: <b>{pick['name']}</b>"]
                if rating:
                    bits.append(f"★ {rating}")
                if tier:
                    bits.append(tier)
                return "done", head, " · ".join(bits)
            return "done", head, ""

        return "done", f"{name} completed", ""

    if status == "over_budget":
        # Real options exist but exceed the user's budget. Show the
        # honest market price — this is a productive signal, not a failure.
        n_real = len(result.get("results", []) or [])

        if name == "search_flights":
            cheapest = result.get("cheapest_market_price_usd")
            cap = result.get("max_price_usd")
            origin = _city(args.get("origin", ""))
            dest = _city(args.get("destination", ""))
            head = f"Found {n_real} flight option{'s' if n_real != 1 else ''} from {origin} to {dest}"
            if cheapest and cap:
                detail = (
                    f"All are above your <b>${int(cap)}</b> budget · "
                    f"cheapest is <b>${int(cheapest)}</b>"
                )
            else:
                detail = "All results exceed the budget filter."
        elif name == "search_hotels":
            cheapest = result.get("cheapest_market_nightly_usd")
            cap = result.get("max_nightly_usd")
            city = args.get("city", "the destination")
            head = f"Found {n_real} hotel{'s' if n_real != 1 else ''} in {city}"
            if cheapest and cap:
                detail = (
                    f"All are above your <b>${int(cap)}</b>/night cap · "
                    f"cheapest is <b>${int(cheapest)}</b>/night"
                )
            else:
                detail = "All results exceed the nightly budget."
        else:
            head = f"{name} — over budget"
            detail = "All results exceeded the budget filter."

        # "warn" marker — visually distinct from a clean success, but still
        # signals the agent did its job and got real data back.
        return "warn", head, detail

    if status == "no_results":
        friendly = {
            "search_flights": "No flights matched",
            "search_hotels": "No hotels matched",
            "search_activities": "No activities found",
            "search_restaurants": "No restaurants found",
            "get_weather_forecast": "Weather data was empty",
        }
        return "warn", friendly.get(name, "No results"), "Trying a broader query may help."

    if status == "unavailable":
        friendly = {
            "search_flights": "Flight search is unavailable",
            "search_hotels": "Hotel search is unavailable",
            "get_weather_forecast": "Weather forecast is unavailable",
            "search_activities": "Activity search is unavailable",
            "search_restaurants": "Restaurant search is unavailable",
        }
        reason = result.get("reason", "")
        # Strip the developer-y "Set X in .env" suffix from the user view
        short_reason = reason.split(".")[0] if reason else "API not configured"
        return "warn", friendly.get(name, f"{name} unavailable"), short_reason

    if status == "error":
        return "error", f"Couldn't complete {name.replace('_', ' ')}", \
               "Atlas will continue with what it has."

    return "done", name, ""


# ============================================================================
# HEADER
# ============================================================================

st.markdown(
    '<div class="atlas-hero atlas-fade-1">'
    '<div class="atlas-coord">'
    '<div><span class="atlas-coord-bold">ESTABLISHED</span> · MMXXVI</div>'
    '<div>VOL. I · ED. 01</div>'
    '</div>'
    '<div class="atlas-center">'
    f'{COMPASS_SVG}'
    '<div class="atlas-wordmark">ATLAS</div>'
    '<div class="atlas-tagline">'
    '<span class="atlas-tagline-accent">An</span> Agentic '
    '<span class="atlas-tagline-accent">·</span> Trip '
    '<span class="atlas-tagline-accent">·</span> Planner'
    '</div>'
    '<div class="atlas-rule-decor">'
    f'<span></span>{DIAMOND_SVG}<span></span>'
    '</div>'
    '</div>'
    '<div class="atlas-coord atlas-coord-right">'
    '<div>OPENAI · TOOL USE</div>'
    '<div><span class="atlas-coord-bold">FIVE</span> AUTONOMOUS TOOLS</div>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================================
# INPUT SECTION
# ============================================================================

EXAMPLES = {
    "(custom brief)": "",
    "Lisbon — tight budget": (
        "Plan a 4-day Lisbon trip from June 15 to June 19, 2026 for 2 people. "
        "Departing from JFK. Budget $1800 total. Must include a day trip to "
        "Sintra. Vegetarian-friendly restaurants only."
    ),
    "Tokyo — foodie focus": (
        "Plan a 6-day Tokyo trip in October 2026 for 1 person, departing from BOS. "
        "Budget $3500. Focus on food experiences and modern art."
    ),
    "Miami — impossible budget": (
        "Plan a luxury 5-day Miami trip in July 2026 for 2 people staying at a "
        "5-star beachfront hotel. Budget: $1200 total."
    ),
}

st.markdown(
    '<div class="atlas-eyebrow atlas-fade-2">'
    '<span class="atlas-eyebrow-num">§ 01</span> Submit a Brief'
    '</div>',
    unsafe_allow_html=True,
)

# Why this dance: Streamlit widgets cache their value in session_state under
# their `key`. Just changing the `value=` parameter on rerun doesn't update
# the widget — its cached state wins. To make the example dropdown actually
# drive the text_area, we detect a change in the dropdown and overwrite the
# text_area's session state BEFORE rendering it.
if "last_example_pick" not in st.session_state:
    st.session_state.last_example_pick = "Lisbon — tight budget"
if "brief_input" not in st.session_state:
    st.session_state.brief_input = EXAMPLES["Lisbon — tight budget"]

cols = st.columns([3, 1])
with cols[1]:
    example_pick = st.selectbox(
        "Load example",
        list(EXAMPLES.keys()),
        index=list(EXAMPLES.keys()).index(st.session_state.last_example_pick),
        key="example_select",
    )

# If the user changed the dropdown since the last rerun, push the new
# example text into the text_area's state and trigger a rerun so the
# text_area picks it up. Without st.rerun(), the change wouldn't reflect
# until the user clicked into the text_area.
if example_pick != st.session_state.last_example_pick:
    st.session_state.last_example_pick = example_pick
    # "" for "(custom brief)"
    st.session_state.brief_input = EXAMPLES[example_pick]
    st.rerun()

with cols[0]:
    # No `value=` here — we let the widget read from session_state directly
    # via its `key`. This is the only way to programmatically clear or
    # change the input from outside the widget.
    brief = st.text_area(
        "Travel brief",
        height=120,
        placeholder="Describe your trip in natural language — destination, dates, budget, must-haves...",
        label_visibility="collapsed",
        key="brief_input",
    )

# Centered run button
btn_cols = st.columns([2, 1, 2])
with btn_cols[1]:
    run_btn = st.button(
        "▷  Plan Trip",
        type="primary",
        disabled=not brief.strip(),
        use_container_width=True,
    )


# ============================================================================
# SESSION STATE — persists across Streamlit reruns
# ----------------------------------------------------------------------------
# Streamlit reruns the whole script on every user interaction (button click,
# input change). We need explicit state to remember:
#   - `conversation`: the OpenAI message history (yielded by the agent's
#                     'session' event). Passed back in for refinements.
#   - `plan`:         the latest plan text, so refinement requests can
#                     redisplay it while the next run is in progress.
#   - `events_log`:   list of (mode, events) tuples — one entry per run.
#                     The most recent one is rendered in the timeline panel.
#   - `refinement_history`: human-readable log of what the user asked for
#                     in each turn. Shown above the chat input.
#   - `is_running`:   guard so the user can't double-submit while the
#                     agent is mid-flight.
# ============================================================================

if "conversation" not in st.session_state:
    st.session_state.conversation = None       # type: list[dict] | None
if "plan" not in st.session_state:
    st.session_state.plan = ""                 # latest plan text
if "events_to_render" not in st.session_state:
    st.session_state.events_to_render = None   # generator to consume on this rerun
if "refinement_history" not in st.session_state:
    st.session_state.refinement_history = []   # list of user refinement strings
if "tool_calls_total" not in st.session_state:
    st.session_state.tool_calls_total = 0
if "revisions_total" not in st.session_state:
    st.session_state.revisions_total = 0


def _kickoff_initial_run(brief_text: str) -> None:
    """Set up state for a fresh first-turn run on the next rerun."""
    agent = AtlasAgent()
    st.session_state.conversation = None
    st.session_state.plan = ""
    st.session_state.refinement_history = []
    st.session_state.tool_calls_total = 0
    st.session_state.revisions_total = 0
    st.session_state.events_to_render = agent.plan_trip(brief_text)


def _kickoff_refinement(refinement_text: str) -> None:
    """Set up state for a refinement turn on the next rerun."""
    if st.session_state.conversation is None:
        return  # safety: no plan yet, nothing to refine
    agent = AtlasAgent()
    st.session_state.refinement_history.append(refinement_text)
    st.session_state.events_to_render = agent.refine_plan(
        st.session_state.conversation, refinement_text
    )


# Wire the main button
if run_btn:
    _kickoff_initial_run(brief)


# ============================================================================
# AGENT RUN — executes when there's a generator queued up
# ============================================================================

if st.session_state.events_to_render is not None:
    st.markdown("<div style='height: 36px'></div>", unsafe_allow_html=True)

    # Column proportions depend on mode:
    # - Dev mode: 50/50 — agent reasoning panel deserves equal space
    # - User mode: 40/60 — the itinerary is the hero, status is a sidebar
    if dev_mode:
        left, right = st.columns([1, 1], gap="large")
    else:
        left, right = st.columns([2, 3], gap="large")

    with left:
        if dev_mode:
            st.markdown(
                '<div class="atlas-eyebrow">'
                '<span class="atlas-eyebrow-num">§ 02</span> Agent Reasoning'
                '</div>'
                '<div class="atlas-col-head">The Navigator at Work</div>'
                '<div class="atlas-col-sub">Live tool calls · decisions · revisions</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="atlas-eyebrow">'
                '<span class="atlas-eyebrow-num">§ 02</span> Progress'
                '</div>'
                '<div class="atlas-col-head">Atlas at Work</div>'
                '<div class="atlas-col-sub">A timeline of the journey</div>',
                unsafe_allow_html=True,
            )
        reasoning_box = st.container(height=620)

    with right:
        st.markdown(
            '<div class="atlas-eyebrow">'
            '<span class="atlas-eyebrow-num">§ 03</span> Final Itinerary'
            '</div>'
            '<div class="atlas-col-head">The Considered Plan</div>'
            '<div class="atlas-col-sub">Synthesized · evaluated · refined</div>',
            unsafe_allow_html=True,
        )
        plan_box = st.empty()
        # If we already have a plan (refinement turn), keep showing it while
        # the agent works. Otherwise show the empty-state placeholder.
        if st.session_state.plan:
            plan_box.markdown(
                f'<div class="atlas-plan">{st.session_state.plan}</div>',
                unsafe_allow_html=True,
            )
        else:
            plan_box.markdown(
                '<div class="atlas-plan-empty">The agent is charting your route. '
                'The final itinerary will appear here once the constraints are met.</div>',
                unsafe_allow_html=True,
            )

    # Carry totals across runs in this session for the dev-mode metrics
    final_plan = st.session_state.plan
    tool_call_count = st.session_state.tool_calls_total
    revision_count = st.session_state.revisions_total
    # Track in-flight tool calls so we can match them when the result comes back.
    # Maps tool_call_id -> (name, args)
    pending_calls: dict[str, tuple[str, dict]] = {}

    with reasoning_box:
        # We consume the generator that was queued in session_state by either
        # the initial-run button or the refinement chat input. After this
        # loop completes we clear it so the next Streamlit rerun doesn't
        # try to consume an already-exhausted generator.
        for event in st.session_state.events_to_render:

            # The 'session' event is a sentinel emitted by the agent at the
            # end of every run, carrying the full conversation history.
            # Persist it so the next refinement can pick up where we left off.
            if event.kind == "session":
                st.session_state.conversation = event.content
                continue

            # ============================================================
            # DEV MODE — raw, technical, exhaustive
            # ============================================================
            if dev_mode:
                if event.kind == "thought":
                    st.markdown(
                        f'<div class="event event-thought">{event.content}</div>',
                        unsafe_allow_html=True,
                    )

                elif event.kind == "tool_call":
                    tool_call_count += 1
                    name = event.content["name"]
                    args = ", ".join(f"{k}={v!r}" for k,
                                     v in event.content["input"].items())
                    st.markdown(
                        f'<div class="event event-tool-call">'
                        f'<span class="tag">CALL</span>'
                        f'<span class="fn">{name}</span>'
                        f'<span class="args">({args})</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                elif event.kind == "tool_result":
                    r = event.content["result"]
                    tool_name = event.content["name"]
                    status = r.get("status", "ok")

                    if status == "ok":
                        source = r.get("source", "?")
                        n = len(r.get("results", []))
                        preview = json.dumps(r.get("results", [])[
                                             :1], indent=2)[:400]
                        st.markdown(
                            f'<div class="event event-ok">'
                            f'<span class="tag">✓ {n} results</span>'
                            f'<b>{tool_name}</b> '
                            f'<span class="source">via {source}</span>'
                            f'<details><summary>preview payload</summary>'
                            f'<pre>{preview}…</pre></details>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    elif status == "over_budget":
                        n_real = len(r.get("results", []))
                        if tool_name == "search_flights":
                            cheapest = r.get("cheapest_market_price_usd")
                            cap = r.get("max_price_usd")
                            label = f"all above ${cap}; cheapest ${cheapest}"
                        elif tool_name == "search_hotels":
                            cheapest = r.get("cheapest_market_nightly_usd")
                            cap = r.get("max_nightly_usd")
                            label = f"all above ${cap}/night; cheapest ${cheapest}/night"
                        else:
                            label = "all results exceed filter"
                        st.markdown(
                            f'<div class="event event-warn">'
                            f'<span class="tag">$ over budget</span>'
                            f'<b>{tool_name}</b> — {n_real} results, {label}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    elif status == "no_results":
                        st.markdown(
                            f'<div class="event event-warn">'
                            f'<span class="tag">○ empty</span>'
                            f'<b>{tool_name}</b>'
                            f'<span class="reason">No results found for the given query.</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    elif status == "unavailable":
                        reason = r.get("reason", "API not configured.")
                        st.markdown(
                            f'<div class="event event-warn">'
                            f'<span class="tag">⊘ unavailable</span>'
                            f'<b>{tool_name}</b>'
                            f'<span class="reason">{reason}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    elif status == "error":
                        reason = r.get("reason", "Unknown error.")
                        st.markdown(
                            f'<div class="event event-error">'
                            f'<span class="tag">✕ error</span>'
                            f'<b>{tool_name}</b><br><small>{reason}</small>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                elif event.kind == "evaluation":
                    v = event.content
                    if v.get("passes"):
                        st.markdown(
                            '<div class="event-eval-pass">Evaluation passed — all constraints met</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        violations = v.get("violations", [])
                        viol_text = " · ".join(
                            f"{x.get('constraint')} ({x.get('severity')})" for x in violations
                        ) or "constraint violation"
                        guidance = v.get("revision_guidance", "")
                        st.markdown(
                            f'<div class="event-eval-fail">'
                            f'<span class="head">Evaluation failed — {viol_text}</span>'
                            f'<span class="body">{guidance}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                elif event.kind == "revision":
                    revision_count += 1
                    st.markdown(
                        f'<div class="event-revision">'
                        f'Revision №{revision_count} — sending the agent back with corrective guidance'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                elif event.kind == "plan":
                    final_plan = event.content
                    plan_box.markdown(
                        f'<div class="atlas-plan">{event.content}</div>',
                        unsafe_allow_html=True,
                    )

                elif event.kind == "done":
                    final_plan = event.content
                    plan_box.markdown(
                        f'<div class="atlas-plan">{event.content}</div>',
                        unsafe_allow_html=True,
                    )

            # ============================================================
            # USER MODE — clean, friendly, chronological timeline
            # ============================================================
            else:
                if event.kind == "thought":
                    # Surface thoughts sparingly — they add personality but
                    # can be noisy. Only show the substantive ones.
                    text = (event.content or "").strip()
                    # Skip the internal "Evaluating plan..." narration
                    if text and not text.lower().startswith("evaluating plan"):
                        # Truncate long thoughts so the timeline stays clean
                        preview = text if len(
                            text) < 280 else text[:280].rsplit(" ", 1)[0] + "…"
                        st.markdown(
                            f'<div class="timeline-thought">{preview}</div>',
                            unsafe_allow_html=True,
                        )

                elif event.kind == "tool_call":
                    # Track the call so we can describe the result later, but
                    # DON'T render a "Searching…" card. Why: in Streamlit we
                    # can't replace that card with a settled-state card when
                    # the result arrives — it would leave a stale "live"
                    # pulse on screen forever. Better to wait the 1-2 seconds
                    # and render only the result, with its real status.
                    tool_call_count += 1
                    pending_calls[event.content["id"]] = (
                        event.content["name"], event.content["input"]
                    )

                elif event.kind == "tool_result":
                    name = event.content["name"]
                    call_id = event.content.get("id")
                    args = pending_calls.get(call_id, (name, {}))[1]
                    marker_cls, headline, detail = describe_tool_result(
                        name, args, event.content["result"]
                    )
                    marker_glyph = {
                        "done": "✓", "warn": "⊘", "error": "✕"
                    }.get(marker_cls, "•")
                    detail_html = (
                        f'<div class="timeline-detail">{detail}</div>' if detail else ""
                    )
                    st.markdown(
                        f'<div class="timeline-item">'
                        f'<div class="timeline-marker {marker_cls}">{marker_glyph}</div>'
                        f'<div class="timeline-body">'
                        f'<div class="timeline-action">{headline}</div>'
                        f'{detail_html}'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                elif event.kind == "evaluation":
                    v = event.content
                    if v.get("passes"):
                        st.markdown(
                            '<div class="timeline-banner success">'
                            '✓  Plan reviewed — all your requirements are met'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        guidance = v.get("revision_guidance",
                                         "Refining the plan…")
                        st.markdown(
                            '<div class="timeline-banner warn">'
                            f'Reviewing the plan — adjustments needed<br>'
                            f'<span style="font-style:italic;font-size:12.5px;'
                            f'opacity:0.9;font-weight:400">{guidance}</span>'
                            '</div>',
                            unsafe_allow_html=True,
                        )

                elif event.kind == "revision":
                    revision_count += 1
                    st.markdown(
                        f'<div class="timeline-banner revision">'
                        f'↻  Refining the plan (revision №{revision_count})'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                elif event.kind == "plan":
                    final_plan = event.content
                    plan_box.markdown(
                        f'<div class="atlas-plan">{event.content}</div>',
                        unsafe_allow_html=True,
                    )

                elif event.kind == "done":
                    final_plan = event.content
                    plan_box.markdown(
                        f'<div class="atlas-plan">{event.content}</div>',
                        unsafe_allow_html=True,
                    )

    # Persist run results so the next rerun can render them above the
    # refinement input, and clear the generator so we don't iterate it twice.
    st.session_state.plan = final_plan
    st.session_state.tool_calls_total = tool_call_count
    st.session_state.revisions_total = revision_count
    st.session_state.events_to_render = None

    # ============================================================================
    # FOOTER METRICS — only shown in developer mode (numbers feel debug-y)
    # ============================================================================

    if dev_mode:
        status_label = "✓ Delivered" if final_plan else "—"
        status_class = "success" if final_plan else ""

        st.markdown(
            '<div class="atlas-metrics">'
            '<div class="atlas-metric">'
            '<div class="atlas-metric-label">Tool Calls Executed</div>'
            f'<div class="atlas-metric-value accent">{tool_call_count:02d}</div>'
            '</div>'
            '<div class="atlas-metric">'
            '<div class="atlas-metric-label">Revisions</div>'
            f'<div class="atlas-metric-value accent">{revision_count:02d}</div>'
            '</div>'
            '<div class="atlas-metric">'
            '<div class="atlas-metric-label">Final Outcome</div>'
            f'<div class="atlas-metric-value {status_class}">{status_label}</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )


# ============================================================================
# REFINEMENT SECTION — appears below the plan once one has been delivered
# ----------------------------------------------------------------------------
# Shows when:
#   - We have a saved plan AND a saved conversation
#   - We are NOT currently mid-flight (events_to_render is None)
# This makes Atlas multi-turn: the user can iteratively shape the plan
# instead of starting from a fresh brief every time.
# ============================================================================

if (st.session_state.plan
        and st.session_state.conversation is not None
        and st.session_state.events_to_render is None):

    st.markdown(
        '<div class="refine-divider">'
        '<div class="atlas-eyebrow">'
        '<span class="atlas-eyebrow-num">§ 04</span> Refine Your Plan'
        '</div>'
        '<div class="refine-prompt">Not quite right? Tell Atlas what to change.</div>'
        '<div class="refine-sub">'
        'Ask for a cheaper hotel, a different return flight, more outdoor '
        'activities, anything. Atlas will revise the plan above.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Show history of refinements the user has already made this session
    if st.session_state.refinement_history:
        history_html = (
            '<div class="refine-history-card">'
            '<div class="refine-history-eyebrow">Your refinements so far</div>'
        )
        for entry in st.session_state.refinement_history:
            # Defensive HTML escape on user input
            safe = (entry.replace("&", "&amp;").replace("<", "&lt;")
                         .replace(">", "&gt;"))
            history_html += f'<div class="refine-history-item">{safe}</div>'
        history_html += "</div>"
        st.markdown(history_html, unsafe_allow_html=True)

    # The chat input. submitting it queues a refinement run for the next rerun.
    refinement = st.chat_input(
        "What would you like to change? (e.g. 'make the hotel cheaper', "
        "'add a day in Coimbra', 'evening return flight instead')"
    )
    if refinement and refinement.strip():
        _kickoff_refinement(refinement.strip())
        st.rerun()

    # Escape hatch: clear everything and start fresh
    reset_cols = st.columns([3, 1])
    with reset_cols[1]:
        if st.button("↻  Plan a new trip", type="secondary",
                     use_container_width=True, key="reset_button"):
            st.session_state.conversation = None
            st.session_state.plan = ""
            st.session_state.refinement_history = []
            st.session_state.events_to_render = None
            st.session_state.tool_calls_total = 0
            st.session_state.revisions_total = 0
            st.rerun()
