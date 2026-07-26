# research_agent/config.py
import os, warnings
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv()

# TRY STREAMLIT SECRETS FIRST (CLOUD), FALL BACK TO .env (local)
try:
    import streamlit as st
    GROQ_API_KEY   = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
    TAVILY_API_KEY = st.secrets.get("TAVILY_API_KEY", os.getenv("TAVILY_API_KEY", ""))
except Exception:
    GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

LLM_MODEL_FAST   = "llama-3.1-8b-instant"
LLM_MODEL_STRONG = "llama-3.3-70b-versatile"

MIN_RELEVANCE_SCORE = 0.6
OUTPUT_DIR          = "./output"

DEPTH_CONFIGS = {
    "Quick":    {"queries": 3, "results_per_query": 3, "chunks": 6},
    "Standard": {"queries": 5, "results_per_query": 5, "chunks": 12},
    "Deep":     {"queries": 8, "results_per_query": 8, "chunks": 20},
}

if TAVILY_API_KEY:
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

# ---- Email (SMTP) — works with Gmail, Outlook/Office365, or any provider ----
# Gmail:   SMTP_HOST=smtp.gmail.com      SMTP_PORT=587  (use a 16-char App Password, not your login password)
# Outlook: SMTP_HOST=smtp.office365.com  SMTP_PORT=587
# Other:   ask your provider for their SMTP host + port (587 with STARTTLS is standard)
try:
    SMTP_HOST     = st.secrets.get("SMTP_HOST", os.getenv("SMTP_HOST", ""))
    SMTP_PORT     = int(st.secrets.get("SMTP_PORT", os.getenv("SMTP_PORT", "587")))
    SMTP_USER     = st.secrets.get("SMTP_USER", os.getenv("SMTP_USER", ""))
    SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
except Exception:
    SMTP_HOST     = os.getenv("SMTP_HOST", "")
    SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER     = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

os.makedirs(OUTPUT_DIR, exist_ok=True)