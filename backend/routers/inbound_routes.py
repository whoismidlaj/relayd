"""
Inbound routes — reads mail directly from Dovecot via IMAP.
All email storage lives exclusively in Dovecot Maildir; MongoDB is NOT used here.
"""
import os
import asyncio
import email
import logging
from email import policy as email_policy
from email.parser import BytesParser
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_current_user

logger = logging.getLogger("relayd")

router = APIRouter(prefix="/inbound", tags=["inbound"])

# ---------------------------------------------------------------------------
# IMAP helpers (using the stdlib imaplib wrapped in asyncio executor)
# ---------------------------------------------------------------------------

IMAP_HOST = os.environ.get("DOVECOT_HOST", "dovecot")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))

# Dovecot passwd-file uses {PLAIN} passwords → we read them from MongoDB mailboxes
async def _get_mailbox_password(email_address: str) -> str | None:
    """Retrieve the plaintext password for an IMAP login from our MongoDB mailboxes collection."""
    try:
        from server import db
        doc = await db.mailboxes.find_one({"address": email_address}, {"_id": 0, "password_hash": 1})
        if doc:
            return doc.get("password_hash", "")  # stored as {PLAIN}xxx
    except Exception as e:
        logger.warning(f"Could not look up mailbox password for {email_address}: {e}")
    return None


def _strip_plain_prefix(pw: str) -> str:
    """Remove the {PLAIN} prefix that Dovecot passwd-file uses."""
    if pw.startswith("{PLAIN}"):
        return pw[len("{PLAIN}"):]
    return pw


def _imap_connect_ssl(host: str, port: int):
    """Open a synchronous SSL IMAP connection (runs in thread pool)."""
    import imaplib, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return imaplib.IMAP4_SSL(host, port, ssl_context=ctx)


def _parse_flags(flags_str: bytes) -> list[str]:
    """Parse IMAP FLAGS string like b'(\\Seen \\Flagged)' → ['\\Seen', '\\Flagged']"""
    try:
        raw = flags_str.decode()
        inner = raw.strip().lstrip("(").rstrip(")")
        return inner.split() if inner.strip() else []
    except Exception:
        return []


def _fetch_folder_messages(host, port, email_address, password, folder="INBOX", limit=50):
    """
    Synchronous IMAP fetch — called in a thread pool executor.
    Returns a list of dicts with message metadata + text body preview.
    """
    import imaplib, ssl, email as emaillib
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    results = []
    try:
        conn = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        conn.login(email_address, password)
        status, data = conn.select(folder, readonly=True)
        if status != "OK":
            conn.logout()
            return results

        status, uids = conn.uid("search", None, "ALL")
        if status != "OK" or not uids[0]:
            conn.logout()
            return results

        uid_list = uids[0].split()
        # Most recent first, capped at limit
        uid_list = uid_list[::-1][:limit]

        for uid in uid_list:
            try:
                status, msg_data = conn.uid("fetch", uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)] BODY.PEEK[TEXT]<0.512>)")
                if status != "OK" or not msg_data or msg_data[0] is None:
                    continue

                # msg_data structure varies; parse robustly
                raw_headers = b""
                raw_body_preview = b""
                flags_str = b""
                for part in msg_data:
                    if isinstance(part, tuple):
                        descriptor = part[0].decode() if isinstance(part[0], bytes) else str(part[0])
                        content = part[1] if isinstance(part[1], bytes) else b""
                        if "HEADER" in descriptor:
                            raw_headers = content
                        elif "TEXT" in descriptor:
                            raw_body_preview = content
                        if "FLAGS" in descriptor:
                            # extract FLAGS from the descriptor string
                            import re
                            m = re.search(r"FLAGS \(([^)]*)\)", descriptor)
                            if m:
                                flags_str = m.group(1).encode()

                hdr = emaillib.message_from_bytes(raw_headers, policy=email_policy.compat32)
                msg_id_str = uid.decode()

                # Decode subject
                raw_subject = hdr.get("Subject", "(No Subject)")
                decoded_parts = emaillib.header.decode_header(raw_subject)
                subject = ""
                for part, enc in decoded_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(enc or "utf-8", errors="replace")
                    else:
                        subject += part

                # Decode From
                raw_from = hdr.get("From", "")
                from_parts = emaillib.header.decode_header(raw_from)
                from_addr = ""
                for part, enc in from_parts:
                    if isinstance(part, bytes):
                        from_addr += part.decode(enc or "utf-8", errors="replace")
                    else:
                        from_addr += part

                # Date
                date_str = hdr.get("Date", "")
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(date_str)
                    created_at = dt.isoformat()
                except Exception:
                    created_at = datetime.now(timezone.utc).isoformat()

                # Body preview (strip non-printable)
                try:
                    body_preview = raw_body_preview.decode("utf-8", errors="replace").strip()
                    body_preview = body_preview[:300]
                except Exception:
                    body_preview = ""

                flags = [f.decode() if isinstance(f, bytes) else f for f in flags_str.split()] if flags_str else []

                results.append({
                    "id": msg_id_str,
                    "uid": msg_id_str,
                    "folder": folder,
                    "from": from_addr,
                    "to": email_address,
                    "subject": subject,
                    "body": body_preview,
                    "created_at": created_at,
                    "read": "\\Seen" in flags,
                    "flags": flags,
                })
            except Exception as e:
                logger.warning(f"Failed to parse IMAP message uid={uid}: {e}")
                continue

        conn.logout()
    except Exception as e:
        logger.error(f"IMAP fetch failed for {email_address}@{host}: {e}")

    return results


