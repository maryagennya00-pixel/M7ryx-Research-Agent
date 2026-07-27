# research_agent/utils.py
import os, re, time, smtplib, warnings, textwrap
from email.message import EmailMessage
warnings.filterwarnings("ignore")

from langchain_groq import ChatGroq
from config import (
    LLM_MODEL_FAST, LLM_MODEL_STRONG, GROQ_API_KEY,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
)

# --------------------------------------------------------------------------
# Fallback: if config.py didn't pick up Streamlit Cloud secrets correctly
# (common cause of "Name or service not known" - SMTP_HOST arriving empty),
# try reading st.secrets directly as a backup source.
# --------------------------------------------------------------------------
def _resolve_smtp_settings():
    host, port, user, password = SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
    if not host or not user or not password:
        try:
            import streamlit as st
            host     = host     or st.secrets.get("SMTP_HOST")
            user     = user     or st.secrets.get("SMTP_USER")
            password = password or st.secrets.get("SMTP_PASSWORD")
            port     = port     or st.secrets.get("SMTP_PORT", 587)
        except Exception:
            pass
    if not port:
        port = 587
    return host, int(port), user, password


if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = GROQ_API_KEY

llm_fast   = ChatGroq(model=LLM_MODEL_FAST)
llm_strong = ChatGroq(model=LLM_MODEL_STRONG)


def safe_invoke(llm, prompt: str, max_retries: int = 3,
                wait_seconds: int = 60, progress_callback=None) -> str:
    """
    Calls llm.invoke(prompt) with automatic retry.
    On rate limits, waits `wait_seconds` before retrying.
    If progress_callback is given, shows a calm, user-facing status
    instead of raw error text - never exposes "failed" language to the UI.
    """
    def update(msg):
        if progress_callback:
            progress_callback(msg)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return llm.invoke(prompt).content
        except Exception as e:
            last_error = e
            msg = str(e).lower()
            is_rate_limit = any(kw in msg for kw in
                                ["rate limit", "429", "quota", "too many requests"])
            if is_rate_limit and attempt < max_retries:
                update("Working on it, just a moment...")
                print(f"[internal] rate limit, attempt {attempt}/{max_retries}, "
                      f"waiting {wait_seconds}s")
                time.sleep(wait_seconds)
                continue
            elif attempt < max_retries:
                update("Working on it, just a moment...")
                print(f"[internal] transient error: {e}, retrying")
                time.sleep(5)
                continue
            else:
                raise last_error
    raise last_error


def _break_long_tokens(text: str, max_len: int = 45) -> str:
    """Insert soft breaks into long unbroken strings (like URLs) so fpdf2
    can wrap them - otherwise a single 'word' wider than the page crashes
    multi_cell with 'Not enough horizontal space to render a single character'."""
    def _break(match):
        word = match.group(0)
        return " ".join(word[i:i+max_len] for i in range(0, len(word), max_len))
    return re.sub(r"\S{" + str(max_len) + r",}", _break, text)


def _pdf_safe(text: str) -> str:
    """Core PDF fonts only support Latin-1. Swap common problem characters
    instead of crashing, and drop anything else that can't be encoded."""
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2022": "-",
        "\u2192": "->", "\u2705": "", "\u2b50": "",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    text = text.encode("latin-1", "replace").decode("latin-1")
    return _break_long_tokens(text)


def report_to_pdf(report_text: str, topic: str = "Research Report") -> bytes:
    """
    Convert the markdown-style report text into a simple, clean PDF.
    Uses fpdf2 (pure Python, no system dependencies) so it can't take
    down the app the way heavier PDF/HTML renderers sometimes do.
    Every write is wrapped so a single bad line can never crash the export -
    worst case it gets hard-wrapped or replaced with a placeholder.
    Returns raw PDF bytes, ready for a download button or email attachment.
    """
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    def _write(text: str, size: float, bold: bool, line_h: float):
        pdf.set_font("Helvetica", "B" if bold else "", size)
        try:
            pdf.multi_cell(0, line_h, text)
        except Exception:
            safe_text = "\n".join(textwrap.wrap(text, width=30)) or "-"
            try:
                pdf.multi_cell(0, line_h, safe_text)
            except Exception:
                pdf.multi_cell(0, line_h, "[content omitted - formatting error]")

    for raw_line in report_text.split("\n"):
        line = _pdf_safe(raw_line.rstrip())

        if not line.strip():
            pdf.ln(3)
            continue

        if line.startswith("# "):
            _write(line[2:].strip(), 18, True, 9)
            pdf.ln(2)
        elif line.startswith("## "):
            _write(line[3:].strip(), 13, True, 8)
            pdf.ln(1)
        elif line.startswith(("- ", "* ")):
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line[2:].strip())
            _write(f"-  {clean}", 10.5, False, 6)
        elif re.match(r"^\d+\.\s", line):
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            _write(clean, 10.5, False, 6)
        else:
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            _write(clean, 10.5, False, 6)

    return bytes(pdf.output())


def send_email_report(to_email: str, subject: str, body_text: str,
                       attachment_bytes: bytes = None,
                       attachment_name: str = "report.pdf") -> tuple:
    """
    Sends the report by email over SMTP with STARTTLS.
    Works with Gmail, Outlook/Office365, or any standard SMTP provider -
    just set SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD in .env
    or Streamlit Cloud secrets.
    Returns (success: bool, message: str) - never raises, so a bad email
    config can't crash the app; it just reports the problem back to the UI.
    """
    host, port, user, password = _resolve_smtp_settings()

    if not host or not user or not password:
        return False, "Email isn't configured yet — add SMTP_HOST, SMTP_USER and SMTP_PASSWORD to your secrets."

    if not to_email or "@" not in to_email:
        return False, "That doesn't look like a valid email address."

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"]    = user
        msg["To"]      = to_email
        msg.set_content(body_text)

        if attachment_bytes:
            msg.add_attachment(
                attachment_bytes,
                maintype="application",
                subtype="pdf",
                filename=attachment_name,
            )

        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        return True, f"Report sent to {to_email}."
    except Exception as e:
        return False, f"Couldn't send the email: {e}"