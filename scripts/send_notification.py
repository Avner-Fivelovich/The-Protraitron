#!/usr/bin/env python3
import os
import sys
import smtplib
import yaml
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

def load_config(config_path="config/server.yaml"):
    """
    Load configuration from YAML file.
    """
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

def main():
    if len(sys.argv) < 3:
        print("Usage: ./send_notification.py <subject> <body>")
        sys.exit(1)

    subject = sys.argv[1]
    body = sys.argv[2]

    # Load environment variables
    load_dotenv()
    
    # Load YAML configuration
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    config_path = os.path.join(project_root, "config", "server.yaml")
    config = load_config(config_path).get("notifications", {})

    sandbox_mode = config.get("sandbox_mode", os.environ.get("SANDBOX", "false").lower() in ("true", "1", "yes"))

    # If in sandbox mode, log email locally and exit successfully
    if sandbox_mode:
        log_file = config.get("sandbox_log_file", "sandbox_emails.log")
        recipient = config.get("recipient_email", os.environ.get("RECIPIENT_EMAIL", "sandbox@portraitron.local"))
        sender = config.get("sender_email", os.environ.get("SENDER_EMAIL", "agent@portraitron.local"))
        email_content = f"""
========================================
[SANDBOX EMAIL]
Subject: {subject}
To: {recipient}
From: {sender}
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

    smtp_server = config.get("smtp_server", os.environ.get("SMTP_SERVER", "smtp.gmail.com"))
    smtp_port = int(config.get("smtp_port", os.environ.get("SMTP_PORT", 587)))
    sender_email = config.get("sender_email", os.environ.get("SENDER_EMAIL"))
    sender_password = config.get("sender_password", os.environ.get("SENDER_PASSWORD"))  # Gmail App Password
    recipient_email = config.get("recipient_email", os.environ.get("RECIPIENT_EMAIL"))

    if not sender_email or not sender_password or not recipient_email:
        print("Error: sender_email, sender_password, and recipient_email must be configured in YAML config, environment, or .env file, or sandbox_mode=True must be set.")
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
