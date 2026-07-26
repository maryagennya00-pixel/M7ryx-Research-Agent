# research_agent/app.py
import warnings
warnings.filterwarnings("ignore")

import os
import base64
import streamlit as st
import json
from datetime import datetime
from pathlib import Path

HISTORY_FILE = "./output/research_history.json"

def load_history() -> list:
    if Path(HISTORY_FILE).exists():
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_to_history(topic: str, report: str, quality: float, sources: int):
    """Append a report entry to the history file."""
    history = load_history()
    entry = {
        "topic": topic,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "quality": round(quality, 2),
        "sources": sources,
        "preview": report[:2000],
        "report": report,
    }
    history.insert(0, entry)
    history = history[:20]
    Path(HISTORY_FILE).parent.mkdir(exist_ok=True)  # FIX: was exists_ok=True (typo, TypeError)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


from config import DEPTH_CONFIGS, GROQ_API_KEY, TAVILY_API_KEY
from tools import run_pipeline
from synthesizer import run_synthesis
from utils import report_to_pdf, send_email_report

# --------------------------------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="m7ryx",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --------------------------------------------------------------------------
# BACKGROUND IMAGE -> BASE64
# --------------------------------------------------------------------------
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
BG_PATH = os.path.join(ASSET_DIR, "galaxy_bg.png")


@st.cache_data(show_spinner=False)
def _load_bg_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


bg_b64 = ""
if os.path.exists(BG_PATH):
    bg_b64 = _load_bg_b64(BG_PATH)
else:
    st.warning(
        f"Background image not found at `{BG_PATH}`. "
        "Make sure `assets/galaxy_bg.png` sits in the same folder as app.py."
    )

# --------------------------------------------------------------------------
# CSS
# --------------------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
    --ink:        #E9ECF6;
    --ink-dim:    #A4ABC2;
    --line:       rgba(233, 236, 246, 0.14);
    --glass:      rgba(14, 17, 30, 0.52);
    --glass-soft: rgba(14, 17, 30, 0.34);
    --star:       #7C96FF;
    --star-soft:  #A9B8FF;
    --nova:       #F2C879;
    --violet:     #9B7EDE;
}}

/* ---- background (multiple selectors for cross-version compatibility) ---- */
html, body, .stApp, [data-testid="stAppViewContainer"] {{
    background-color: #05070f !important;
}}
.stApp, [data-testid="stAppViewContainer"] {{
    background-image:
        linear-gradient(180deg, rgba(3,5,12,0.55) 0%, rgba(3,5,12,0.72) 55%, rgba(3,5,12,0.92) 100%),
        url("data:image/png;base64,{bg_b64}") !important;
    background-size: cover !important;
    background-position: center top !important;
    background-attachment: fixed !important;
    background-repeat: no-repeat !important;
}}
[data-testid="stAppViewContainer"] > .main {{
    background: transparent !important;
}}
[data-testid="stHeader"] {{
    background: transparent;
}}
[data-testid="stToolbar"] {{ display: none; }}
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}

.block-container {{
    max-width: 880px;
    padding-top: 4.5rem;
    padding-bottom: 5rem;
}}

* {{ font-family: 'Inter', sans-serif; }}

/* ---- hero ---- */
.nova-eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--star-soft);
    text-align: center;
    margin-bottom: 1.1rem;
    opacity: 0.85;
}}
.nova-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 3.1rem;
    line-height: 1.08;
    text-align: center;
    color: var(--ink);
    letter-spacing: -0.01em;
    margin-bottom: 0.6rem;
}}
.nova-title em {{
    font-style: normal;
    background: linear-gradient(90deg, var(--star-soft), var(--nova));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}}
.nova-sub {{
    text-align: center;
    color: var(--ink-dim);
    font-size: 1.02rem;
    max-width: 560px;
    margin: 0 auto 2.6rem auto;
    line-height: 1.6;
}}