def _fetch_full_message(host, port, email_address, password, uid, folder="INBOX"):
    """Fetch the full body of a single message by UID."""
    import imaplib, ssl, email as emaillib
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        conn = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        conn.login(email_address, password)
        conn.select(folder, readonly=False)

        status, msg_data = conn.uid("fetch", uid.encode(), "(FLAGS BODY[])")
        if status != "OK" or not msg_data or msg_data[0] is None:
            conn.logout()
            return None

        raw = b""
        flags = []
        for part in msg_data:
            if isinstance(part, tuple):
                descriptor = part[0].decode() if isinstance(part[0], bytes) else str(part[0])
                content = part[1] if isinstance(part[1], bytes) else b""
                raw = content
                import re
                m = re.search(r"FLAGS \(([^)]*)\)", descriptor)
                if m:
                    flags = m.group(1).split()

        if not raw:
            conn.logout()
            return None

        # Mark as read
        conn.uid("store", uid.encode(), "+FLAGS", "\\Seen")
        conn.logout()

        hdr = emaillib.message_from_bytes(raw, policy=email_policy.compat32)

        # Full body extraction
        parsed = BytesParser(policy=email_policy.default).parsebytes(raw)
        body_text = ""
        body_html = ""
        try:
            plain_part = parsed.get_body(preferencelist=("plain",))
            if plain_part:
                body_text = plain_part.get_content()
        except Exception:
            pass
        try:
            html_part = parsed.get_body(preferencelist=("html",))
            if html_part:
                body_html = html_part.get_content()
        except Exception:
            pass

        # Decode subject
        raw_subject = hdr.get("Subject", "(No Subject)")
        decoded_parts = emaillib.header.decode_header(raw_subject)
        subject = ""
        for part, enc in decoded_parts:
            if isinstance(part, bytes):
                subject += part.decode(enc or "utf-8", errors="replace")
            else:
                subject += part

        raw_from = hdr.get("From", "")
        date_str = hdr.get("Date", "")
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            created_at = dt.isoformat()
        except Exception:
            created_at = datetime.now(timezone.utc).isoformat()

        return {
            "id": uid,
            "uid": uid,
            "folder": folder,
            "from": raw_from,
            "to": email_address,
            "subject": subject,
            "body": body_text or body_html or "",
            "body_html": body_html,
            "body_text": body_text,
            "created_at": created_at,
            "read": True,
            "flags": flags,
        }
    except Exception as e:
        logger.error(f"IMAP full fetch failed uid={uid}: {e}")
        return None


def _imap_delete(host, port, email_address, password, uid, folder="INBOX"):
    """Move a message to Trash or expunge it if already in Trash."""
    import imaplib, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        conn = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        conn.login(email_address, password)
        conn.select(folder, readonly=False)
        if folder == "Trash":
            conn.uid("store", uid.encode(), "+FLAGS", "\\Deleted")
            conn.expunge()
        else:
            conn.uid("copy", uid.encode(), "Trash")
            conn.uid("store", uid.encode(), "+FLAGS", "\\Deleted")
            conn.expunge()
        conn.logout()
        return True
    except Exception as e:
        logger.error(f"IMAP delete failed uid={uid}: {e}")
        return False


def _imap_move(host, port, email_address, password, uid, src_folder, dst_folder):
    """Move a message between IMAP folders."""
    import imaplib, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        conn = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        conn.login(email_address, password)
        conn.select(src_folder, readonly=False)
        conn.uid("copy", uid.encode(), dst_folder)
        conn.uid("store", uid.encode(), "+FLAGS", "\\Deleted")
        conn.expunge()
        conn.logout()
        return True
    except Exception as e:
        logger.error(f"IMAP move failed uid={uid} {src_folder}→{dst_folder}: {e}")
        return False


