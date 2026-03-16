"""Email sender — sends Banana TXT + CSV as attachments via SMTP."""
from __future__ import annotations
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import pandas as pd

from app.services.export import df_to_banana_tsv, df_to_csv


def _load_smtp_config() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": int(os.environ.get("SMTP_PORT", "465")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_email": os.environ.get("FROM_EMAIL", ""),
    }


def is_email_configured() -> bool:
    cfg = _load_smtp_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"])


def send_bookkeeping_email(
    df: pd.DataFrame,
    to_email: str,
    subject: str | None = None,
    body_text: str | None = None,
    base_filename: str = "buchhaltung",
) -> tuple[bool, str]:
    """Send bookkeeping data as email with Banana TXT + CSV attachments.

    Returns (success, message).
    """
    cfg = _load_smtp_config()
    if not cfg["host"] or not cfg["user"]:
        return False, "E-Mail nicht konfiguriert."

    today = datetime.now().strftime("%d.%m.%Y")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    if not subject:
        subject = f"RDS Buchhaltung {base_filename} {today}"

    if not body_text:
        nrows = len(df)
        total = 0.0
        try:
            total = (
                df["Betrag CHF"]
                .apply(
                    lambda x: float(x)
                    if x != "" and x is not None and not (isinstance(x, float) and pd.isna(x))
                    else 0
                )
                .sum()
            )
        except Exception:
            pass
        body_text = (
            f"Buchhaltungsdaten vom {today}\n"
            f"Anzahl Buchungen: {nrows}\n"
            f"Total Betrag CHF: {total:,.2f}\n\n"
            f"Im Anhang:\n"
            f"  {base_filename}_{timestamp}.txt (Banana Import)\n"
            f"  {base_filename}_{timestamp}.csv (CSV)\n\n"
            f"Gesendet von RDS Buchhaltung App"
        )

    msg = MIMEMultipart()
    msg["From"] = cfg["from_email"] or cfg["user"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # Attachment 1: Banana TXT
    txt_data = df_to_banana_tsv(df)
    txt_part = MIMEBase("text", "plain")
    txt_part.set_payload(txt_data.encode("utf-8"))
    encoders.encode_base64(txt_part)
    txt_part.add_header(
        "Content-Disposition", "attachment",
        filename=f"{base_filename}_{timestamp}.txt",
    )
    msg.attach(txt_part)

    # Attachment 2: CSV
    csv_data = df_to_csv(df)
    csv_part = MIMEBase("text", "csv")
    csv_part.set_payload(csv_data.encode("utf-8"))
    encoders.encode_base64(csv_part)
    csv_part.add_header(
        "Content-Disposition", "attachment",
        filename=f"{base_filename}_{timestamp}.csv",
    )
    msg.attach(csv_part)

    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(
                cfg["host"], cfg["port"], context=context, timeout=30
            ) as server:
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
                server.starttls(context=context)
                server.login(cfg["user"], cfg["password"])
                server.send_message(msg)

        return True, f"E-Mail gesendet an {to_email}"
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP Anmeldung fehlgeschlagen. Zugangsdaten in .env prüfen."
    except smtplib.SMTPException as e:
        return False, f"SMTP Fehler: {e}"
    except Exception as e:
        return False, f"E-Mail Fehler: {e}"