/* ---- constellation rail: search -> synthesize -> report ---- */
.nova-rail {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    margin-bottom: 2.2rem;
}}
.nova-node {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    width: 110px;
}}
.nova-dot {{
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--star-soft);
    box-shadow: 0 0 10px 2px rgba(169, 184, 255, 0.55);
}}
.nova-node span {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--ink-dim);
}}
.nova-link {{
    flex: 1;
    height: 1px;
    max-width: 70px;
    background: linear-gradient(90deg, rgba(124,150,255,0.05), rgba(124,150,255,0.55), rgba(124,150,255,0.05));
    margin-top: -18px;
}}

/* ---- glass input card ---- */
.nova-card {{
    background: var(--glass);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 1.6rem 1.6rem 1.3rem 1.6rem;
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    box-shadow: 0 20px 60px -20px rgba(0,0,0,0.6);
}}

div[data-testid="stTextInput"] input {{
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid var(--line) !important;
    border-radius: 12px !important;
    color: var(--ink) !important;
    font-size: 1.02rem !important;
    padding: 0.9rem 1rem !important;
}}
div[data-testid="stTextInput"] input:focus {{
    border-color: var(--star) !important;
    box-shadow: 0 0 0 3px rgba(124,150,255,0.18) !important;
}}
div[data-testid="stTextInput"] input::placeholder {{ color: var(--ink-dim) !important; }}
div[data-testid="stTextInput"] label {{ display: none; }}

/* depth pills via radio */
div[role="radiogroup"] {{
    gap: 0.5rem;
}}
div[role="radiogroup"] label {{
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.35rem 0.95rem !important;
    color: var(--ink-dim) !important;
    font-size: 0.85rem;
    transition: all 0.15s ease;
}}
div[role="radiogroup"] label:hover {{ border-color: var(--star); color: var(--ink) !important; }}

/* buttons */
.stButton > button {{
    background: linear-gradient(135deg, var(--star), var(--violet));
    color: #0A0C16;
    font-weight: 600;
    border: none;
    border-radius: 12px;
    padding: 0.7rem 1.6rem;
    font-size: 0.95rem;
    width: 100%;
    box-shadow: 0 8px 24px -8px rgba(124,150,255,0.5);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}}
.stButton > button:hover {{
    transform: translateY(-1px);
    box-shadow: 0 10px 30px -8px rgba(124,150,255,0.65);
}}
.stDownloadButton > button {{
    background: rgba(255,255,255,0.05);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 12px;
    font-weight: 500;
}}

/* progress ticker */
.nova-status {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    color: var(--star-soft);
    text-align: center;
    padding: 0.9rem 0 0.2rem 0;
}}

/* report card */
.nova-report {{
    background: var(--glass-soft);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 2.2rem 2.4rem;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    margin-top: 1.6rem;
    color: var(--ink);
    line-height: 1.7;
}}
.nova-report h1 {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.7rem;
    color: var(--ink);
    margin-bottom: 1rem;
}}
.nova-report h2 {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.15rem;
    color: var(--star-soft);
    margin-top: 1.8rem;
    border-bottom: 1px solid var(--line);
    padding-bottom: 0.5rem;
}}
.nova-report a {{ color: var(--nova); }}

/* quality badges */
.nova-badges {{ display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 1rem 0 0 0; }}
.nova-badge {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: var(--ink-dim);
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.3rem 0.8rem;
}}
.nova-badge b {{ color: var(--star-soft); }}

hr {{ border-color: var(--line); }}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# SESSION STATE
# --------------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "running" not in st.session_state:
    st.session_state.running = False

# --------------------------------------------------------------------------
# HERO
# --------------------------------------------------------------------------
st.markdown('<div class="nova-eyebrow">Autonomous Research Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="nova-title">m7ryx</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="nova-sub">m7ryx searches the live web, cross-checks sources, and writes a '
    'structured brief with citations, in minutes — not hours.</div>',
    unsafe_allow_html=True,
)

