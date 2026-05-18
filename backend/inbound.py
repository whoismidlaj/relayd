import asyncio
import os
import logging
import uuid
import ssl
import pymongo
from datetime import datetime, timezone
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, AuthResult, LoginPassword
from motor.motor_asyncio import AsyncIOMotorClient
from email.parser import BytesParser
from email.policy import default

from auth import verify_password

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("relayd-inbound")

db = None
client = None

# ---- Custom Controller for STARTTLS support on port 587 ----
class STARTTLSController(Controller):
    def __init__(self, handler, hostname='0.0.0.0', port=587, tls_context=None, authenticator=None, auth_required=True):
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
            auth_require_tls=False  # Allow auth over STARTTLS or plain for local testing
        )

# ---- Authenticator for Outgoing Submission ----
class MailboxAuthenticator:
    def __init__(self, mongo_url, db_name):
        self.client = pymongo.MongoClient(mongo_url)
        self.db = self.client[db_name]

    def __call__(self, server, session, envelope, mechanism, auth_data):
        if not isinstance(auth_data, LoginPassword):
            return AuthResult(success=False, handled=False)
            
        username = auth_data.login.decode('utf-8', errors='ignore').lower().strip()
        password = auth_data.password.decode('utf-8', errors='ignore')
        
        try:
            mailbox = self.db.mailboxes.find_one({"address": username, "active": True})
            if not mailbox:
                logger.warning(f"Submission Auth Failed: Mailbox '{username}' not found or inactive")
                return AuthResult(success=False, handled=False)
                
            if verify_password(password, mailbox.get("password_hash", "")):
                session.authenticated_user = username
                logger.info(f"Submission Auth Succeeded: {username}")
                return AuthResult(success=True)
                
            logger.warning(f"Submission Auth Failed: Password mismatch for '{username}'")
            return AuthResult(success=False, handled=False)
        except Exception as e:
            logger.error(f"Submission Auth Error: {e}")
            return AuthResult(success=False, handled=False)

