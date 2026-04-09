import imaplib
import smtplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.header import decode_header
import os
from config import load_config


def _decode_header_value(value):
    """Decode an email header value."""
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _get_email_body(msg):
    """Extract email body (prefer HTML, fallback to plain text)."""
    body_html = ""
    body_text = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in content_disposition:
                continue

            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body_html = payload.decode(charset, errors="replace")
            elif content_type == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body_text = payload.decode(charset, errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        if content_type == "text/html":
            body_html = payload.decode(charset, errors="replace")
        else:
            body_text = payload.decode(charset, errors="replace")

    return body_html or f"<pre>{body_text}</pre>"


def _get_attachments(msg):
    """Extract attachments from email message."""
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    filename = _decode_header_value(filename)
                    content = part.get_payload(decode=True)
                    attachments.append({
                        "filename": filename,
                        "content": content,
                        "size": len(content) if content else 0,
                    })
    return attachments


def _parse_bodystructure_attachments(resp_text):
    """Extract attachment filenames and sizes from a raw BODYSTRUCTURE response.

    This is a best-effort regex parser - IMAP bodystructure is complex but for
    our scan-view needs (just showing filename + size) a regex is sufficient.
    Returns a list of {filename, size, content=None}.
    """
    import re as _re
    attachments = []
    # Look for attachment disposition entries. Example fragment:
    # ("ATTACHMENT" ("FILENAME" "doc.pdf")) ... 12345
    # Or filename in content-type: ("NAME" "doc.pdf")
    # Match both FILENAME and NAME parameters
    filename_matches = _re.findall(
        r'"(?:FILENAME|NAME)"\s+"([^"]+)"',
        resp_text,
        _re.IGNORECASE,
    )
    # Deduplicate while preserving order
    seen = set()
    for fn in filename_matches:
        decoded = fn
        # Try to decode RFC 2047 encoded-words if present
        try:
            from email.header import decode_header as _dh
            parts = _dh(fn)
            decoded = "".join(
                (p.decode(enc or "utf-8", errors="replace") if isinstance(p, bytes) else p)
                for p, enc in parts
            )
        except Exception:
            pass
        if decoded not in seen:
            seen.add(decoded)
            attachments.append({"filename": decoded, "size": 0, "content": None})
    return attachments


def fetch_emails(max_count=20, unread_only=True, days_back=None, headers_only=False):
    """Fetch emails from the configured IMAP inbox.

    Args:
        max_count: maximum number of emails to return
        unread_only: only fetch unread (UNSEEN) emails
        days_back: if set, only fetch emails newer than N days ago
        headers_only: if True, only fetch headers (fast - no bodies or attachment content).
                      Use for scan view; use full fetch only for import.

    Returns a list of dicts with: message_id, subject, sender, sender_email,
    date, body_html, attachments (list of {filename, content, size}).
    In headers_only mode, body_html is empty and attachments have no content.
    """
    config = load_config()
    if not config.get("email_address") or not config.get("email_password"):
        raise ValueError("Email credentials not configured. Go to Settings.")

    mail = imaplib.IMAP4_SSL(config["imap_server"], config["imap_port"])
    mail.login(config["email_address"], config["email_password"])
    mail.select("INBOX")

    # Build IMAP search criteria. IMAP date format: DD-Mon-YYYY (no quotes).
    # Multiple criteria need to be passed as separate args to mail.search.
    search_args = []
    if unread_only:
        search_args.append("UNSEEN")
    if days_back is not None and days_back > 0:
        from datetime import datetime, timedelta
        since_date = (datetime.now() - timedelta(days=int(days_back))).strftime("%d-%b-%Y")
        search_args.extend(["SINCE", since_date])

    if not search_args:
        search_args = ["ALL"]

    import time as _time
    try:
        import applog
    except Exception:
        applog = None

    def _log(*args):
        if applog:
            applog.info("[email_service]", *args)
        else:
            print("[email_service]", *args)

    t_search = _time.time()
    _log(f"IMAP search: {search_args}, headers_only={headers_only}")
    status, message_ids = mail.search(None, *search_args)
    _log(f"search took {_time.time()-t_search:.2f}s, status={status}")

    if status != "OK":
        mail.logout()
        return []

    ids = message_ids[0].split()
    # Take the most recent ones (newest first)
    ids = ids[-max_count:] if len(ids) > max_count else ids
    ids_newest_first = list(reversed(ids))

    if not ids_newest_first:
        mail.logout()
        return []

    # In headers mode, fetch only essential headers + bodystructure for ALL ids in a SINGLE batch
    # This is dramatically faster than per-message fetches (1 round trip vs N).
    # Only fetch the headers we actually need.
    if headers_only:
        fetch_spec = "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] BODYSTRUCTURE)"
    else:
        fetch_spec = "(RFC822)"

    msg_set = b",".join(ids_newest_first).decode("ascii")
    t_fetch = _time.time()
    _log(f"Batch fetching {len(ids_newest_first)} emails (headers_only={headers_only}, spec={fetch_spec})")
    status, msg_data = mail.fetch(msg_set, fetch_spec)
    _log(f"fetch took {_time.time()-t_fetch:.2f}s, status={status}, parts={len(msg_data) if msg_data else 0}")
    mail.logout()

    if status != "OK" or not msg_data:
        return []

    # msg_data is a list where each fetched message comes as one or more entries.
    # Tuples carry literal blocks (like the requested header bytes), bare bytes
    # carry the BODYSTRUCTURE / closing parens. We group entries per message by
    # detecting the ")" sentinel that ends each FETCH response.
    messages_raw = []
    current = []
    for item in msg_data:
        current.append(item)
        # End of one message: a bare bytes entry containing ")"
        if isinstance(item, bytes) and item.strip().endswith(b")"):
            messages_raw.append(current)
            current = []
    if current:
        messages_raw.append(current)

    emails = []
    for i, msg_parts in enumerate(messages_raw):
        try:
            # Combine all bytes for parsing both headers and bodystructure response
            header_bytes = b""
            full_resp = b""
            for part in msg_parts:
                if isinstance(part, tuple):
                    full_resp += part[0] + b" " + part[1]
                    if not header_bytes:
                        header_bytes = part[1]
                elif isinstance(part, bytes):
                    full_resp += part

            if headers_only:
                msg = email.message_from_bytes(header_bytes)
                body_html = ""
                try:
                    attachments = _parse_bodystructure_attachments(
                        full_resp.decode("utf-8", errors="replace")
                    )
                except Exception:
                    attachments = []
            else:
                # Full RFC822 mode
                raw_email = header_bytes
                msg = email.message_from_bytes(raw_email)
                body_html = _get_email_body(msg)
                attachments = _get_attachments(msg)

            subject = _decode_header_value(msg["Subject"])
            from_header = _decode_header_value(msg["From"])
            date_str = msg["Date"] or ""

            sender_name = from_header
            sender_email_addr = ""
            if "<" in from_header and ">" in from_header:
                sender_name = from_header.split("<")[0].strip().strip('"')
                sender_email_addr = from_header.split("<")[1].split(">")[0]
            else:
                sender_email_addr = from_header

            try:
                from email.utils import parsedate_to_datetime
                date_obj = parsedate_to_datetime(date_str)
                date_formatted = date_obj.strftime("%d/%m/%Y %H:%M")
            except Exception:
                date_formatted = date_str

            # Use sequence id from our list (matches the order of msg_set)
            msg_id = ids_newest_first[i].decode() if i < len(ids_newest_first) else ""

            emails.append({
                "message_id": msg_id,
                "subject": subject,
                "sender_name": sender_name,
                "sender_email": sender_email_addr,
                "date": date_formatted,
                "body_html": body_html,
                "attachments": [
                    {
                        "filename": a.get("filename", ""),
                        "size": a.get("size", 0),
                        "content": a.get("content"),
                    }
                    for a in attachments
                ],
            })
        except Exception as e:
            print(f"[email_service] Error parsing message {i}: {e}")
            continue

    return emails


def mark_as_read(message_id):
    """Mark a specific email as read."""
    config = load_config()
    mail = imaplib.IMAP4_SSL(config["imap_server"], config["imap_port"])
    mail.login(config["email_address"], config["email_password"])
    mail.select("INBOX")
    mail.store(message_id.encode(), "+FLAGS", "\\Seen")
    mail.logout()


def send_email(to_address, subject, body_html, attachment_paths=None):
    """Send an email with optional attachments via SMTP."""
    config = load_config()
    if not config.get("email_address") or not config.get("email_password"):
        raise ValueError("Email credentials not configured. Go to Settings.")

    msg = MIMEMultipart()
    msg["From"] = config["email_address"]
    msg["To"] = to_address
    msg["Subject"] = subject

    msg.attach(MIMEText(body_html, "html", "utf-8"))

    if attachment_paths:
        for filepath in attachment_paths:
            if not os.path.exists(filepath):
                continue
            filename = os.path.basename(filepath)
            with open(filepath, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{filename}"',
                )
                msg.attach(part)

    with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
        server.starttls()
        server.login(config["email_address"], config["email_password"])
        server.send_message(msg)


def test_connection():
    """Test IMAP connection with current credentials."""
    config = load_config()
    if not config.get("email_address") or not config.get("email_password"):
        return False, "Email credentials not configured"
    try:
        mail = imaplib.IMAP4_SSL(config["imap_server"], config["imap_port"])
        mail.login(config["email_address"], config["email_password"])
        mail.logout()
        return True, "Connection successful"
    except imaplib.IMAP4.error as e:
        msg = str(e)
        if "AUTHENTICATIONFAILED" in msg or "Invalid credentials" in msg:
            return False, "שם משתמש או סיסמה שגויים. ודא שאתה משתמש ב-App Password ולא בסיסמה הרגילה של Gmail."
        return False, msg
    except Exception as e:
        return False, str(e)
