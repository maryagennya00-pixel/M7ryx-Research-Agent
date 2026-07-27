# research_agent/utils.py
import os, re, time, smtplib, warnings
from email.message import EmailMessage
warnings.filterwarnings("ignore")

from langchain_groq import ChatGroq
from config import (
    LLM_MODEL_FAST, LLM_MODEL_STRONG, GROQ_API_KEY,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
)

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
    can wrap them — otherwise a single 'word' wider than the page crashes
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
    Returns raw PDF bytes, ready for a download button or email attachment.
    """
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    for raw_line in report_text.split("\n"):
        line = _pdf_safe(raw_line.rstrip())

        if not line.strip():
            pdf.ln(3)
            continue

        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(0, 9, line[2:].strip())
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(0, 8, line[3:].strip())
            pdf.ln(1)
        elif line.startswith(("- ", "* ")):
            pdf.set_font("Helvetica", "", 10.5)
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line[2:].strip())
            pdf.multi_cell(0, 6, f"-  {clean}")
        elif re.match(r"^\d+\.\s", line):
            pdf.set_font("Helvetica", "", 10.5)
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            pdf.multi_cell(0, 6, clean)
        else:
            pdf.set_font("Helvetica", "", 10.5)
            clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            pdf.multi_cell(0, 6, clean)

    return bytes(pdf.output())


def send_email_report(to_email: str, subject: str, body_text: str,
                       attachment_bytes: bytes = None,
                       attachment_name: str = "report.pdf") -> tuple:
    """
    Sends the report by email over SMTP with STARTTLS.
    Works with Gmail, Outlook/Office365, or any standard SMTP provider —
    just set SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD in .env.
    Returns (success: bool, message: str) — never raises, so a bad email
    config can't crash the app; it just reports the problem back to the UI.
    """
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        return False, "Email isn't configured yet — add SMTP_HOST, SMTP_USER and SMTP_PASSWORD to your .env."

    if not to_email or "@" not in to_email:
        return False, "That doesn't look like a valid email address."

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = to_email
        msg.set_content(body_text)

        if attachment_bytes:
            msg.add_attachment(
                attachment_bytes,
                maintype="application",
                subtype="pdf",
                filename=attachment_name,
            )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        return True, f"Report sent to {to_email}."
    except Exception as e:
        return False, f"Couldn't send the email: {e}"

