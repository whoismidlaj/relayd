"""Outbound relay service: send via Resend or Generic SMTP. Other providers stubbed."""
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
import resend


class RelaySendError(Exception):
    pass


async def send_via_resend(api_key: str, from_email: str, to: list[str], subject: str,
                         html: str | None = None, text: str | None = None) -> dict:
    if not api_key:
        raise RelaySendError("Resend API key missing")
    resend.api_key = api_key
    params: dict[str, Any] = {"from": from_email, "to": to, "subject": subject}
    if html:
        params["html"] = html
    if text:
        params["text"] = text
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"ok": True, "message_id": result.get("id"), "raw": result}
    except Exception as e:
        return {"ok": False, "error": str(e), "raw": None}


def _send_smtp_sync(config: dict, from_email: str, to: list[str], subject: str,
                    html: str | None, text: str | None) -> dict:
    host = config.get("host")
    port = int(config.get("port", 587))
    username = config.get("username")
    password = config.get("password")
    use_tls = bool(config.get("use_tls", True))
    use_ssl = bool(config.get("use_ssl", False))

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if text:
        msg.attach(MIMEText(text, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
    try:
        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.sendmail(from_email, to, msg.as_string())
        return {"ok": True, "message_id": msg.get("Message-ID", ""), "raw": "250 OK"}
    finally:
        try:
            server.quit()
        except Exception:
            pass


async def send_via_smtp(config: dict, from_email: str, to: list[str], subject: str,
                       html: str | None = None, text: str | None = None) -> dict:
    try:
        return await asyncio.to_thread(_send_smtp_sync, config, from_email, to, subject, html, text)
    except Exception as e:
        return {"ok": False, "error": str(e), "raw": None}


async def send_email(provider: dict, from_email: str, to: list[str], subject: str,
                    html: str | None = None, text: str | None = None) -> dict:
    """Dispatch send through the appropriate provider type."""
    ptype = provider.get("type")
    cfg = provider.get("config", {}) or {}

    if ptype == "resend":
        return await send_via_resend(cfg.get("api_key", ""), from_email, to, subject, html, text)
    if ptype == "smtp":
        return await send_via_smtp(cfg, from_email, to, subject, html, text)
    # Stubs — config-only providers
    if ptype in ("ses", "brevo", "smtp2go"):
        return {
            "ok": False,
            "error": f"Provider '{ptype}' is configured but sending is not yet wired in this MVP.",
            "raw": None,
        }
    return {"ok": False, "error": f"Unknown provider type: {ptype}", "raw": None}
