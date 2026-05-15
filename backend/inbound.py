import asyncio
import os
import logging
import uuid
from datetime import datetime, timezone
from aiosmtpd.controller import Controller
from motor.motor_asyncio import AsyncIOMotorClient
from email.parser import BytesParser
from email.policy import default

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("relayd-inbound")

db = None
client = None

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
            peer = session.peer
            mail_from = envelope.mail_from
            rcpts = envelope.rcpt_tos
            content = envelope.content  # bytes
            
            # Parse message
            msg = BytesParser(policy=default).parsebytes(content)
            subject = msg.get('subject', '(No Subject)')
            
            logger.info(f"Incoming mail from {mail_from} to {rcpts}")
            
            for rcpt in rcpts:
                rcpt = rcpt.lower().strip().strip('<>')
                domain_name = rcpt.split('@')[-1]
                
                # Find the owner of the domain
                domain_doc = await db.domains.find_one({"name": domain_name})
                if not domain_doc:
                    continue
                
                user_id = domain_doc["user_id"]
                
                # Check if this recipient is a dedicated Mailbox
                is_mailbox = await db.mailboxes.count_documents({"address": rcpt, "active": True}) > 0

                # Save message to DB
                msg_id = str(uuid.uuid4())
                message_doc = {
                    "id": msg_id,
                    "user_id": user_id,
                    "from": mail_from,
                    "to": rcpt,
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
                logger.info(f"Stored message {msg_id} for {rcpt}")
                
                # Forward to Stalwart IMAP Server if it's a dedicated mailbox
                if is_mailbox:
                    import smtplib
                    try:
                        # Attempt to forward to internal Stalwart container on port 2525
                        with smtplib.SMTP("stalwart", 2525) as smtp:
                            smtp.send_message(msg, from_addr=mail_from, to_addrs=[rcpt])
                        logger.info(f"Forwarded {msg_id} to Stalwart IMAP server for {rcpt}")
                    except Exception as e:
                        # It's fine if Stalwart isn't running, it just stays in the Webmail DB
                        logger.warning(f"Stalwart IMAP forward skipped: {e}")
                
            return '250 Message accepted for delivery'
        except Exception as e:
            logger.error(f"Error handling DATA: {e}")
            return '451 Internal error during storage'

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
    
    handler = RelaydHandler()
    controller = Controller(handler, hostname='0.0.0.0', port=25)
    
    logger.info("Starting Inbound SMTP listener on port 25...")
    controller.start()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        controller.stop()

if __name__ == "__main__":
    asyncio.run(start_inbound())
