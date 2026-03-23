"""Email sender — professional HTML emails with Banana TXT, CSV & Excel attachments."""
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

from app.services.export import df_to_banana_tsv, df_to_csv, df_to_styled_excel, fmt_swiss


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


def _build_html_body(df: pd.DataFrame, today: str, timestamp: str) -> str:
    nrows = len(df)
    total = 0.0
    try:
        total = df["Betrag CHF"].apply(
            lambda x: float(x) if x not in ("", None) and not (isinstance(x, float) and pd.isna(x)) else 0
        ).sum()
    except Exception:
        pass

    # Build table rows from dataframe
    table_headers = ["Datum", "Beschreibung", "KtSoll", "KtHaben", "Betrag CHF", "MwStUSt-Code"]
    header_cells = "".join(
        f'<th style="padding:10px 14px;text-align:left;font-size:12px;font-weight:600;'
        f'color:#64748b;text-transform:uppercase;letter-spacing:0.05em;'
        f'border-bottom:2px solid #e2e8f0;">{h}</th>'
        for h in table_headers
    )

    body_rows = ""
    for i, (_, row) in enumerate(df.iterrows()):
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        betrag = row.get("Betrag CHF", 0)
        try:
            betrag_str = fmt_swiss(float(betrag))
        except (ValueError, TypeError):
            betrag_str = str(betrag)

        body_rows += f"""<tr style="background:{bg};">
            <td style="padding:10px 14px;font-size:13px;color:#334155;border-bottom:1px solid #f1f5f9;">{row.get('Datum', '')}</td>
            <td style="padding:10px 14px;font-size:13px;color:#334155;border-bottom:1px solid #f1f5f9;">{row.get('Beschreibung', '')}</td>
            <td style="padding:10px 14px;font-size:13px;color:#334155;border-bottom:1px solid #f1f5f9;font-family:monospace;">{row.get('KtSoll', '')}</td>
            <td style="padding:10px 14px;font-size:13px;color:#334155;border-bottom:1px solid #f1f5f9;font-family:monospace;">{row.get('KtHaben', '')}</td>
            <td style="padding:10px 14px;font-size:13px;color:#334155;border-bottom:1px solid #f1f5f9;text-align:right;font-family:monospace;font-weight:600;">{betrag_str}</td>
            <td style="padding:10px 14px;font-size:13px;color:#334155;border-bottom:1px solid #f1f5f9;">{row.get('MwStUSt-Code', '')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px;">
    <tr><td align="center">
      <table width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e40af,#3b82f6);padding:32px 40px;">
            <h1 style="margin:0;font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.01em;">
              📒 Buchhaltung Export
            </h1>
            <p style="margin:6px 0 0;font-size:14px;color:rgba(255,255,255,0.85);">
              {today} · {nrows} Buchung{"en" if nrows != 1 else ""}
            </p>
          </td>
        </tr>

        <!-- Summary Cards -->
        <tr>
          <td style="padding:28px 40px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="50%" style="padding-right:8px;">
                  <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:16px 20px;">
                    <p style="margin:0;font-size:11px;font-weight:600;color:#0369a1;text-transform:uppercase;letter-spacing:0.05em;">Buchungen</p>
                    <p style="margin:6px 0 0;font-size:24px;font-weight:700;color:#0c4a6e;">{nrows}</p>
                  </div>
                </td>
                <td width="50%" style="padding-left:8px;">
                  <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px 20px;">
                    <p style="margin:0;font-size:11px;font-weight:600;color:#15803d;text-transform:uppercase;letter-spacing:0.05em;">Total CHF</p>
                    <p style="margin:6px 0 0;font-size:24px;font-weight:700;color:#14532d;">{fmt_swiss(total)}</p>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Booking Table -->
        <tr>
          <td style="padding:28px 40px 0;">
            <p style="margin:0 0 12px;font-size:15px;font-weight:600;color:#1e293b;">Buchungsübersicht</p>
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
              <thead><tr style="background:#f8fafc;">{header_cells}</tr></thead>
              <tbody>{body_rows}</tbody>
              <tfoot>
                <tr style="background:#f8fafc;">
                  <td colspan="4" style="padding:12px 14px;font-size:13px;font-weight:700;color:#1e293b;border-top:2px solid #e2e8f0;">Total</td>
                  <td style="padding:12px 14px;font-size:13px;font-weight:700;color:#1e293b;text-align:right;font-family:monospace;border-top:2px solid #e2e8f0;">{fmt_swiss(total)}</td>
                  <td style="border-top:2px solid #e2e8f0;"></td>
                </tr>
              </tfoot>
            </table>
          </td>
        </tr>

        <!-- Attachments Info -->
        <tr>
          <td style="padding:28px 40px;">
            <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:16px 20px;">
              <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#92400e;">📎 Anhänge</p>
              <p style="margin:0;font-size:13px;color:#78350f;line-height:1.6;">
                <code style="background:#fef3c7;padding:2px 6px;border-radius:4px;font-size:12px;">buchhaltung_{timestamp}.txt</code> — Banana Accounting Import<br>
                <code style="background:#fef3c7;padding:2px 6px;border-radius:4px;font-size:12px;">buchhaltung_{timestamp}.csv</code> — CSV (Semikolon)<br>
                <code style="background:#fef3c7;padding:2px 6px;border-radius:4px;font-size:12px;">buchhaltung_{timestamp}.xlsx</code> — Excel (formatiert)
              </p>
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;">
            <p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;">
              Automatisch gesendet von <strong style="color:#64748b;">RDS Buchhaltung</strong> · {today}
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_bookkeeping_email(
    df: pd.DataFrame,
    to_email: str,
    subject: str | None = None,
    base_filename: str = "buchhaltung",
) -> tuple[bool, str]:
    cfg = _load_smtp_config()
    if not cfg["host"] or not cfg["user"]:
        return False, "E-Mail nicht konfiguriert."

    today = datetime.now().strftime("%d.%m.%Y")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    nrows = len(df)
    if not subject:
        subject = f"📒 Buchhaltung — {nrows} Buchungen — {today}"

    # Build message
    msg = MIMEMultipart("mixed")
    msg["From"] = cfg["from_email"] or cfg["user"]
    msg["To"] = to_email
    msg["Subject"] = subject

    # HTML body
    html_content = _build_html_body(df, today, timestamp)

    # Alternative part: plain text + HTML
    alt_part = MIMEMultipart("alternative")
    plain_text = (
        f"Buchhaltung Export — {today}\n"
        f"Buchungen: {nrows}\n\n"
        f"Siehe Anhänge für Details.\n\n"
        f"— RDS Buchhaltung"
    )
    alt_part.attach(MIMEText(plain_text, "plain", "utf-8"))
    alt_part.attach(MIMEText(html_content, "html", "utf-8"))
    msg.attach(alt_part)

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

    # Attachment 3: Excel
    try:
        xlsx_data = df_to_styled_excel(df)
        xlsx_part = MIMEBase(
            "application",
            "vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        xlsx_part.set_payload(xlsx_data)
        encoders.encode_base64(xlsx_part)
        xlsx_part.add_header(
            "Content-Disposition", "attachment",
            filename=f"{base_filename}_{timestamp}.xlsx",
        )
        msg.attach(xlsx_part)
    except Exception:
        pass  # Excel optional — don't fail the email

    # Send
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