st.markdown("""
<div class="nova-rail">
  <div class="nova-node"><div class="nova-dot"></div><span>Search</span></div>
  <div class="nova-link"></div>
  <div class="nova-node"><div class="nova-dot"></div><span>Synthesize</span></div>
  <div class="nova-link"></div>
  <div class="nova-node"><div class="nova-dot"></div><span>Report</span></div>
</div>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# INPUT CARD
# --------------------------------------------------------------------------
st.markdown('<div class="nova-card">', unsafe_allow_html=True)

topic = st.text_input(
    "topic",
    placeholder="e.g. The economic impact of offshore wind energy in 2026",
    label_visibility="collapsed",
)

col_a, col_b = st.columns([2.2, 1])
with col_a:
    depth = st.radio(
        "depth",
        options=list(DEPTH_CONFIGS.keys()),
        index=1,
        horizontal=True,
        label_visibility="collapsed",
    )
with col_b:
    run_clicked = st.button("Run research →", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

if not GROQ_API_KEY or not TAVILY_API_KEY:
    st.markdown(
        '<div class="nova-status">Missing API keys — add GROQ_API_KEY and TAVILY_API_KEY '
        'to your .env or Streamlit secrets.</div>',
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------
# PIPELINE EXECUTION
# --------------------------------------------------------------------------
status_slot = st.empty()


def _progress(msg: str):
    status_slot.markdown(f'<div class="nova-status">{msg}</div>', unsafe_allow_html=True)


if run_clicked and topic.strip():
    st.session_state.running = True
    try:
        pipeline_result = run_pipeline(topic.strip(), depth, progress_callback=_progress)
        if pipeline_result["source_count"] == 0:
            status_slot.markdown(
                '<div class="nova-status">No usable sources found — try rephrasing the topic.</div>',
                unsafe_allow_html=True,
            )
        else:
            synthesis = run_synthesis(pipeline_result, progress_callback=_progress)
            st.session_state.result = {"pipeline": pipeline_result, "synthesis": synthesis}
            status_slot.empty()
    except Exception as e:
        status_slot.markdown(
            f'<div class="nova-status">Something interrupted the run: {e}</div>',
            unsafe_allow_html=True,
        )
    st.session_state.running = False
elif run_clicked:
    status_slot.markdown(
        '<div class="nova-status">Enter a topic to begin.</div>',
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------
# RESULTS
# --------------------------------------------------------------------------
if st.session_state.result:
    pipeline_result = st.session_state.result["pipeline"]
    synthesis = st.session_state.result["synthesis"]
    quality = synthesis["quality_scores"]

    st.markdown('<div class="nova-report">', unsafe_allow_html=True)
    st.markdown(synthesis["report"])
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="nova-badges">
        <div class="nova-badge">Sources <b>{pipeline_result['source_count']}</b></div>
        <div class="nova-badge">Depth <b>{pipeline_result['depth']}</b></div>
        <div class="nova-badge">Grounding <b>{synthesis['findings']['grounding_score']}</b></div>
        <div class="nova-badge">Quality <b>{quality.get('overall', 0)}</b></div>
    </div>
    """, unsafe_allow_html=True)

    safe_name = pipeline_result['topic'][:40].strip().replace(' ', '_') or "report"

    # ---- generate PDF once, reuse for both download + email ----
    try:
        pdf_bytes = report_to_pdf(synthesis["report"], pipeline_result["topic"])
    except Exception as e:
        pdf_bytes = None
        st.caption(f"PDF export unavailable right now: {e}")

    st.write("")
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "Download .md",
            data=synthesis["report"],
            file_name=f"{safe_name}_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with dl_col2:
        if pdf_bytes:
            st.download_button(
                "Download .pdf",
                data=pdf_bytes,
                file_name=f"{safe_name}_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    with st.expander("Email this report"):
        email_col1, email_col2 = st.columns([3, 1])
        with email_col1:
            recipient = st.text_input(
                "recipient",
                placeholder="name@example.com",
                label_visibility="collapsed",
                key="email_recipient",
            )
        with email_col2:
            send_clicked = st.button("Send", use_container_width=True, key="send_email_btn")

        if send_clicked:
            ok, message = send_email_report(
                to_email=recipient.strip(),
                subject=f"Research report: {pipeline_result['topic']}",
                body_text=synthesis["report"],
                attachment_bytes=pdf_bytes,
                attachment_name=f"{safe_name}_report.pdf",
            )
            if ok:
                st.success(message)
            else:
                st.error(message)

    with st.expander("Sources"):
        for url, title in pipeline_result["sources"]:
            st.markdown(f"- [{title or url}]({url})")
