"""Yandex Mail IMAP API router."""
import asyncio
from typing import List, Dict, Any, Optional
import imaplib
import smtplib
import base64
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()

from app.transport.routers.attachments import store_attachment, AttachmentDTO


class EmailMessage(BaseModel):
    """Email message model."""
    id: str
    subject: str
    from_email: str
    to_email: str
    date: str
    body: str
    status: str = "received"
    attachments_count: int = 0
    is_read: bool = False


class IMAPRequest(BaseModel):
    """IMAP request model."""
    access_token: str
    email: str
    limit: int = 20
    folder: str = "INBOX"


class IMAPMessageRequest(BaseModel):
    access_token: str
    email: str
    folder: str = "INBOX"


class IMAPMoveRequest(BaseModel):
    access_token: str
    email: str
    source_folder: str = "SPAM"
    target_folder: str = "INBOX"


class IMAPFoldersRequest(BaseModel):
    access_token: str
    email: str


class SMTPRequest(BaseModel):
    access_token: str
    email: str
    to_email: str
    subject: str
    body: str


async def send_yandex_email_smtp_multi(*, email_addr: str, access_token: str, to_emails: list[str], subject: str, body: str) -> dict:
    def _build_xoauth2_string(user: str, token: str) -> str:
        return f"user={user}\x01auth=Bearer {token}\x01\x01"

    def _parse_list_line(line: bytes) -> tuple[list[str], str] | None:
        try:
            raw = line.decode("utf-8", errors="ignore")
            m = re.match(r"^\((?P<flags>[^)]*)\)\s+\"?[^\"]*\"?\s+(?P<name>.*)$", raw)
            if not m:
                return None
            flags_part = (m.group("flags") or "").strip()
            name_part = (m.group("name") or "").strip()
            if name_part.startswith('"') and name_part.endswith('"') and len(name_part) >= 2:
                name_part = name_part[1:-1]
            flags = [f.strip() for f in flags_part.split() if f.strip()]
            return flags, name_part
        except Exception:
            return None

    def _resolve_sent_mailbox(email_addr_local: str, access_token_local: str) -> str:
        imap_client = None
        try:
            imap_client = imaplib.IMAP4_SSL("imap.yandex.ru", 993, timeout=15)

            def auth_string(_challenge: bytes | None = None):
                return _build_xoauth2_string(email_addr_local, access_token_local)

            res, _ = imap_client.authenticate("XOAUTH2", auth_string)
            if res != "OK":
                return "Sent"

            res, data = imap_client.list()
            if res != "OK" or not data:
                return "Sent"

            for item in data:
                if not item:
                    continue
                parsed = _parse_list_line(item)
                if not parsed:
                    continue
                flags, mailbox = parsed
                if any(f.lower() == "\\sent" for f in flags):
                    return mailbox

            return "Sent"
        except Exception:
            return "Sent"
        finally:
            if imap_client is not None:
                try:
                    imap_client.logout()
                except Exception:
                    pass

    def _append_to_sent(email_addr_local: str, access_token_local: str, mailbox: str, rfc822_bytes: bytes) -> None:
        imap_client = None
        try:
            imap_client = imaplib.IMAP4_SSL("imap.yandex.ru", 993, timeout=15)

            def auth_string(_challenge: bytes | None = None):
                return _build_xoauth2_string(email_addr_local, access_token_local)

            res, _ = imap_client.authenticate("XOAUTH2", auth_string)
            if res != "OK":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="IMAP auth failed")

            date_time = imaplib.Time2Internaldate(datetime.utcnow().timestamp())
            res, _ = imap_client.append(mailbox, "\\Seen", date_time, rfc822_bytes)
            if res != "OK":
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"IMAP APPEND failed: {res}")
        finally:
            if imap_client is not None:
                try:
                    imap_client.logout()
                except Exception:
                    pass

    def _send_sync() -> dict:
        SMTP_SERVER = "smtp.yandex.ru"
        SMTP_PORT = 465
        SMTP_TIMEOUT = 15

        to_list = [str(x or "").strip() for x in (to_emails or []) if str(x or "").strip()]
        if not to_list or not subject or not body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required fields")

        msg = MIMEMultipart()
        msg["From"] = email_addr
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = subject
        msg["Date"] = email.utils.format_datetime(datetime.now().astimezone())
        msg.attach(MIMEText(body, "plain", "utf-8"))

        auth_string = _build_xoauth2_string(email_addr, access_token)
        auth_b64 = base64.b64encode(auth_string.encode("utf-8")).decode("ascii")

        server = None
        try:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=SMTP_TIMEOUT)
            code, resp = server.docmd("AUTH", "XOAUTH2 " + auth_b64)
            if code != 235:
                resp_text = resp.decode("utf-8", errors="ignore") if isinstance(resp, (bytes, bytearray)) else str(resp)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"SMTP XOAUTH2 auth failed: {code} - {resp_text}",
                )

            rfc822 = msg.as_bytes()
            server.sendmail(email_addr, to_list, rfc822)

            sent_mailbox = _resolve_sent_mailbox(email_addr, access_token)
            _append_to_sent(email_addr, access_token, sent_mailbox, rfc822)
            return {"success": True, "appended_to_sent": True, "sent_mailbox": sent_mailbox, "recipients": len(to_list)}
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass

    return await asyncio.wait_for(asyncio.to_thread(_send_sync), timeout=20)



