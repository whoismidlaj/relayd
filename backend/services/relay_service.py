import asyncio
import smtplib
import dns.resolver
import dkim
import time
import resend
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Any


class RelaySendError(Exception):
    pass


def get_mx_records(domain: str) -> list[str]:
    """Find MX servers for a domain, sorted by priority."""
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        # Sort by priority
        records = sorted(answers, key=lambda x: x.preference)
        return [r.exchange.to_text().strip('.') for r in records]
    except Exception:
        # Fallback to A record if no MX exists
        return [domain]


def _send_direct_sync(from_email: str, to: list[str], subject: str,
                     html: str | None, text: str | None,
                     dkim_key: str | None = None, dkim_selector: str = "mail") -> dict:
    from_domain = from_email.split('@')[-1]
    recipient_domain = to[0].split('@')[-1]
    mx_hosts = get_mx_records(recipient_domain)

    if not mx_hosts:
        return {"ok": False, "error": f"No MX records found for {recipient_domain}", "raw": None}

    # Construct message
    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_domain)

    if text:
        msg.attach(MIMEText(text, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    msg_bytes = msg.as_bytes()

    # Sign with DKIM if key provided
    if dkim_key:
        try:
            # dkimpy expects bytes for everything
            header = dkim.sign(
                msg_bytes,
                dkim_selector.encode(),
                from_domain.encode(),
                dkim_key.encode(),
                include_headers=[b"From", b"To", b"Subject", b"Date", b"Message-ID"]
            )
            msg_bytes = header + msg_bytes
        except Exception as e:
            # Log signing error but attempt send anyway? Or fail? 
            # Better to fail to avoid spam box
            return {"ok": False, "error": f"DKIM signing failed: {e}", "raw": None}

    last_error = "Unknown error"
    for host in mx_hosts:
        try:
            # Direct send on port 25
            server = smtplib.SMTP(host, 25, timeout=20)
            server.ehlo(from_domain)
            if server.has_extn("STARTTLS"):
                server.starttls()
                server.ehlo(from_domain)
            
            server.sendmail(from_email, to, msg_bytes)
            server.quit()
            return {"ok": True, "message_id": msg["Message-ID"], "raw": f"Delivered via {host}"}
        except Exception as e:
            last_error = str(e)
            continue
    
    return {"ok": False, "error": f"Failed to deliver to any MX: {last_error}", "raw": None}


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
    if ptype == "direct":
        # Direct send requires DKIM key from the domain
        dkim_key = cfg.get("dkim_private_key")
        dkim_selector = cfg.get("dkim_selector", "mail")
        return await asyncio.to_thread(_send_direct_sync, from_email, to, subject, html, text, dkim_key, dkim_selector)

    # Stubs — config-only providers
    if ptype in ("ses", "brevo", "smtp2go"):
        return {
            "ok": False,
            "error": f"Provider '{ptype}' is configured but sending is not yet wired in this MVP.",
            "raw": None,
        }
    return {"ok": False, "error": f"Unknown provider type: {ptype}", "raw": None}