async def _get_imap_creds(user: dict):
    """
    Resolve IMAP credentials for the current user.
    Mailbox users log in as themselves. Admin users don't have a personal mailbox here.
    """
    if user.get("role") != "mailbox":
        raise HTTPException(status_code=403, detail="IMAP access is only available for mailbox users")
    email_address = user["email"]
    pw_hash = await _get_mailbox_password(email_address)
    if not pw_hash:
        raise HTTPException(status_code=500, detail="Could not resolve mailbox credentials")
    password = _strip_plain_prefix(pw_hash)
    return email_address, password


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/messages")
async def list_messages(
    user: dict = Depends(get_current_user),
    folder: str = Query("INBOX"),
    limit: int = Query(50, le=200),
):
    """
    List messages in a mailbox folder directly from Dovecot via IMAP.
    Folder aliases: inbox→INBOX, sent→Sent, trash→Trash, spam/junk→Junk
    """
    # Admin users — return empty list (they use delivery_logs for audit)
    if user.get("role") != "mailbox":
        from server import db
        query = {"user_id": user["id"]}
        # Return lightweight metadata records from delivery_logs for admin view
        items = await db.delivery_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        return items

    folder_map = {
        "inbox": "INBOX",
        "sent": "Sent",
        "trash": "Trash",
        "spam": "Junk",
        "junk": "Junk",
        "drafts": "Drafts",
    }
    imap_folder = folder_map.get(folder.lower(), folder)

    email_address, password = await _get_imap_creds(user)
    loop = asyncio.get_event_loop()
    messages = await loop.run_in_executor(
        None, _fetch_folder_messages, IMAP_HOST, IMAP_PORT, email_address, password, imap_folder, limit
    )
    return messages


@router.get("/messages/{uid}")
async def get_message(
    uid: str,
    folder: str = Query("INBOX"),
    user: dict = Depends(get_current_user),
):
    """Fetch and return the full content of a single message by IMAP UID. Marks it as read."""
    if user.get("role") != "mailbox":
        from server import db
        msg = await db.delivery_logs.find_one({"id": uid, "user_id": user["id"]}, {"_id": 0})
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        return msg

    folder_map = {
        "inbox": "INBOX", "sent": "Sent", "trash": "Trash",
        "spam": "Junk", "junk": "Junk", "drafts": "Drafts",
    }
    imap_folder = folder_map.get(folder.lower(), folder)

    email_address, password = await _get_imap_creds(user)
    loop = asyncio.get_event_loop()
    msg = await loop.run_in_executor(
        None, _fetch_full_message, IMAP_HOST, IMAP_PORT, email_address, password, uid, imap_folder
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


@router.delete("/messages/{uid}")
async def delete_message(
    uid: str,
    folder: str = Query("INBOX"),
    user: dict = Depends(get_current_user),
):
    """Delete (or trash) a message via IMAP."""
    if user.get("role") != "mailbox":
        raise HTTPException(status_code=403, detail="Not a mailbox user")

    folder_map = {
        "inbox": "INBOX", "sent": "Sent", "trash": "Trash",
        "spam": "Junk", "junk": "Junk",
    }
    imap_folder = folder_map.get(folder.lower(), folder)

    email_address, password = await _get_imap_creds(user)
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(
        None, _imap_delete, IMAP_HOST, IMAP_PORT, email_address, password, uid, imap_folder
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete message")
    return {"ok": True}


@router.post("/messages/{uid}/move")
async def move_message(
    uid: str,
    src: str = Query("INBOX"),
    dst: str = Query("Trash"),
    user: dict = Depends(get_current_user),
):
    """Move a message between folders (e.g. to Junk, Trash, or back to INBOX)."""
    if user.get("role") != "mailbox":
        raise HTTPException(status_code=403, detail="Not a mailbox user")

    folder_map = {
        "inbox": "INBOX", "sent": "Sent", "trash": "Trash",
        "spam": "Junk", "junk": "Junk",
    }
    src_folder = folder_map.get(src.lower(), src)
    dst_folder = folder_map.get(dst.lower(), dst)

    email_address, password = await _get_imap_creds(user)
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(
        None, _imap_move, IMAP_HOST, IMAP_PORT, email_address, password, uid, src_folder, dst_folder
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to move message")
    return {"ok": True}


@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    """Return unread/total counts for the mailbox from IMAP."""
    if user.get("role") != "mailbox":
        from server import db
        total = await db.delivery_logs.count_documents({"user_id": user["id"]})
        return {"total": total, "unread": 0}

    email_address, password = await _get_imap_creds(user)

    def _count():
        import imaplib, ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
            conn.login(email_address, password)
            _, data = conn.select("INBOX", readonly=True)
            total_str = data[0].decode() if data and data[0] else "0"
            total = int(total_str)
            _, unseen_data = conn.search(None, "UNSEEN")
            unread = len(unseen_data[0].split()) if unseen_data and unseen_data[0] else 0
            conn.logout()
            return {"total": total, "unread": unread}
        except Exception as e:
            logger.error(f"IMAP stats failed: {e}")
            return {"total": 0, "unread": 0}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _count)
