"""
Simple email service using local SMTP (Postfix/sendmail).
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@niftystrategist.com")


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Send a password reset email. Returns True on success."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "NiftyStrategist - Password Reset"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    text_body = f"""Hi,

You requested a password reset for your NiftyStrategist account.

Click the link below to reset your password:
{reset_url}

This link expires in 1 hour. If you didn't request this, you can safely ignore this email.

— NiftyStrategist"""

    html_body = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; color: #333;">
  <h2 style="color: #2563eb;">Password Reset</h2>
  <p>You requested a password reset for your NiftyStrategist account.</p>
  <p>
    <a href="{reset_url}"
       style="display: inline-block; padding: 12px 24px; background: #2563eb; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
      Reset Password
    </a>
  </p>
  <p style="font-size: 13px; color: #666;">This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p style="font-size: 12px; color: #999;">NiftyStrategist — AI Trading Assistant</p>
</body>
</html>"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.send_message(msg)
        logger.info(f"[Email] Password reset email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[Email] Failed to send reset email to {to_email}: {e}")
        return False