def decode_mime_words(s):
    """Decode MIME encoded words."""
    try:
        decoded_parts = decode_header(s)
        decoded_string = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    decoded_string += part.decode(encoding)
                else:
                    decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += part
        return decoded_string
    except:
        return str(s)


def get_email_address(msg, field):
    """Extract email address from message field."""
    try:
        header_field = msg.get(field, "")
        if header_field:
            match = re.search(r'<(.+?)>', header_field)
            if match:
                return match.group(1)
            return header_field
        return ""
    except:
        return ""


def _extract_message_bodies(msg: email.message.Message) -> tuple[str, str]:
    text_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="ignore")
            except Exception:
                decoded = payload.decode("utf-8", errors="ignore")

            if content_type == "text/plain" and not text_body:
                text_body = decoded
            elif content_type == "text/html" and not html_body:
                html_body = decoded
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="ignore")
            except Exception:
                decoded = payload.decode("utf-8", errors="ignore")
            if msg.get_content_type() == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    return text_body, html_body


def _extract_fetch_bytes(msg_data: list[Any]) -> bytes:
    """Extract raw bytes payload from IMAP FETCH response."""
    if not msg_data:
        raise ValueError("Empty FETCH response")

    for item in msg_data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])

    raise ValueError("Unable to find bytes payload in FETCH response")


def _extract_fetch_section_bytes(msg_data: list[Any], needle: bytes) -> bytes | None:
    """Extract bytes payload for a specific IMAP FETCH section (by matching needle in item[0])."""
    for item in msg_data:
        if (
            isinstance(item, tuple)
            and len(item) >= 2
            and isinstance(item[0], (bytes, bytearray))
            and isinstance(item[1], (bytes, bytearray))
        ):
            if needle in bytes(item[0]):
                return bytes(item[1])
    return None


@router.post("/mail/yandex/imap/folders")
async def fetch_yandex_folders_status(request: IMAPFoldersRequest):
    """Return folder counters and mailbox mapping using IMAP LIST + STATUS."""

    def _parse_list_line(line: bytes) -> tuple[list[str], str] | None:
        try:
            raw = line.decode("utf-8", errors="ignore")
            m = re.match(r"^\((?P<flags>[^)]*)\)\s+\"?[^\"]*\"?\s+(?P<name>.*)$", raw)
            if not m:
                return None
            flags_part = (m.group("flags") or "").strip()
            name_part = (m.group("name") or "").strip()
            # mailbox name can be quoted
            if name_part.startswith('"') and name_part.endswith('"') and len(name_part) >= 2:
                name_part = name_part[1:-1]
            flags = [f.strip() for f in flags_part.split() if f.strip()]
            return flags, name_part
        except Exception:
            return None

    def _normalize_role(flags: list[str], name: str) -> str | None:
        fset = {f.lower() for f in flags}
        lname = name.lower()
        if "\\inbox" in fset or lname == "inbox":
            return "inbox"
        if "\\sent" in fset or "sent" == lname or "отправ" in lname:
            return "sent"
        if "\\junk" in fset or "\\spam" in fset or "spam" == lname or "спам" in lname:
            return "spam"
        if "\\trash" in fset or "trash" == lname or "корз" in lname or "удален" in lname:
            return "trash"
        return None

    def _fetch_sync() -> dict:
        imap_client = None
        try:
            IMAP_SERVER = "imap.yandex.ru"
            IMAP_PORT = 993
            IMAP_TIMEOUT = 30
            imap_client = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=IMAP_TIMEOUT)

            def auth_string(_challenge: bytes | None = None):
                return f"user={request.email}\x01auth=Bearer {request.access_token}\x01\x01"

            result, _data = imap_client.authenticate("XOAUTH2", auth_string)
            if result != "OK":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="IMAP authentication failed")

            result, data = imap_client.list()
            if result != "OK" or not data:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="IMAP LIST failed")

            role_to_mailbox: dict[str, str] = {}
            for item in data:
                if not item:
                    continue
                parsed = _parse_list_line(item)
                if not parsed:
                    continue
                flags, mailbox = parsed
                role = _normalize_role(flags, mailbox)
                if role and role not in role_to_mailbox:
                    role_to_mailbox[role] = mailbox

            # Fallbacks if server didn't provide flags
            role_to_mailbox.setdefault("inbox", "INBOX")
            role_to_mailbox.setdefault("spam", "SPAM")
            role_to_mailbox.setdefault("sent", "Sent")
            role_to_mailbox.setdefault("trash", "Trash")

            folders: dict[str, dict[str, Any]] = {}
            for role, mailbox in role_to_mailbox.items():
                try:
                    st_res, st_data = imap_client.status(mailbox, "(MESSAGES UNSEEN)")
                    total = 0
                    unseen = 0
                    if st_res == "OK" and st_data and st_data[0]:
                        raw = st_data[0].decode("utf-8", errors="ignore")
                        m_total = re.search(r"MESSAGES\s+(\d+)", raw)
                        m_unseen = re.search(r"UNSEEN\s+(\d+)", raw)
                        if m_total:
                            total = int(m_total.group(1))
                        if m_unseen:
                            unseen = int(m_unseen.group(1))
                    folders[role] = {
                        "mailbox": mailbox,
                        "total": total,
                        "unseen": unseen,
                    }
                except Exception:
                    folders[role] = {
                        "mailbox": mailbox,
                        "total": 0,
                        "unseen": 0,
                    }

            return {
                "folders": folders,
            }
        finally:
            if imap_client is not None:
                try:
                    imap_client.logout()
                except Exception:
                    pass

    try:
        return await asyncio.wait_for(asyncio.to_thread(_fetch_sync), timeout=12)
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="IMAP folders request timeout")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"IMAP folders error: {str(e)}")


