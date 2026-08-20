<!-- documentation_hub_data: {"title": "Send Notification Script", "type": "script-doc", "repository": "The-Portraitron-AI-agent"} -->
<div style="font-family: 'Inter', sans-serif;">

<h1 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 2px solid #4a148c; padding-bottom: 8px;">Send Notification Script Documentation</h1>

<p><strong>Script Path:</strong> <code style="font-family: 'JetBrains Mono', monospace; background-color: #0f0f10; color: #fff; padding: 2px 6px; border-radius: 4px;">scripts/send_notification.py</code></p>

<h2 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 1px solid #26a69a; padding-bottom: 6px;">1. Purpose</h2>
<p>
The <code>send_notification.py</code> script is a standalone Python utility designed to send simple plaintext email notifications. It is primarily used within the Portraitron ecosystem for alerting users or system administrators about job completions, errors, or automated tasks. To facilitate development and testing without spamming actual email accounts, the script includes a built-in sandbox mode that logs emails locally instead of transmitting them over SMTP.
</p>

<h2 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 1px solid #26a69a; padding-bottom: 6px;">2. How to Use</h2>
<p>
The script is executed via the command line and requires two positional arguments: the <strong>subject</strong> and the <strong>body</strong> of the email.
</p>

<pre style="font-family: 'JetBrains Mono', monospace; background-color: #0f0f10; color: #fff; padding: 12px; border-radius: 6px;"><code>./send_notification.py "Job Complete" "The rendering job has finished successfully."</code></pre>

<p><strong>Return Codes:</strong></p>
<ul>
    <li><code>0</code>: Email sent successfully, or successfully logged in Sandbox mode.</li>
    <li><code>1</code>: Missing arguments, missing configuration, or SMTP transmission failure.</li>
</ul>

<h2 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 1px solid #26a69a; padding-bottom: 6px;">3. Configuration Files & Environment Variables</h2>
<p>
The script automatically interacts with a <code style="font-family: 'JetBrains Mono', monospace; background-color: #0f0f10; color: #fff; padding: 2px 6px; border-radius: 4px;">.env</code> file located in the directory from which the script is executed. It relies on the following environment variables (which can be passed directly via the environment or defined in the <code>.env</code> file):
</p>

<ul>
    <li><strong><code>SANDBOX</code></strong>: Set to <code>true</code>, <code>1</code>, or <code>yes</code> to enable sandbox mode. Emails will be logged locally to <code>sandbox_emails.log</code> instead of being sent.</li>
    <li><strong><code>SMTP_SERVER</code></strong>: The SMTP server address (defaults to <code>smtp.gmail.com</code>).</li>
    <li><strong><code>SMTP_PORT</code></strong>: The SMTP port (defaults to <code>587</code>).</li>
    <li><strong><code>SENDER_EMAIL</code></strong>: The email address sending the notification (Required unless in Sandbox).</li>
    <li><strong><code>SENDER_PASSWORD</code></strong>: The application password or SMTP password for the sender account (Required unless in Sandbox).</li>
    <li><strong><code>RECIPIENT_EMAIL</code></strong>: The destination email address (Required unless in Sandbox).</li>
</ul>

<h2 style="font-family: 'Space Grotesk', sans-serif; text-transform: uppercase; border-bottom: 1px solid #26a69a; padding-bottom: 6px;">4. Inner Workings</h2>
<p>
The internal flow of the script operates as follows:
</p>
<ol>
    <li><strong>Argument Parsing:</strong> Validates that exactly two arguments (subject and body) have been provided using <code>sys.argv</code>. Exits with a usage prompt if they are missing.</li>
    <li><strong>Environment Loading:</strong> Invokes a custom <code>load_dotenv()</code> function to parse the local <code>.env</code> file manually. It ignores comments and empty lines, injecting valid key-value pairs into <code>os.environ</code>.</li>
    <li><strong>Sandbox Check:</strong> Checks the boolean state of the <code>SANDBOX</code> variable. If active, it bypasses SMTP completely, formats the email contents into a text block, appends it to <code>sandbox_emails.log</code>, and exits successfully.</li>
    <li><strong>SMTP Transmission:</strong> If sandbox mode is disabled, it constructs a MIME text message using <code>email.mime.text.MIMEText</code> and <code>MIMEMultipart</code>. It connects to the configured SMTP server over TLS (<code>server.starttls()</code>), authenticates using the provided credentials, dispatches the message, and cleanly closes the connection.</li>
</ol>

</div>
