#!/usr/bin/env python3
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def load_dotenv(filepath=".env"):
    """
    Manually load environment variables from a .env file if it exists.
    """
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

def main():
    if len(sys.argv) < 3:
        print("Usage: ./send_notification.py <subject> <body>")
        sys.exit(1)

    subject = sys.argv[1]
    body = sys.argv[2]

    # Load environment variables
    load_dotenv()

    sandbox_mode = os.environ.get("SANDBOX", "false").lower() in ("true", "1", "yes")

    # If in sandbox mode, log email locally and exit successfully
    if sandbox_mode:
        log_file = "sandbox_emails.log"
        email_content = f"""
========================================
[SANDBOX EMAIL]
Subject: {subject}
To: {os.environ.get("RECIPIENT_EMAIL", "sandbox@portraitron.local")}
From: {os.environ.get("SENDER_EMAIL", "agent@portraitron.local")}
----------------------------------------
{body}
========================================
"""
        print(email_content)
        try:
            with open(log_file, "a") as f:
                f.write(email_content)
            print(f"Logged email locally to {log_file} (Sandbox Mode).")
            sys.exit(0)
        except Exception as e:
            print(f"Failed to write to sandbox log: {e}")
            sys.exit(1)

    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")  # Gmail App Password
    recipient_email = os.environ.get("RECIPIENT_EMAIL")

    if not sender_email or not sender_password or not recipient_email:
        print("Error: SENDER_EMAIL, SENDER_PASSWORD, and RECIPIENT_EMAIL must be configured in environment or .env file, or SANDBOX=True must be set.")
        sys.exit(1)

    # Create message
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        # Connect and send
        print(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.close()
        print("Email notification sent successfully.")
    except Exception as e:
        print(f"Failed to send email notification: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