@router.post("/mail/yandex/smtp/send")
async def send_yandex_email_smtp(request: SMTPRequest):
    """Send email via Yandex SMTP using OAuth2 (XOAUTH2)."""

    try:
        return await send_yandex_email_smtp_multi(
            email_addr=str(request.email),
            access_token=str(request.access_token),
            to_emails=[str(request.to_email)],
            subject=str(request.subject),
            body=str(request.body),
        )
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="SMTP send timeout")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"SMTP send error: {str(e)}")


@router.post("/mail/yandex/imap")
async def fetch_yandex_emails_imap(request: IMAPRequest):
    """Fetch emails from Yandex using IMAP with OAuth2 token."""
    def _fetch_sync() -> dict:
        imap_client = None
        try:
            # Yandex IMAP settings
            IMAP_SERVER = "imap.yandex.ru"
            IMAP_PORT = 993
            IMAP_TIMEOUT = 30

            # Connect to IMAP server
            imap_client = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=IMAP_TIMEOUT)

            # Authenticate using OAuth2 token
            def auth_string(_challenge: bytes | None = None):
                return f"user={request.email}\x01auth=Bearer {request.access_token}\x01\x01"

            try:
                result, _data = imap_client.authenticate("XOAUTH2", auth_string)
                if result != "OK":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="IMAP authentication failed",
                    )
            except Exception as auth_error:
                print(f"OAuth2 auth failed: {auth_error}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"IMAP authentication failed: {auth_error}",
                )

            # Select folder
            sel_res, _sel_data = imap_client.select(request.folder)
            if sel_res != "OK":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"IMAP select failed for folder: {request.folder}",
                )

            # Get message ids (prefer SORT for performance on large mailboxes)
            email_ids: list[bytes] = []
            try:
                result, data = imap_client.sort("REVERSE DATE", "UTF-8", "ALL")
                if result == "OK" and data and data[0]:
                    email_ids = data[0].split()
            except Exception:
                email_ids = []

            if not email_ids:
                # Try limiting search window first to avoid scanning very large mailboxes
                try:
                    since_date = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
                    result, data = imap_client.search(None, "SINCE", since_date)
                    if result == "OK" and data and data[0]:
                        email_ids = data[0].split()
                except Exception:
                    email_ids = []

            if not email_ids:
                result, data = imap_client.search(None, "ALL")
                if result != "OK":
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to search emails",
                    )
                email_ids = data[0].split()
            emails = []

            # Limit number of emails
            email_ids = email_ids[-request.limit:] if len(email_ids) > request.limit else email_ids

            for email_id in reversed(email_ids):
                try:
                    # headers + flags + small text preview for list
                    result, msg_data = imap_client.fetch(email_id, "(BODY.PEEK[HEADER] FLAGS BODY.PEEK[TEXT]<0.2048>)")
                    if result != "OK":
                        continue

                    raw_headers = _extract_fetch_section_bytes(msg_data, b"BODY[HEADER]")
                    if raw_headers is None:
                        try:
                            raw_headers = _extract_fetch_bytes(msg_data)
                        except Exception:
                            continue

                    msg = email.message_from_bytes(raw_headers)

                    subject = decode_mime_words(msg.get("Subject", "(Без темы)"))
                    from_email = get_email_address(msg, "From")
                    to_email = get_email_address(msg, "To")

                    date_str = msg.get("Date", "")
                    try:
                        if date_str:
                            date_obj = email.utils.parsedate_to_datetime(date_str)
                            date_iso = date_obj.isoformat()
                        else:
                            date_iso = datetime.now().isoformat()
                    except Exception:
                        date_iso = datetime.now().isoformat()

                    # Try to extract preview from BODY[TEXT] snippet
                    snippet_bytes = _extract_fetch_section_bytes(msg_data, b"BODY[TEXT]")
                    if snippet_bytes:
                        try:
                            body = snippet_bytes.decode("utf-8", errors="ignore").strip()
                        except Exception:
                            body = ""
                    else:
                        # Try BODY[1] (first part) if TEXT is empty (common for HTML/multipart)
                        snippet_bytes = _extract_fetch_section_bytes(msg_data, b"BODY[1]")
                        if snippet_bytes:
                            try:
                                body = snippet_bytes.decode("utf-8", errors="ignore").strip()
                            except Exception:
                                body = ""
                        else:
                            # Fallback: fetch first 2KB of full message for preview
                            try:
                                result_preview, preview_data = imap_client.fetch(email_id, "(BODY.PEEK[TEXT]<0.2048>)")
                                if result_preview == "OK" and preview_data:
                                    preview_raw = _extract_fetch_bytes(preview_data)
                                    if preview_raw:
                                        body = preview_raw.decode("utf-8", errors="ignore").strip()
                                else:
                                    body = ""
                            except Exception:
                                body = ""

                    # If still empty, try to extract from RFC822 small slice as last resort
                    if not body:
                        try:
                            result_full, full_data = imap_client.fetch(email_id, "(RFC822)<0.2048>")
                            if result_full == "OK" and full_data:
                                full_raw = _extract_fetch_bytes(full_data)
                                if full_raw:
                                    body = full_raw.decode("utf-8", errors="ignore").strip()
                            else:
                                body = ""
                        except Exception:
                            body = ""

                    # Clean up common HTML tags for preview (optional)
                    if body and "<" in body:
                        import re
                        body = re.sub(r"<[^>]+>", " ", body)
                        body = re.sub(r"\s+", " ", body).strip()

                    if len(body) > 400:
                        body = body[:400]

                    attachments_count = 0

                    # Determine read/unread via FLAGS
                    is_read = False
                    for item in msg_data:
                        if isinstance(item, tuple) and item and isinstance(item[0], (bytes, bytearray)):
                            flags_raw = bytes(item[0])
                            if b"\\\\Seen" in flags_raw or b"\\Seen" in flags_raw:
                                is_read = True
                                break

                    email_message = EmailMessage(
                        id=str(email_id.decode("utf-8")),
                        subject=subject,
                        from_email=from_email,
                        to_email=to_email,
                        date=date_iso,
                        body=body,
                        status="received",
                        attachments_count=attachments_count,
                        is_read=is_read,
                    )

                    emails.append(email_message)
                except Exception as e:
                    print(f"Error parsing email {email_id}: {e}")
                    continue

            try:
                imap_client.close()
            except Exception:
                pass
            try:
                imap_client.logout()
            except Exception:
                pass

            return {
                "messages": emails,
                "total": len(emails),
                "folder": request.folder,
            }
        finally:
            if imap_client is not None:
                try:
                    imap_client.logout()
                except Exception:
                    pass

    try:
        return await asyncio.wait_for(asyncio.to_thread(_fetch_sync), timeout=25)
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="IMAP request timeout")
    except Exception as e:
        print(f"IMAP error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"IMAP error: {str(e)}",
        )


