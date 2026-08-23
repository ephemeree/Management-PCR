import os
import logging
from concurrent.futures import ThreadPoolExecutor
from flask import current_app
from flask_mail import Message

logger = logging.getLogger(__name__)

# Single thread pool for asynchronous background email dispatch
_email_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="flask_mail_worker")


def get_mail_config():
    """Reads Flask-Mail configuration from environment variables."""
    host = os.getenv('MAIL_SERVER') or os.getenv('SMTP_HOST') or ''
    port_str = os.getenv('MAIL_PORT') or os.getenv('SMTP_PORT') or '587'
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    user = os.getenv('MAIL_USERNAME') or os.getenv('SMTP_USER') or ''
    password = os.getenv('MAIL_PASSWORD') or os.getenv('SMTP_PASSWORD') or ''
    
    use_tls_env = os.getenv('MAIL_USE_TLS') or os.getenv('SMTP_USE_TLS') or 'true'
    use_tls = use_tls_env.lower() in ('1', 'true', 'yes')

    use_ssl_env = os.getenv('MAIL_USE_SSL') or os.getenv('SMTP_USE_SSL') or 'false'
    use_ssl = use_ssl_env.lower() in ('1', 'true', 'yes') or (port == 465)

    default_sender = os.getenv('MAIL_DEFAULT_SENDER', 'D-IPCR System <no-reply@cict.edu.ph>')
    suppress_send = (os.getenv('MAIL_SUPPRESS_SEND') or 'false').lower() in ('1', 'true', 'yes')

    return {
        'host': host.strip(),
        'port': port,
        'user': user.strip(),
        'password': password,
        'use_tls': use_tls,
        'use_ssl': use_ssl,
        'default_sender': default_sender,
        'suppress_send': suppress_send
    }


def _send_email_sync(subject: str, recipients: list[str], html_body: str, text_body: str = "", sender: str = None) -> tuple[bool, str]:
    """
    Synchronously sends an email using Flask-Mail.
    If mail server is not configured or in development mode, logs the email output.
    """
    if not recipients:
        return False, "No recipient email addresses provided."

    cfg = get_mail_config()
    sender = sender or cfg['default_sender']

    valid_recipients = [r.strip() for r in recipients if r and r.strip()]
    if not valid_recipients:
        return False, "No valid recipient email addresses found."

    # If no mail server is configured or sending is suppressed, log and succeed gracefully
    if not cfg['host'] or cfg['suppress_send']:
        logger.info(
            f"[FLASK-MAIL DEV LOG] Email would be sent:\n"
            f"  From: {sender}\n"
            f"  To: {', '.join(valid_recipients)}\n"
            f"  Subject: {subject}\n"
            f"  (MAIL_SERVER not set or MAIL_SUPPRESS_SEND=true — logged to console)"
        )
        return True, "DEV_LOGGED"

    try:
        from app import app, mail
        with app.app_context():
            msg = Message(
                subject=subject,
                recipients=valid_recipients,
                body=text_body if text_body else None,
                html=html_body if html_body else None,
                sender=sender
            )
            mail.send(msg)

        logger.info(f"[FLASK-MAIL SUCCESS] Email sent to {valid_recipients} with Subject: '{subject}'")
        print(f"[FLASK-MAIL SUCCESS] Email sent to {valid_recipients} with Subject: '{subject}'", flush=True)
        return True, "SENT"

    except Exception as e:
        error_msg = f"Failed to send email via Flask-Mail to {valid_recipients}: {str(e)}"
        logger.error(f"[FLASK-MAIL ERROR] {error_msg}")
        print(f"[FLASK-MAIL ERROR] {error_msg}", flush=True)
        return False, error_msg


def send_async_email(subject: str, recipients: list[str], html_body: str, text_body: str = "", sender: str = None, on_complete=None):
    """
    Submits email sending task to background thread pool.
    Non-blocking, returns immediately so web requests are never held up.
    """
    def _task():
        success, message = _send_email_sync(subject, recipients, html_body, text_body, sender)
        if on_complete and callable(on_complete):
            try:
                on_complete(success, message, recipients)
            except Exception as cb_err:
                logger.error(f"Error in mail callback: {cb_err}")

    _email_executor.submit(_task)
