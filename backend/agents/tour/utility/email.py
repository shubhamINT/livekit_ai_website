import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

async def send_email(to: str, subject: str, html_body: str):
    """
    Sends an HTML email using SMTP configuration from environment variables.
    """
    smtp_host = os.getenv("SMTP_HOST","smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.error("SMTP configuration is incomplete. Check environment variables.")
        raise ValueError("SMTP configuration missing.")

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to

    # Attach HTML body
    part = MIMEText(html_body, "html")
    msg.attach(part)

    try:
        # SMTP connection
        # Using simple smtplib for now. 
        # Note: In a production async environment, consider using aio-smtp-client
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()  # Secure the connection
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, to, msg.as_string())
        
        logger.info(f"Email sent successfully to {to}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {str(e)}")
        raise e
