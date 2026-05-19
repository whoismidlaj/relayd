"""End-to-End Local SMTP Tester for Relayd.

This script makes local testing incredibly fast, robust, and completely automatic.
It connects to your local MongoDB instance, verifies or seeds a test domain and mailbox,
and runs both Inbound (Port 1025) and Outbound Submission (Port 1587) SMTP handshakes.
"""
import os
import ssl
import sys
import smtplib
import pymongo
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from auth import hash_password

# Dynamic .env Loader
def load_env():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

# Load local environment first
load_env()

# Configuration
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "relayd_db")
SMTP_HOST = "127.0.0.1"
SMTP_INBOUND_PORT = 1025
SMTP_SUBMISSION_PORT = 1587

TEST_DOMAIN = "localtest.com"
TEST_MAILBOX = "hello@localtest.com"
TEST_PASSWORD = "password123"

def print_banner(title):
    print("\n" + "=" * 60)
    print(f" {title.upper()} ".center(60, "-"))
    print("=" * 60)

def main():
    print_banner("Relayd Local SMTP Test Suite")

    # 1. Connect to MongoDB and seed test accounts
    print(f"Connecting to MongoDB at {MONGO_URL}...")
    try:
        # Use direct connection or TLS configuration matches Atlas SRV/URL parameters
        client_kwargs = {}
        if "ssl=true" in MONGO_URL.lower() or "tls=true" in MONGO_URL.lower() or "mongodb+srv://" in MONGO_URL.lower():
            import certifi
            client_kwargs["tlsCAFile"] = certifi.where()

        client = pymongo.MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000, **client_kwargs)
        db = client[DB_NAME]
        # Ping the DB
        client.admin.command('ping')
        print("[SUCCESS] Connected to MongoDB successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}")
        print("Please ensure MongoDB is running or the MONGO_URL in your .env file is correct.")
        sys.exit(1)

    # Retrieve or create a valid user_id
    user = db.users.find_one({"role": "admin"})
    user_id = str(user["_id"]) if user else "mock_admin_user_id"

    # Seed verified domain
    print(f"\nEnsuring domain '{TEST_DOMAIN}' is verified in database with user_id '{user_id}'...")
    db.domains.update_one(
        {"name": TEST_DOMAIN},
        {"$set": {
            "verified": True,
            "user_id": user_id,
            "created_at": datetime.datetime.utcnow()
        }},
        upsert=True
    )
    print(f"[SUCCESS] Domain '{TEST_DOMAIN}' seeded and verified.")

    # Seed active mailbox
    print(f"Ensuring mailbox '{TEST_MAILBOX}' exists with password '{TEST_PASSWORD}' and user_id '{user_id}'...")
    db.mailboxes.update_one(
        {"address": TEST_MAILBOX},
        {"$set": {
            "password_hash": hash_password(TEST_PASSWORD),
            "user_id": user_id,
            "active": True,
            "created_at": datetime.datetime.utcnow()
        }},
        upsert=True
    )
    print(f"[SUCCESS] Mailbox '{TEST_MAILBOX}' seeded and verified.")

    # -------------------------------------------------------------
    # TEST 1: INBOUND SMTP EMAIL (PORT 1025)
    # -------------------------------------------------------------
    print_banner("Test 1: Inbound Mail Delivery (Port 1025)")
    print(f"Sending a mock inbound email from external to '{TEST_MAILBOX}'...")
    
    msg_in = MIMEMultipart()
    msg_in["From"] = "sender@gmail.com"
    msg_in["To"] = TEST_MAILBOX
    msg_in["Subject"] = "Welcome to Relayd local testing!"
    msg_in.attach(MIMEText("This simulates an incoming message sent from an external provider directly to your inbox.", "plain"))

    try:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_INBOUND_PORT, timeout=5)
        print(f"Connected to Inbound SMTP on {SMTP_HOST}:{SMTP_INBOUND_PORT}")
        smtp.sendmail("sender@gmail.com", [TEST_MAILBOX], msg_in.as_string())
        smtp.quit()
        print("[SUCCESS] Inbound message accepted by SMTP listener!")
    except Exception as e:
        print(f"[ERROR] FAILED Inbound SMTP test: {e}")
        print("Is 'python inbound.py' running locally with SMTP_PORT=1025?")

    # -------------------------------------------------------------
    # TEST 2: OUTBOUND SMTP SUBMISSION (PORT 1587)
    # -------------------------------------------------------------
    print_banner("Test 2: Outbound Mail Submission (Port 1587)")
    print(f"Connecting to Submission server on {SMTP_HOST}:{SMTP_SUBMISSION_PORT}...")
    
    msg_out = MIMEMultipart()
    msg_out["From"] = TEST_MAILBOX
    msg_out["To"] = "recipient@external.com"
    msg_out["Subject"] = "Sending Outbound via Relayd Submission"
    msg_out.attach(MIMEText("This simulates Thunderbird connecting via STARTTLS, authenticating, and submitting a mail.", "plain"))

    try:
        # Create non-verifying SSL context for self-signed certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        smtp = smtplib.SMTP(SMTP_HOST, SMTP_SUBMISSION_PORT, timeout=5)
        print(f"Connected to Submission server on {SMTP_HOST}:{SMTP_SUBMISSION_PORT}")
        
        # Say hello
        smtp.ehlo()
        
        # Start TLS
        print("Initiating STARTTLS secure handshake...")
        smtp.starttls(context=ssl_context)
        smtp.ehlo()
        
        # Authenticate
        print(f"Authenticating as '{TEST_MAILBOX}'...")
        smtp.login(TEST_MAILBOX, TEST_PASSWORD)
        print("[SUCCESS] Authentication Succeeded!")
        
        # Send
        print(f"Submitting mail from '{TEST_MAILBOX}' to 'recipient@external.com'...")
        smtp.sendmail(TEST_MAILBOX, ["recipient@external.com"], msg_out.as_string())
        smtp.quit()
        print("[SUCCESS] Outgoing message submitted and accepted successfully!")
    except Exception as e:
        print(f"[ERROR] FAILED Outbound Submission test: {e}")
        print("Is 'python inbound.py' running locally with SUBMISSION_PORT=1587?")

    # -------------------------------------------------------------
    # DB RECORD VERIFICATION
    # -------------------------------------------------------------
    print_banner("Verification: Checking Database Records")
    
    # 1. Check Inbound Messages logged in DB
    inbox_records = list(db.inbound_messages.find({"to": TEST_MAILBOX}).sort("_id", -1).limit(1))
    if inbox_records:
        rec = inbox_records[0]
        print(f"[SUCCESS] Found Inbound Log in DB:")
        print(f"  - Subject: '{rec.get('subject')}'")
        print(f"  - From: {rec.get('from')}")
        print(f"  - Received At: {rec.get('created_at')}")
    else:
        print("[ERROR] No Inbound Log record found in DB for this recipient.")

    # 2. Check Outbound Delivery logs
    outbox_records = list(db.delivery_logs.find({"from_email": TEST_MAILBOX}).sort("_id", -1).limit(1))
    if outbox_records:
        rec = outbox_records[0]
        print(f"[SUCCESS] Found Outbound Delivery Log in DB:")
        print(f"  - Subject: '{rec.get('subject')}'")
        print(f"  - To: {rec.get('to')}")
        print(f"  - Status: '{rec.get('status')}'")
        print(f"  - Sent At: {rec.get('created_at')}")
    else:
        print("[ERROR] No Outbound Log record found in DB for this sender.")

    print("\n" + "=" * 60)
    print(" Local SMTP Tests Complete! ".center(60, "*"))
    print("=" * 60)

if __name__ == "__main__":
    main()