@router.post("/mail/yandex/imap/{message_id}")
async def fetch_yandex_email_imap_message(message_id: str, request: IMAPMessageRequest):
    def _fetch_sync() -> dict:
        imap_client = None
        try:
            IMAP_SERVER = "imap.yandex.ru"
            IMAP_PORT = 993
            IMAP_TIMEOUT = 30

            imap_client = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=IMAP_TIMEOUT)

            def auth_string(_challenge: bytes | None = None):
                return f"user={request.email}\x01auth=Bearer {request.access_token}\x01\x01"

            try:
                result, _data = imap_client.authenticate("XOAUTH2", auth_string)
                if result != "OK":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="IMAP authentication failed",
                    )
            except Exception as auth_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"IMAP authentication failed: {auth_error}",
                )

            imap_client.select(request.folder)

            result, msg_data = imap_client.fetch(message_id, "(RFC822)")
            if result != "OK":
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="IMAP fetch failed")

            try:
                raw_email = _extract_fetch_bytes(msg_data)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Message not found",
                )
            except Exception as fetch_error:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"IMAP fetch parse error: {fetch_error}",
                )

            try:
                msg = email.message_from_bytes(raw_email)
            except Exception as parse_error:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to parse email: {parse_error}",
                )

            subject = decode_mime_words(msg.get("Subject", "(Без темы)"))
            from_email = get_email_address(msg, "From")
            to_email = get_email_address(msg, "To")

            date_str = msg.get("Date", "")
            try:
                if date_str:
                    date_obj = email.utils.parsedate_to_datetime(date_str)
                    date_iso = date_obj.isoformat()
                else:
                    date_iso = datetime.now().isoformat()
            except Exception:
                date_iso = datetime.now().isoformat()

            text_body, html_body = _extract_message_bodies(msg)

            attachments: list[AttachmentDTO] = []
            try:
                for part in msg.walk():
                    if part.get_content_maintype() == "multipart":
                        continue

                    content_disposition = part.get_content_disposition()
                    filename = part.get_filename()
                    if content_disposition != "attachment" and not filename:
                        continue

                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue

                    stored = store_attachment(
                        filename=decode_mime_words(filename or "attachment"),
                        content_type=part.get_content_type(),
                        data=payload,
                    )
                    attachments.append(stored)
            except Exception:
                attachments = []

            return {
                "id": message_id,
                "subject": subject,
                "from_email": from_email,
                "to_email": to_email,
                "date": date_iso,
                "body": text_body,
                "html": html_body,
                "attachments": attachments,
                "attachments_count": len(attachments),
            }
        finally:
            if imap_client is not None:
                try:
                    imap_client.logout()
                except Exception:
                    pass

    try:
        return await asyncio.wait_for(asyncio.to_thread(_fetch_sync), timeout=18)
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="IMAP request timeout",
        )


