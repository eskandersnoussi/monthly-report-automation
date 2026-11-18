"""Optional: email the finished report (any SMTP server, e.g. Outlook / Microsoft 365 or Gmail)."""
from __future__ import annotations

import mimetypes
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


def settings_from_env() -> dict:
    keys = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "REPORT_FROM", "REPORT_TO"]
    values = {k: os.environ.get(k, "") for k in keys}
    missing = [k for k in ("SMTP_HOST", "REPORT_TO") if not values[k]]
    if missing:
        raise ValueError("Missing email settings: " + ", ".join(missing))
    values["SMTP_PORT"] = int(values["SMTP_PORT"] or 587)
    values["REPORT_FROM"] = values["REPORT_FROM"] or values["SMTP_USER"]
    return values


def build_message(subject: str, body: str, sender: str, recipients: list,
                  attachments: Iterable[Path]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, sender, ", ".join(recipients)
    msg.set_content(body)
    for path in attachments:
        ctype, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        msg.add_attachment(Path(path).read_bytes(), maintype=maintype, subtype=subtype,
                           filename=Path(path).name)
    return msg


def send_report(subject: str, body: str, attachments: Iterable[Path],
                settings: dict, smtp_class=smtplib.SMTP) -> None:
    recipients = [r.strip() for r in settings["REPORT_TO"].split(",") if r.strip()]
    msg = build_message(subject, body, settings["REPORT_FROM"], recipients, attachments)
    with smtp_class(settings["SMTP_HOST"], settings["SMTP_PORT"], timeout=30) as smtp:
        smtp.starttls()
        if settings["SMTP_USER"]:
            smtp.login(settings["SMTP_USER"], settings["SMTP_PASSWORD"])
        smtp.send_message(msg)
