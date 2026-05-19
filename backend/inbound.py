import asyncio
import os
import logging
import ssl
import sys
from pathlib import Path
from datetime import datetime, timezone
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, AuthResult, LoginPassword
from email.parser import BytesParser
from email.policy import default

from dotenv import load_dotenv
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth import verify_password

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("relayd-inbound")


# ---------------------------------------------------------------------------
# STARTTLS Controller
# ---------------------------------------------------------------------------
class STARTTLSController(Controller):
    def __init__(self, handler, hostname="0.0.0.0", port=587, tls_context=None, authenticator=None, auth_required=True):
        self.tls_context = tls_context
        self.authenticator = authenticator
        self.auth_required = auth_required
        super().__init__(handler, hostname=hostname, port=port)

    def factory(self):
        return SMTP(
            self.handler,
            tls_context=self.tls_context,
            require_starttls=False,
            authenticator=self.authenticator,
            auth_required=self.auth_required,
            auth_require_tls=False,
        )


# ---------------------------------------------------------------------------
# Authenticator for Outgoing Submission (synchronous — runs in thread)
# Uses a synchronous psycopg2 connection to avoid event loop conflicts with aiosmtpd
# ---------------------------------------------------------------------------
class MailboxAuthenticator:
    """Synchronous mailbox authenticator for the SMTP Submission server."""

    def __call__(self, server, session, envelope, mechanism, auth_data):
        if not isinstance(auth_data, LoginPassword):
            return AuthResult(success=False, handled=False)

        username = auth_data.login.decode("utf-8", errors="ignore").lower().strip()
        password = auth_data.password.decode("utf-8", errors="ignore")

        try:
            import psycopg2
            db_url = os.environ.get("DATABASE_URL", "")
            # Convert asyncpg URL to psycopg2 URL (strip +asyncpg)
            sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgresql://")
            conn = psycopg2.connect(sync_url)
            cur = conn.cursor()
            cur.execute(
                "SELECT password_hash FROM mailboxes WHERE address = %s AND active = TRUE",
                (username,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            if not row:
                logger.warning(f"Submission Auth Failed: Mailbox '{username}' not found or inactive")
                return AuthResult(success=False, handled=False)

            if verify_password(password, row[0]):
                session.authenticated_user = username
                logger.info(f"Submission Auth Succeeded: {username}")
                return AuthResult(success=True)

            logger.warning(f"Submission Auth Failed: Password mismatch for '{username}'")
            return AuthResult(success=False, handled=False)

        except Exception as e:
            logger.error(f"Submission Auth Error: {e}")
            return AuthResult(success=False, handled=False)


# ---------------------------------------------------------------------------
# Inbound Handler (Port 25)
# ---------------------------------------------------------------------------
class RelaydHandler:
    async def handle_MAIL(self, server, session, envelope, address, mail_options):
        envelope.mail_from = address
        return "250 OK"

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        try:
            from database import AsyncSessionLocal
            from models import Domain, Mailbox, Alias
            from sqlalchemy import select, func

            rcpt = address.lower().strip().strip("<>")
            if "@" not in rcpt:
                return "550 Invalid recipient"

            domain = rcpt.split("@")[-1]
            logger.info(f"Incoming RCPT check: {rcpt}")

            async with AsyncSessionLocal() as session:
                # 1. Check if domain exists and is verified
                result = await session.execute(select(Domain).where(Domain.name == domain))
                domain_doc = result.scalar_one_or_none()
                if not domain_doc:
                    logger.warning(f"Rejected: Domain '{domain}' not in database")
                    return "550 Relay access denied"
                if not domain_doc.verified:
                    logger.warning(f"Rejected: Domain '{domain}' not verified")
                    return "550 Domain not verified"

                # 2. Check mailbox
                result = await session.execute(
                    select(Mailbox).where(Mailbox.address == rcpt, Mailbox.active == True)
                )
                if result.scalar_one_or_none():
                    envelope.rcpt_tos.append(address)
                    return "250 OK"

                # 3. Check alias
                result = await session.execute(
                    select(Alias).where(Alias.address == rcpt, Alias.enabled == True)
                )
                if result.scalar_one_or_none():
                    envelope.rcpt_tos.append(address)
                    return "250 OK"

                # 4. Check catch-all
                result = await session.execute(
                    select(Alias).where(Alias.address == f"*@{domain}", Alias.enabled == True)
                )
                if result.scalar_one_or_none():
                    envelope.rcpt_tos.append(address)
                    return "250 OK"

            logger.info(f"Rejected: {rcpt} - No mailbox or alias found")
            return "550 No such user"

        except Exception as e:
            logger.error(f"Inbound RCPT error: {e}", exc_info=True)
            return "451 Internal error"

    async def handle_DATA(self, server, session, envelope):
        try:
            logger.info("--- START handle_DATA ---")
            mail_from = envelope.mail_from
            rcpts = envelope.rcpt_tos
            content = envelope.content  # bytes

            logger.info(f"Incoming: From={mail_from}, To={rcpts}, Size={len(content)}")

            try:
                msg = BytesParser(policy=default).parsebytes(content)
                subject = msg.get("subject", "(No Subject)")
            except Exception as e:
                logger.error(f"Parse error: {e}")
                return "554 Error parsing message content"

            for rcpt in rcpts:
                try:
                    rcpt_clean = rcpt.lower().strip().strip("<>")
                    # Forward to Dovecot LMTP — single source of truth for mail storage
                    import smtplib
                    dovecot_host = os.environ.get("DOVECOT_HOST", "dovecot")
                    dovecot_port = int(os.environ.get("DOVECOT_LMTP_PORT", "2525"))
                    try:
                        with smtplib.SMTP(dovecot_host, dovecot_port, timeout=5) as lmtp:
                            lmtp.sendmail(mail_from or "MAILER-DAEMON", [rcpt_clean], content)
                        logger.info(f"Delivered to Dovecot LMTP for {rcpt_clean} (from={mail_from}, subject={subject!r}, size={len(content)})")
                    except Exception as e:
                        logger.warning(f"Dovecot LMTP forward failed for {rcpt_clean}: {e}")
                except Exception as rcpt_err:
                    logger.error(f"Rcpt error {rcpt}: {rcpt_err}")

            logger.info("--- END handle_DATA ---")
            return "250 Message accepted for delivery"
        except Exception as e:
            logger.error(f"DATA Error: {e}", exc_info=True)
            return "451 Internal error"


# ---------------------------------------------------------------------------
# Submission Handler (Port 587) — outbound SMTP for mailbox users
# ---------------------------------------------------------------------------
background_tasks: set = set()


async def run_submission_in_background(payload, mock_user, rcpt_clean):
    try:
        from routers.relay_routes import send_test_email
        res = await send_test_email(payload, user=mock_user)
        logger.info(f"Submission to {rcpt_clean} processed in background: {res}")
    except Exception as e:
        logger.error(f"Background submission failed for {rcpt_clean}: {e}", exc_info=True)


class SubmissionHandler:
    async def handle_MAIL(self, server, session, envelope, address, mail_options):
        if not hasattr(session, "authenticated_user"):
            return "530 Authentication required"
        mail_from = address.lower().strip().strip("<>")
        auth_user = session.authenticated_user.lower().strip()
        if mail_from != auth_user:
            logger.warning(f"Submission Rejected: auth={auth_user} tried to send as {mail_from}")
            return "553 From address must match authenticated user"
        envelope.mail_from = address
        return "250 OK"

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not hasattr(session, "authenticated_user"):
            return "530 Authentication required"
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        try:
            if not hasattr(session, "authenticated_user"):
                return "530 Authentication required"

            auth_user = session.authenticated_user.lower().strip()

            from database import AsyncSessionLocal
            from models import Mailbox
            from sqlalchemy import select

            async with AsyncSessionLocal() as db_session:
                result = await db_session.execute(
                    select(Mailbox).where(Mailbox.address == auth_user)
                )
                mailbox = result.scalar_one_or_none()

            if not mailbox:
                return "554 Sender mailbox not found"

            user_id = mailbox.user_id
            content = envelope.content

            try:
                msg = BytesParser(policy=default).parsebytes(content)
                subject = msg.get("subject", "(No Subject)")
                body_text = ""
                body_html = None
                plain_part = msg.get_body(preferencelist=("plain",))
                if plain_part:
                    body_text = plain_part.get_content()
                html_part = msg.get_body(preferencelist=("html",))
                if html_part:
                    body_html = html_part.get_content()
            except Exception as parse_err:
                logger.error(f"Submission Parse Error: {parse_err}")
                return "554 Error parsing message"

            from routers.relay_routes import TestEmailIn
            logger.info(f"Processing Submission from {auth_user} to {envelope.rcpt_tos}")

            for rcpt in envelope.rcpt_tos:
                rcpt_clean = rcpt.lower().strip().strip("<>")
                payload = TestEmailIn(
                    from_email=auth_user,
                    to=rcpt_clean,
                    subject=subject,
                    body=body_text or body_html or " ",
                    tags=["submission"],
                )
                mock_user = {"id": user_id, "email": auth_user, "role": "user"}
                task = asyncio.create_task(run_submission_in_background(payload, mock_user, rcpt_clean))
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)

            return "250 Message accepted for delivery"
        except Exception as e:
            logger.error(f"Submission DATA Error: {e}", exc_info=True)
            return "451 Internal error"


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
async def start_inbound():
    from database import get_engine
    get_engine()  # initialise pool

    handler = RelaydHandler()
    smtp_port = int(os.environ.get("SMTP_PORT", 25))
    smtp_host = os.environ.get("SMTP_HOST", "127.0.0.1" if sys.platform == "win32" else "0.0.0.0")
    controller = Controller(handler, hostname=smtp_host, port=smtp_port)
    logger.info(f"Starting Inbound SMTP listener on port {smtp_port} on {smtp_host}...")
    controller.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        controller.stop()


async def start_submission():
    from database import get_engine
    get_engine()

    ssl_dir = os.environ.get("SSL_DIR", "/app")
    if not os.path.exists(ssl_dir):
        ssl_dir = "."
    cert_path = f"{ssl_dir}/cert.pem"
    key_path  = f"{ssl_dir}/key.pem"

    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        logger.info("Generating self-signed SSL certificate for SMTP Submission...")
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime as dt
            import ipaddress
            import urllib.request

            public_ip = None
            try:
                public_ip = urllib.request.urlopen("https://api.ipify.org", timeout=2).read().decode().strip()
            except Exception:
                pass

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "relayd-smtp")])
            san_list = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]
            if public_ip:
                try:
                    san_list.append(x509.IPAddress(ipaddress.IPv4Address(public_ip)))
                    logger.info(f"Added public IP to SSL SAN: {public_ip}")
                except Exception:
                    pass

            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(dt.datetime.now(dt.timezone.utc))
                .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3650))
                .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
                .sign(key, hashes.SHA256())
            )
            with open(key_path, "wb") as f:
                f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            logger.info("Self-signed certificate generated successfully")
        except Exception as e:
            logger.error(f"Failed to generate SSL certificate: {e}")

    context = None
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert_path, key_path)
    except Exception as ssl_err:
        logger.error(f"Failed to create SSL context: {ssl_err}")

    authenticator = MailboxAuthenticator()
    handler = SubmissionHandler()
    submission_port = int(os.environ.get("SUBMISSION_PORT", 587))
    submission_host = os.environ.get("SUBMISSION_HOST", "127.0.0.1" if sys.platform == "win32" else "0.0.0.0")
    controller = STARTTLSController(handler, hostname=submission_host, port=submission_port, tls_context=context, authenticator=authenticator)
    logger.info(f"Starting Outgoing SMTP Submission listener on port {submission_port} on {submission_host}...")
    controller.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        controller.stop()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    async def main():
        await asyncio.gather(start_inbound(), start_submission())

    asyncio.run(main())
