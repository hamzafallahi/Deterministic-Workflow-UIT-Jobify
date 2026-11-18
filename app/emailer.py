"""SMTP delivery for generated applications."""

import smtplib
from email.message import EmailMessage
from pathlib import Path


class EmailError(RuntimeError):
    """Raised when SMTP delivery fails."""


def send_application(
    smtp_host: str,
    smtp_port: int,
    sender: str,
    password: str,
    recipient: str,
    subject: str,
    cover_letter: str,
    pdf_path: Path,
) -> None:
    if not sender or not password:
        raise ValueError("USER_EMAIL and EMAIL_APP_PASSWORD are required")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(cover_letter)
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(message)
    except smtplib.SMTPException as exc:
        raise EmailError(f"SMTP delivery failed: {exc}") from exc
