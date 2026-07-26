# research_agent/email_sender.py
# Send research report via email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from config import EMAIL_ADDRESS, EMAIL_APP_PASSWORD


def send_report_email(
    recipient_email: str,
    recipient_name: str,
    topic: str,
    report_md: str,
    pdf_bytes: bytes = None,
) -> dict:
    """
    Send research report via email with optional PDF attachment.
    Uses Gmail SMTP - requires an App Password (not your regular Gmail password).
    Returns: {"success": bool, "message": str}
    """
    sender   = EMAIL_ADDRESS
    password = EMAIL_APP_PASSWORD

    if not sender or not password:
        return {
            "success": False,
            "message": "Email credentials not configured. Add EMAIL_ADDRESS and EMAIL_APP_PASSWORD to your .env."
        }

    if not recipient_email or "@" not in recipient_email:
        return {
            "success": False,
            "message": "That doesn't look like a valid email address."
        }

    # Build email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Research Report: {topic}"
    msg["From"]    = f"M7RYX Research Agent <{sender}>"
    msg["To"]      = recipient_email

    generated_at = datetime.now().strftime('%B %d, %Y at %H:%M')

    # Plain text version
    plain_text = f"""Hi {recipient_name},

Your research report on "{topic}" is ready.

{report_md[:500]}...

[Full report attached as PDF]

Best regards,
M7RYX Research Agent
Generated: {generated_at}"""

    # HTML version
    preview = report_md[:400].replace(chr(10), '<br>')
    html_body = f"""
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<div style="background: #1f3864; padding: 20px; border-radius: 8px 8px 0 0;">
    <h2 style="color: white; margin: 0;">M7RYX Research Agent</h2>
    <p style="color: #aac4ff; margin: 5px 0 0 0;">Research Report Ready</p>
</div>
<div style="background: #f8f9ff; padding: 25px; border: 1px solid #e0e4ff;">
    <p>Hi <strong>{recipient_name}</strong>,</p>
    <p>Your research report on <strong>"{topic}"</strong> has been generated.</p>
    <div style="background: white; border-left: 4px solid #667eea;
                padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0;">
        <h3 style="color: #1f3864; margin-top: 0;">Report Preview</h3>
        <p style="color: #555; font-size: 14px;">
            {preview}...
        </p>
    </div>
    <p style="color: #888; font-size: 12px;">
        Generated: {generated_at}
    </p>
</div>
<div style="background: #1f3864; padding: 12px; text-align: center;
            border-radius: 0 0 8px 8px;">
    <p style="color: #aac4ff; font-size: 11px; margin: 0;">
        M7RYX | Powered by Agentic AI
    </p>
</div>
</body></html>"""

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Attach PDF if provided
    if pdf_bytes:
        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(pdf_bytes)
        encoders.encode_base64(attachment)

        safe_topic = topic[:30].replace(" ", "_")
        attachment.add_header(
            "Content-Disposition",
            f"attachment; filename=research_{safe_topic}.pdf"
        )
        msg.attach(attachment)

    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient_email, msg.as_string())
        return {
            "success": True,
            "message": f"Report sent to {recipient_email}."
        }
    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "message": "Authentication failed. Use an App Password from Google Account -> Security -> 2-Step Verification -> App Passwords."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Email failed: {str(e)}"
        }