# ---- Handler for Inbound Port 25 ----
class RelaydHandler:
    async def handle_MAIL(self, server, session, envelope, address, mail_options):
        """Handle the MAIL FROM command."""
        envelope.mail_from = address
        return '250 OK'

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        """Verify that we should accept mail for this recipient."""
        global db
        try:
            # Sanitize address
            rcpt = address.lower().strip().strip('<>')
            if '@' not in rcpt:
                return '550 Invalid recipient'

            domain = rcpt.split('@')[-1]
            logger.info(f"Incoming RCPT check: {rcpt}")
            
            # 1. Check if domain exists
            domain_doc = await db.domains.find_one({"name": domain})
            if not domain_doc:
                logger.warning(f"Rejected: Domain '{domain}' not in database")
                return '550 Relay access denied'
            
            # Check verification
            is_verified = domain_doc.get("verified")
            if is_verified not in [True, "true", "True"]:
                logger.warning(f"Rejected: Domain '{domain}' not verified")
                return '550 Domain not verified'
            
            # 2. Check if address exists as mailbox or alias
            mailbox = await db.mailboxes.find_one({"address": rcpt, "active": True})
            if mailbox:
                envelope.rcpt_tos.append(address)
                return '250 OK'
                
            alias = await db.aliases.find_one({"address": rcpt, "enabled": True})
            if alias:
                envelope.rcpt_tos.append(address)
                return '250 OK'
                
            # 3. Check for Catch-all
            catchall = await db.aliases.find_one({"address": f"*@{domain}", "enabled": True})
            if catchall:
                envelope.rcpt_tos.append(address)
                return '250 OK'

            logger.info(f"Rejected: {rcpt} - No mailbox or alias found")
            return '550 No such user'
        except Exception as e:
            logger.error(f"Inbound error: {e}", exc_info=True)
            return '451 Internal error'

    async def handle_DATA(self, server, session, envelope):
        """Process the incoming email message."""
        global db
        try:
            logger.info("--- START handle_DATA ---")
            mail_from = envelope.mail_from
            rcpts = envelope.rcpt_tos
            content = envelope.content  # bytes
            
            logger.info(f"Incoming: From={mail_from}, To={rcpts}, Size={len(content)}")
            
            # Parse message
            try:
                msg = BytesParser(policy=default).parsebytes(content)
                subject = msg.get('subject', '(No Subject)')
            except Exception as e:
                logger.error(f"Parse error: {e}")
                return '554 Error parsing message content'

            for rcpt in rcpts:
                try:
                    rcpt_clean = rcpt.lower().strip().strip('<>')
                    domain_name = rcpt_clean.split('@')[-1]
                    
                    domain_doc = await db.domains.find_one({"name": domain_name})
                    if not domain_doc:
                        continue
                    
                    user_id = domain_doc["user_id"]
                    is_mailbox = await db.mailboxes.count_documents({"address": rcpt_clean, "active": True}) > 0

                    # Save to DB
                    msg_id = str(uuid.uuid4())
                    message_doc = {
                        "id": msg_id,
                        "user_id": user_id,
                        "from": mail_from,
                        "to": rcpt_clean,
                        "subject": subject,
                        "body_text": msg.get_body(preferencelist=('plain',)).get_content() if msg.get_body(preferencelist=('plain',)) else "",
                        "body_html": msg.get_body(preferencelist=('html',)).get_content() if msg.get_body(preferencelist=('html',)) else None,
                        "headers": dict(msg.items()),
                        "raw_size": len(content),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "read": False,
                        "is_mailbox": is_mailbox
                    }
                    
                    await db.inbound_messages.insert_one(message_doc)
                    logger.info(f"Stored message {msg_id} for {rcpt_clean}")
                    
                    if is_mailbox:
                        import smtplib
                        dovecot_host = os.environ.get("DOVECOT_HOST", "dovecot")
                        dovecot_port = int(os.environ.get("DOVECOT_LMTP_PORT", "2525"))
                        try:
                            with smtplib.SMTP(dovecot_host, dovecot_port, timeout=5) as lmtp:
                                lmtp.sendmail(mail_from or "MAILER-DAEMON", [rcpt_clean], content)
                            logger.info(f"Forwarded {msg_id} to Dovecot LMTP ({dovecot_host}:{dovecot_port})")
                        except Exception as e:
                            logger.warning(f"Dovecot LMTP forward failed for {rcpt_clean}: {e} — message still saved in MongoDB")
                except Exception as rcpt_err:
                    logger.error(f"Rcpt error {rcpt}: {rcpt_err}")

            logger.info("--- END handle_DATA ---")
            return '250 Message accepted for delivery'
        except Exception as e:
            logger.error(f"DATA Error: {e}", exc_info=True)
            return '451 Internal error'

# ---- Background task tracker & runner for SMTP Submission ----
background_tasks = set()

async def run_submission_in_background(payload, mock_user, rcpt_clean):
    try:
        from routers.relay_routes import send_test_email
        res = await send_test_email(payload, user=mock_user)
        logger.info(f"Submission to {rcpt_clean} successfully processed in background: {res}")
    except Exception as e:
        logger.error(f"Background submission failed for {rcpt_clean}: {e}", exc_info=True)