@router.post("/mail/yandex/imap/{message_id}/unspam")
async def unspam_yandex_email_imap_message(message_id: str, request: IMAPMoveRequest):
    def _move_sync() -> dict:
        imap_client = None
        try:
            IMAP_SERVER = "imap.yandex.ru"
            IMAP_PORT = 993
            IMAP_TIMEOUT = 30

            imap_client = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=IMAP_TIMEOUT)

            def auth_string(_challenge: bytes | None = None):
                return f"user={request.email}\x01auth=Bearer {request.access_token}\x01\x01"

            result, _data = imap_client.authenticate("XOAUTH2", auth_string)
            if result != "OK":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="IMAP authentication failed")

            sel_res, _ = imap_client.select(request.source_folder)
            if sel_res != "OK":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"IMAP select failed: {request.source_folder}")

            copy_res, _ = imap_client.copy(message_id, request.target_folder)
            if copy_res != "OK":
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="IMAP copy failed")

            store_res, _ = imap_client.store(message_id, "+FLAGS.SILENT", "(\\Deleted)")
            if store_res != "OK":
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="IMAP store (delete flag) failed")

            exp_res, _ = imap_client.expunge()
            if exp_res != "OK":
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="IMAP expunge failed")

            return {"success": True, "moved": True, "from": request.source_folder, "to": request.target_folder}
        finally:
            if imap_client is not None:
                try:
                    imap_client.logout()
                except Exception:
                    pass

    try:
        return await asyncio.wait_for(asyncio.to_thread(_move_sync), timeout=18)
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="IMAP request timeout")


@router.get("/mail/yandex/test")
async def test_imap_connection():
    """Test IMAP connection to Yandex."""
    try:
        IMAP_SERVER = "imap.yandex.ru"
        IMAP_PORT = 993
        
        # Test connection
        imap_client = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        
        # Try to get capabilities
        capabilities = imap_client.capabilities
        
        imap_client.logout()
        
        return {
            "status": "connected",
            "server": IMAP_SERVER,
            "port": IMAP_PORT,
            "capabilities": list(capabilities)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"IMAP connection test failed: {str(e)}"
        )
