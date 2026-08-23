<!-- documentation_hub_data: {"title": "Send Notification Script", "type": "script-doc", "repository": "The-Portraitron-AI-agent"} -->
<style>
  h1, h2, h3, h4, h5, h6 {
    font-family: 'Space Grotesk', sans-serif;
    text-transform: uppercase;
  }
  h1, h2 {
    border-bottom: 2px solid #4a148c;
  }
  h3 {
    border-left: 4px solid #26a69a;
    padding-left: 8px;
  }
  body, p, li, td {
    font-family: 'Inter', sans-serif;
  }
  pre, code {
    font-family: 'JetBrains Mono', monospace;
    background-color: #0f0f10;
    color: #f8f8f2;
    padding: 2px 4px;
    border-radius: 4px;
  }
  pre {
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
  }
  pre code {
    padding: 0;
  }
</style>

# SEND NOTIFICATION SCRIPT (`scripts/send_notification.py`)

## PURPOSE

The `send_notification.py` script is a standalone Python utility designed to dispatch plain-text email notifications. Within the **Portraitron 3000** robotic sketching ecosystem, it is used by background workers, pipeline managers, and automated tasks to alert operators and administrators regarding job completions, system faults, or hardware status updates.

To support offline testing and local development without sending real emails or requiring live SMTP credentials, the script features a built-in **Sandbox Mode** that intercepts emails and logs them locally to a file.

---

## HOW TO USE IT

The script is executed via the command line and accepts two mandatory positional arguments: **Subject** and **Body**.

### Basic Usage

```bash
python scripts/send_notification.py "Job Complete" "The rendering job has finished successfully."
```

Or make the script executable directly:

```bash
./scripts/send_notification.py "Plotting Error" "Robotic arm encountered a protective stop at P1."
```

### Return Codes

| Return Code | Meaning |
| :--- | :--- |
| `0` | **Success**: Email was successfully transmitted over SMTP, or successfully written to the sandbox log. |
| `1` | **Failure**: Missing positional arguments, unconfigured credentials in live mode, invalid SMTP host/port, authentication failure, or filesystem write error. |

---

## CONFIGURATION

The script loads configuration from two sources with a clear precedence hierarchy:

1. **YAML Configuration** (`config/server.yaml` under the `notifications` key)
2. **Environment Variables** (Loaded from `.env` in the working directory, or inherited from the operating system shell)
3. **Built-in Defaults**

```
Priority: config/server.yaml (notifications section) > Environment Variables / .env > Fallback Defaults
```

### 1. YAML Configuration (`config/server.yaml`)

You can define notification parameters in `config/server.yaml`:

```yaml
notifications:
  sandbox_mode: false
  sandbox_log_file: "sandbox_emails.log"
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "your-bot@gmail.com"
  sender_password: "your-app-password"
  recipient_email: "operator@domain.com"
```

### 2. Environment Variables & `.env`

Alternatively, create a `.env` file in your execution directory or export variables in your shell environment:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `SANDBOX` | `bool` (`true`, `1`, `yes`) | `false` | Enables sandbox mode to log emails locally without connecting to an SMTP server. |
| `SMTP_SERVER` | `str` | `smtp.gmail.com` | Hostname of the outgoing SMTP mail server. |
| `SMTP_PORT` | `int` | `587` | Port for SMTP TLS connection (typically `587`). |
| `SENDER_EMAIL` | `str` | `agent@portraitron.local` (Sandbox) | The sender email address. Required for live SMTP transmission. |
| `SENDER_PASSWORD` | `str` | `None` | SMTP password or Gmail App Password. Required for live SMTP transmission. |
| `RECIPIENT_EMAIL` | `str` | `sandbox@portraitron.local` (Sandbox) | The destination email address. Required for live SMTP transmission. |

---

## SANDBOX MODE

When testing or running in an environment without internet access or valid SMTP credentials, activate Sandbox Mode by either:

- Setting `sandbox_mode: true` in `config/server.yaml`, or
- Setting `SANDBOX=true` in `.env` / shell environment.

### Sandbox Behavior:
1. Skips all network and SMTP connections.
2. Formats the email with headers (`Subject`, `To`, `From`) and body content.
3. Prints the structured notification block directly to standard output (`stdout`).
4. Appends the notification block to the configured log file (default: `sandbox_emails.log`).
5. Exits cleanly with status code `0`.

**Sample Sandbox Output:**
```text
========================================
[SANDBOX EMAIL]
Subject: Job Complete
To: sandbox@portraitron.local
From: agent@portraitron.local
----------------------------------------
The rendering job has finished successfully.
========================================

Logged email locally to sandbox_emails.log (Sandbox Mode).
```

---

## INNER WORKINGS

The execution pipeline of `send_notification.py` proceeds as follows:

```
[CLI Invocation]
       │
       ▼
1. Validate CLI Arguments (sys.argv: <subject> <body>)
       │
       ▼
2. Load .env Variables via custom load_dotenv()
       │
       ▼
3. Load config/server.yaml (notifications section)
       │
       ▼
4. Check Sandbox Mode?
      ├── YES ──► Write to sandbox_emails.log & Print to stdout ──► Exit (0)
      │
      └── NO
           │
           ▼
5. Validate SMTP Credentials (sender_email, sender_password, recipient_email)
       │ (Missing credentials: Error & Exit 1)
       ▼
6. Construct MIME Message (MIMEMultipart & MIMEText)
       │
       ▼
7. Connect to SMTP Server (smtplib.SMTP + starttls())
       │
       ▼
8. Authenticate & Dispatch (server.login() & server.sendmail())
       │
       ▼
9. Close Connection & Exit (0)
```

1. **Argument Validation**: Ensures that exactly two command line arguments (`subject` and `body`) are supplied. If fewer are provided, prints usage instructions and exits with code `1`.
2. **Environment Loading**: Reads key-value pairs from `.env` via `load_dotenv()`, ignoring comments and empty lines, and populates `os.environ`.
3. **YAML Configuration Resolution**: Locates the project root relative to the script path (`os.path.dirname(os.path.abspath(__file__))`), opens `config/server.yaml`, and parses the `notifications` configuration block using `yaml.safe_load`.
4. **Sandbox Evaluation**: Evaluates `sandbox_mode` against the YAML config and `SANDBOX` environment variable. If active, formats the email, writes it to `sandbox_log_file` (default `sandbox_emails.log`), prints it to the console, and exits with `0`.
5. **Credential & Host Validation**: In live mode, verifies that `sender_email`, `sender_password`, and `recipient_email` are present. If any are missing, prints an informative error and exits with `1`.
6. **MIME Message Construction**: Constructs a multipart message container (`MIMEMultipart`) containing standard MIME email headers (`From`, `To`, `Subject`) and attaches the plain-text body (`MIMEText(body, "plain")`).
7. **SMTP Transmission & Security**: Connects to the configured `smtp_server` on `smtp_port`, initiates explicit TLS encryption via `server.starttls()`, logs in with `sender_email` and `sender_password`, dispatches the message via `server.sendmail()`, and terminates the session with `server.close()`.
8. **Exception Handling**: Wraps the network transmission in a `try...except` block, logging any connection timeouts, DNS resolution failures, or SMTP authentication rejections before exiting with code `1`.