# ---- Handler for Outbound Port 587 ----
class SubmissionHandler:
    async def handle_MAIL(self, server, session, envelope, address, mail_options):
        if not hasattr(session, 'authenticated_user'):
            return '530 Authentication required'
            
        mail_from = address.lower().strip().strip('<>')
        auth_user = session.authenticated_user.lower().strip()
        
        if mail_from != auth_user:
            logger.warning(f"Submission Rejected: authenticated as {auth_user} but tried to send as {mail_from}")
            return '553 From address must match authenticated user'
            
        envelope.mail_from = address
        return '250 OK'

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not hasattr(session, 'authenticated_user'):
            return '530 Authentication required'
            
        envelope.rcpt_tos.append(address)
        return '250 OK'

    async def handle_DATA(self, server, session, envelope):
        global db
        try:
            if not hasattr(session, 'authenticated_user'):
                return '530 Authentication required'
                
            auth_user = session.authenticated_user.lower().strip()
            mailbox = await db.mailboxes.find_one({"address": auth_user})
            if not mailbox:
                return '554 Sender mailbox not found'
                
            user_id = mailbox["user_id"]
            content = envelope.content
            
            # Parse message
            try:
                msg = BytesParser(policy=default).parsebytes(content)
                subject = msg.get('subject', '(No Subject)')
                
                body_text = ""
                body_html = None
                
                plain_part = msg.get_body(preferencelist=('plain',))
                if plain_part:
                    body_text = plain_part.get_content()
                
                html_part = msg.get_body(preferencelist=('html',))
                if html_part:
                    body_html = html_part.get_content()
            except Exception as parse_err:
                logger.error(f"Submission Parse Error: {parse_err}")
                return '554 Error parsing message'
                
            # Import routes logic
            from routers.relay_routes import TestEmailIn
            
            logger.info(f"Processing Submission from {auth_user} to {envelope.rcpt_tos}")
            
            for rcpt in envelope.rcpt_tos:
                rcpt_clean = rcpt.lower().strip().strip('<>')
                
                payload = TestEmailIn(
                    from_email=auth_user,
                    to=rcpt_clean,
                    subject=subject,
                    body=body_text or body_html or " ",
                    tags=["submission"]
                )
                mock_user = {"id": user_id, "email": auth_user, "role": "user"}
                
                # Hand it off to the smart routing and failover engine in the background
                # to return a 250 response to the client immediately and prevent timeouts.
                task = asyncio.create_task(run_submission_in_background(payload, mock_user, rcpt_clean))
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
                
            return '250 Message accepted for delivery'
        except Exception as e:
            logger.error(f"Submission DATA Error: {e}", exc_info=True)
            return '451 Internal error'

async def start_inbound():
    global db, client
    
    # Initialize DB
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "relayd_db")
    
    # Same stability logic as server.py
    use_tls = any(x in mongo_url.lower() for x in ["mongodb+srv://", "tls=true", "ssl=true"])
    client_kwargs = {
        "connectTimeoutMS": 30000,
        "serverSelectionTimeoutMS": 30000,
        "heartbeatFrequencyMS": 10000,
        "maxIdleTimeMS": 60000,
        "retryWrites": True,
    }
    if use_tls:
        import certifi
        client_kwargs.update({
            "tlsCAFile": certifi.where(),
            "directConnection": False,
        })
        if not any(x in mongo_url.lower() for x in ["mongodb+srv://", "ssl=", "tls="]):
            client_kwargs["tls"] = True
        
    client = AsyncIOMotorClient(mongo_url, **client_kwargs)
    db = client[db_name]
    
    # Expose db reference to server module so imported routes work in this process context
    import server
    server.db = db
    
    handler = RelaydHandler()
    controller = Controller(handler, hostname='0.0.0.0', port=25)
    
    logger.info("Starting Inbound SMTP listener on port 25...")
    controller.start()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        controller.stop()

async def start_submission():
    global db
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "relayd_db")
    
    # Generate self-signed cert if missing
    ssl_dir = "/app"
    cert_path = f"{ssl_dir}/cert.pem"
    key_path = f"{ssl_dir}/key.pem"
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        logger.info("Generating self-signed SSL certificate for SMTP Submission...")
        os.system(f'openssl req -new -x509 -days 3650 -nodes -out {cert_path} -keyout {key_path} -subj "/CN=relayd-smtp"')
        
    # Build SSL Context for STARTTLS
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert_path, key_path)
    except Exception as ssl_err:
        logger.error(f"Failed to create SSL context for STARTTLS: {ssl_err}")
        context = None

    authenticator = MailboxAuthenticator(mongo_url, db_name)
    handler = SubmissionHandler()
    
    controller = STARTTLSController(
        handler, 
        hostname='0.0.0.0', 
        port=587, 
        tls_context=context, 
        authenticator=authenticator
    )
    
    logger.info("Starting Outgoing SMTP Submission listener on port 587...")
    controller.start()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        controller.stop()

if __name__ == "__main__":
    # Ensure Windows asyncio loop policy
    import sys
    if sys.platform == 'win32':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    async def main():
        await asyncio.gather(
            start_inbound(),
            start_submission()
        )
        
    asyncio.run(main())
