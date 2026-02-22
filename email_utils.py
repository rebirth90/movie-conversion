
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import List, Optional
from config import AppConfig

logger = logging.getLogger(__name__)

def send_failure_email(config: AppConfig, subject: str, body: str, attachment_paths: Optional[List[Path]] = None) -> bool:
    """
    Send an email notification via SMTP with optional file attachments.
    
    Args:
        subject (str): The email subject line.
        body (str): The email body text.
        attachment_paths (Optional[List[Path]]): List of file paths to attach (e.g. logs).
        
    Returns:
        bool: True if sent successfully, False otherwise.
        
    Behavior:
        - Skips sending if SMTP config is missing/empty.
        - Tries to attach files; logs error but continues if an attachment fails.
        - Supports both STARTTLS (port 587) and standard SSL (usually 465, but configurable).
    """
    if not config.email_smtp_host:
        logger.warning("Email configuration missing, skipping notification.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = config.email_smtp_username
        msg['To'] = config.email_recipient
        msg['Subject'] = f"[MovieConversion] FAILURE: {subject}"

        msg.attach(MIMEText(body, 'plain'))

        if attachment_paths:
            for path in attachment_paths:
                if path and path.exists():
                    try:
                        with open(path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=path.name)
                        part['Content-Disposition'] = f'attachment; filename="{path.name}"'
                        msg.attach(part)
                    except Exception as e:
                        logger.error(f"Failed to attach file {path}: {e}")

        # Connect to SMTP Server
        if config.email_smtp_ssl:
            server = smtplib.SMTP_SSL(config.email_smtp_host, config.email_smtp_port)
        else:
            server = smtplib.SMTP(config.email_smtp_host, config.email_smtp_port)
            server.starttls() # Upgrade connection to secure

        server.login(config.email_smtp_username, config.email_smtp_password)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Failure notification sent to {config.email_recipient}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
