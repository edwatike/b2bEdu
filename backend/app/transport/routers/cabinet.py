"""Cabinet router for user cabinet functionality."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
from pydantic import BaseModel
import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.session import get_db
from app.transport.routers.auth import get_current_user
from app.usecases import start_parsing

logger = logging.getLogger(__name__)

router = APIRouter()


def _clean_cabinet_keys(keys: List[str]) -> List[str]:
    import re

    out: List[str] = []
    seen: set[str] = set()

    # Note: users sometimes paste OCR text with mixed Cyrillic/Latin letters (e.g., "шT"), so include [тt].
    unit_re = re.compile(r"\b(ш[тt]\.?\-?|шту?к\.?\-?|м2|м²|кг|г|т|тонн|п\.м|пог\.\s*м|мм|см|м)\b", re.IGNORECASE)
    unit_split_re = re.compile(r"\b(ш[тt]\.?\-?|шту?к\.?\-?|м2|м²|кг|г|т|тонн|п\.м|пог\.\s*м|мм|см|м)\b", re.IGNORECASE)
    money_re = re.compile(r"\b\d{1,3}(?:[\s\u00A0]\d{3})+(?:[\.,]\d{2})?\b")
    currency_re = re.compile(r"\b(руб\.?|р\.?|₽|eur|usd|\$|€)\b", re.IGNORECASE)
    percent_re = re.compile(r"\b\d{1,3}(?:[\.,]\d+)?\s*%\b")
    tech_re = re.compile(r"\b(?:dnid|dn|sn|pn|sdr|od|id|ø|d=|l=|len=|length=)\b", re.IGNORECASE)
    tech_split_re = re.compile(r"\b(?:dnid|dn|sn|pn|sdr|od|id|ø|d\s*=|l\s*=|len\s*=|length\s*=)\b", re.IGNORECASE)
    inn_kpp_re = re.compile(r"\b(инн|кпп|огрн|р/с|к/с|бик)\b", re.IGNORECASE)
    email_re = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
    url_re = re.compile(r"\bhttps?://\S+\b|\bwww\.\S+\b", re.IGNORECASE)
    header_like_re = re.compile(r"\b(счет\b|сч[её]т\s*№|итого\b|всего\b|к\s+оплате|ндс\b|условия\b|контакты\b)\b", re.IGNORECASE)

    def _strip_prefix(s: str) -> str:
        s = re.sub(r"^\s*№\s*\d+\s*", "", s)
        s = re.sub(r"^\s*\d{1,4}\s*[\)\.]\s*", "", s)
        s = re.sub(r"^\s*\d{1,4}\s+", "", s)
        return s.strip()

    for raw in keys or []:
        s = " ".join(str(raw or "").split())
        if not s:
            continue
        if header_like_re.search(s) or inn_kpp_re.search(s) or email_re.search(s) or url_re.search(s):
            continue

        m = money_re.search(s)
        if m:
            s = s[: m.start()].strip()
        m2 = currency_re.search(s)
        if m2:
            s = s[: m2.start()].strip()

        s = _strip_prefix(s)

        # Deterministic split: cut at the first unit marker or tech marker regardless of spacing/punctuation.
        m_u = unit_split_re.search(s)
        if m_u and m_u.start() >= 6:
            s = s[: m_u.start()].strip()
        m_t = tech_split_re.search(s)
        if m_t and m_t.start() >= 6:
            s = s[: m_t.start()].strip()
        m_p = percent_re.search(s)
        if m_p and m_p.start() >= 6:
            s = s[: m_p.start()].strip()
        parts = s.split()
        cut = len(parts)
        for i, tok in enumerate(parts):
            if i >= 2 and (unit_re.fullmatch(tok) or tech_re.search(tok) or percent_re.search(tok)):
                cut = min(cut, i)
                break
        if cut < len(parts):
            s = " ".join(parts[:cut]).strip()

        # Final guard: if it still looks like a spec/price line, keep only the left name tokens.
        digits = len(re.findall(r"\d", s))
        letters = len(re.findall(r"[A-Za-zА-Яа-я]", s))
        if len(s) > 30 and digits >= 10 and letters >= 6:
            toks = [t for t in s.split() if re.search(r"[A-Za-zА-Яа-я]", t)]
            if len(toks) >= 3:
                s = " ".join(toks[:7]).strip()

        if len(s) < 4:
            continue
        low = s.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(s)

    return out


_request_suppliers_state: Dict[int, Dict[int, dict]] = {}

# DTOs for cabinet functionality
class EmailMessageDTO(BaseModel):
    id: str
    subject: str
    from_email: str
    to_email: str
    status: str  # "sent", "replied", "waiting"
    date: str
    attachments_count: int = 0
    body: str = ""

class UserSettingsDTO(BaseModel):
    email: Optional[str] = None
    app_password: Optional[str] = None
    two_fa_enabled: bool = True
    organization_name: Optional[str] = None
    organization_verified: bool = False
    openai_api_key: Optional[str] = None
    openai_api_key_configured: bool = False
    groq_api_key: Optional[str] = None
    groq_api_key_configured: bool = False

class EmailComposeRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    attachments: Optional[List[str]] = []


class RequestSupplierItemDTO(BaseModel):
    supplier_id: int
    name: str
    email: Optional[str] = None
    emails: Optional[List[str]] = None
    phone: Optional[str] = None
    domain: Optional[str] = None
    status: str  # "waiting" | "sent" | "replied"
    last_error: Optional[str] = None


class RequestSupplierMessageDTO(BaseModel):
    id: str
    direction: str  # "out" | "in"
    subject: str
    body: str
    date: str


class SendRequestEmailPayload(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


class SendRequestEmailBulkPayload(BaseModel):
    supplier_ids: List[int]
    subject: Optional[str] = None
    body: Optional[str] = None


class SendRequestEmailBulkResultItemDTO(BaseModel):
    supplier_id: int
    ok: bool
    emails: List[str] = []
    error: Optional[str] = None


class SendRequestEmailBulkResponseDTO(BaseModel):
    total_suppliers: int
    total_emails: int
    batches_sent: int
    results: List[SendRequestEmailBulkResultItemDTO]


class CabinetParsingRequestDTO(BaseModel):
    id: int
    title: Optional[str] = None
    raw_keys_json: Optional[str] = None
    depth: Optional[int] = None
    source: Optional[str] = None
    comment: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_to_moderator: bool = False
    submitted_at: Optional[str] = None


async def _ensure_request_suppliers_loaded(*, db: AsyncSession, request_id: int) -> None:
    if int(request_id) in _request_suppliers_state:
        return

    # Lazy init with suppliers from moderator DB (MVP): suppliers with email
    from sqlalchemy import text

    # Note: We keep this endpoint simple for MVP.
    # Moderation UI owns supplier data; user request just references it.
    _request_suppliers_state[int(request_id)] = {}

    rows = []
    try:
        result = await db.execute(
            text(
                "SELECT id, name, email, phone, domain FROM moderator_suppliers "
                "WHERE email IS NOT NULL AND email <> '' ORDER BY updated_at DESC LIMIT 50"
            )
        )
        rows = result.fetchall() or []
    except Exception:
        rows = []

    # If moderator suppliers are empty/unavailable, provide a small demo set
    if not rows:
        rows = [
            (100001, "ООО Поставщик 1", "sales1@example.com", None, "supplier1.example.com"),
            (100002, "ООО Поставщик 2", "sales2@example.com", None, "supplier2.example.com"),
            (100003, "ООО Поставщик 3", "sales3@example.com", None, "supplier3.example.com"),
        ]

    import re

    def _split_emails(v: str | None) -> list[str]:
        raw = (v or "").strip()
        if not raw:
            return []
        parts = re.split(r"[;,\s]+", raw)
        out: list[str] = []
        seen: set[str] = set()
        for p in parts:
            s = (p or "").strip()
            if not s:
                continue
            low = s.lower()
            if low in seen:
                continue
            seen.add(low)
            out.append(s)
        return out

    for r in rows:
        sid = int(r[0])
        emails = _split_emails(r[2])
        _request_suppliers_state[int(request_id)][sid] = {
            "supplier_id": sid,
            "name": r[1] or "",
            "email": (emails[0] if emails else None),
            "emails": emails,
            "phone": r[3],
            "domain": r[4],
            "status": "waiting",
            "messages": [],
            "last_error": None,
        }


def _render_request_email_template(*, request_title: str, positions: List[str], supplier_name: str) -> tuple[str, str]:
    subject = f"Запрос КП: {request_title}" if request_title else "Запрос коммерческого предложения"
    positions_block = "\n".join([f"- {p}" for p in positions[:50]]) if positions else "- (позиции не указаны)"
    body = (
        f"Здравствуйте, {supplier_name or 'коллеги'}!\n\n"
        f"Просим направить коммерческое предложение по заявке: {request_title or '—'}\n\n"
        f"Состав заявки:\n{positions_block}\n\n"
        f"Спасибо!"
    )
    return subject, body


@router.get("/requests/{request_id}/suppliers", response_model=List[RequestSupplierItemDTO])
async def list_request_suppliers(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text

    user_id = int(current_user.get("id"))
    owned = await db.execute(
        text("SELECT id FROM parsing_requests WHERE id = :id AND created_by = :uid"),
        {"id": int(request_id), "uid": user_id},
    )
    if not owned.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    await _ensure_request_suppliers_loaded(db=db, request_id=int(request_id))
    items = list(_request_suppliers_state.get(int(request_id), {}).values())
    return [RequestSupplierItemDTO(**{k: v for k, v in it.items() if k != "messages"}) for it in items]


@router.post("/requests/{request_id}/suppliers/send-bulk", response_model=SendRequestEmailBulkResponseDTO)
async def send_request_email_to_suppliers_bulk(
    request_id: int,
    payload: SendRequestEmailBulkPayload,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    import json

    from app.transport.routers.mail import send_yandex_email_smtp_multi

    user_id = int(current_user.get("id"))
    owned = await db.execute(
        text("SELECT id, title, raw_keys_json FROM parsing_requests WHERE id = :id AND created_by = :uid"),
        {"id": int(request_id), "uid": user_id},
    )
    row = owned.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    # Fetch user's yandex OAuth data (sender identity)
    u = await db.execute(
        text("SELECT email, yandex_access_token FROM users WHERE id = :id"),
        {"id": user_id},
    )
    urow = u.fetchone()
    user_email = (urow[0] if urow else "") or ""
    yandex_access_token = (urow[1] if urow else "") or ""
    if not user_email.strip() or not yandex_access_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yandex mail is not connected for this user",
        )

    request_title = row[1] or ""
    positions: List[str] = []
    try:
        parsed = json.loads(row[2] or "[]")
        if isinstance(parsed, list):
            positions = [str(x) for x in parsed if str(x).strip()]
    except Exception:
        positions = []

    supplier_ids = [int(x) for x in (payload.supplier_ids or []) if str(x).strip()]
    supplier_ids = list(dict.fromkeys(supplier_ids))
    if not supplier_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="supplier_ids is required")

    await _ensure_request_suppliers_loaded(db=db, request_id=int(request_id))
    supplier_map = _request_suppliers_state.get(int(request_id), {})

    # Constraints
    max_emails_per_supplier = 10
    batch_size = 30

    # Prepare per-supplier emails
    results: list[SendRequestEmailBulkResultItemDTO] = []
    results_by_supplier: dict[int, SendRequestEmailBulkResultItemDTO] = {}
    all_emails: list[str] = []
    email_to_suppliers: dict[str, list[int]] = {}
    for sid in supplier_ids:
        supplier = supplier_map.get(int(sid))
        if not supplier:
            item = SendRequestEmailBulkResultItemDTO(supplier_id=int(sid), ok=False, emails=[], error="Supplier not found")
            results.append(item)
            results_by_supplier[int(sid)] = item
            continue

        emails = supplier.get("emails") or []
        if not isinstance(emails, list):
            emails = []
        emails = [str(e).strip() for e in emails if str(e).strip()][:max_emails_per_supplier]
        if not emails:
            item = SendRequestEmailBulkResultItemDTO(supplier_id=int(sid), ok=False, emails=[], error="Supplier has no email")
            results.append(item)
            results_by_supplier[int(sid)] = item
            supplier["last_error"] = "Supplier has no email"
            continue

        item = SendRequestEmailBulkResultItemDTO(supplier_id=int(sid), ok=True, emails=emails, error=None)
        results.append(item)
        results_by_supplier[int(sid)] = item
        for em in emails:
            low = em.lower()
            if low not in email_to_suppliers:
                email_to_suppliers[low] = []
            if int(sid) not in email_to_suppliers[low]:
                email_to_suppliers[low].append(int(sid))

    # Global email list (dedup)
    all_emails = [k for k in email_to_suppliers.keys()]
    total_emails = len(all_emails)

    subject_default, body_default = _render_request_email_template(
        request_title=str(request_title),
        positions=positions,
        supplier_name="коллеги",
    )
    subject = payload.subject.strip() if payload.subject and payload.subject.strip() else subject_default
    body = payload.body.strip() if payload.body and payload.body.strip() else body_default

    # Send in batches (one click -> multiple messages). Best-effort: a failed batch does not stop the rest.
    batches_sent = 0
    if all_emails:
        for i in range(0, len(all_emails), batch_size):
            batch = all_emails[i : i + batch_size]
            try:
                await send_yandex_email_smtp_multi(
                    email_addr=str(user_email),
                    access_token=str(yandex_access_token),
                    to_emails=[str(x) for x in batch],
                    subject=str(subject),
                    body=str(body),
                )
                batches_sent += 1
            except HTTPException as e:
                err = str(e.detail) if getattr(e, "detail", None) else "SMTP send failed"
                for em in batch:
                    for sid in email_to_suppliers.get(em.lower(), []):
                        supplier = supplier_map.get(int(sid))
                        if supplier:
                            supplier["last_error"] = err[:200]
                        item = results_by_supplier.get(int(sid))
                        if item:
                            item.ok = False
                            item.error = err[:200]
            except Exception as e:
                err = str(e)
                for em in batch:
                    for sid in email_to_suppliers.get(em.lower(), []):
                        supplier = supplier_map.get(int(sid))
                        if supplier:
                            supplier["last_error"] = err[:200]
                        item = results_by_supplier.get(int(sid))
                        if item:
                            item.ok = False
                            item.error = "SMTP send failed"

    # Update supplier states + add messages for successful suppliers
    for r in results:
        supplier = supplier_map.get(int(r.supplier_id))
        if not supplier:
            continue
        if not r.ok:
            continue
        msg = {
            "id": str(uuid.uuid4()),
            "direction": "out",
            "subject": subject,
            "body": body,
            "date": datetime.utcnow().isoformat(),
        }
        supplier.setdefault("messages", []).append(msg)
        supplier["status"] = "sent"
        supplier["last_error"] = None

    return SendRequestEmailBulkResponseDTO(
        total_suppliers=len(supplier_ids),
        total_emails=total_emails,
        batches_sent=batches_sent,
        results=results,
    )


@router.get("/requests/{request_id}/suppliers/{supplier_id}/messages", response_model=List[RequestSupplierMessageDTO])
async def get_request_supplier_messages(
    request_id: int,
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text

    user_id = int(current_user.get("id"))
    owned = await db.execute(
        text("SELECT id FROM parsing_requests WHERE id = :id AND created_by = :uid"),
        {"id": int(request_id), "uid": user_id},
    )
    if not owned.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    await _ensure_request_suppliers_loaded(db=db, request_id=int(request_id))
    supplier = _request_suppliers_state.get(int(request_id), {}).get(int(supplier_id))
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    messages = supplier.get("messages") or []
    return [RequestSupplierMessageDTO(**m) for m in messages]


@router.post("/requests/{request_id}/suppliers/{supplier_id}/send", response_model=RequestSupplierItemDTO)
async def send_request_email_to_supplier(
    request_id: int,
    supplier_id: int,
    payload: SendRequestEmailPayload,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    import json

    from app.transport.routers.mail import send_yandex_email_smtp_multi

    user_id = int(current_user.get("id"))
    owned = await db.execute(
        text("SELECT id, title, raw_keys_json FROM parsing_requests WHERE id = :id AND created_by = :uid"),
        {"id": int(request_id), "uid": user_id},
    )
    row = owned.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    request_title = row[1] or ""
    positions: List[str] = []
    try:
        parsed = json.loads(row[2] or "[]")
        if isinstance(parsed, list):
            positions = [str(x) for x in parsed if str(x).strip()]
    except Exception:
        positions = []

    await _ensure_request_suppliers_loaded(db=db, request_id=int(request_id))
    supplier = _request_suppliers_state.get(int(request_id), {}).get(int(supplier_id))
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    # Fetch user's yandex OAuth data (sender identity)
    u = await db.execute(
        text("SELECT email, yandex_access_token FROM users WHERE id = :id"),
        {"id": user_id},
    )
    urow = u.fetchone()
    user_email = (urow[0] if urow else "") or ""
    yandex_access_token = (urow[1] if urow else "") or ""
    if not user_email.strip() or not yandex_access_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yandex mail is not connected for this user",
        )

    emails = supplier.get("emails") or ([] if supplier.get("email") is None else [supplier.get("email")])
    if not isinstance(emails, list):
        emails = []
    emails = [str(e).strip() for e in emails if str(e).strip()][:10]
    if not emails:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier has no email")

    subject, body = _render_request_email_template(
        request_title=str(request_title),
        positions=positions,
        supplier_name=str(supplier.get("name") or ""),
    )

    if payload.subject and payload.subject.strip():
        subject = payload.subject.strip()
    if payload.body and payload.body.strip():
        body = payload.body.strip()

    try:
        await send_yandex_email_smtp_multi(
            email_addr=str(user_email),
            access_token=str(yandex_access_token),
            to_emails=[str(x) for x in emails],
            subject=str(subject),
            body=str(body),
        )
    except HTTPException as e:
        supplier["last_error"] = (str(e.detail) if getattr(e, "detail", None) else "SMTP send failed")[:200]
        raise
    except Exception as e:
        supplier["last_error"] = str(e)[:200]
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="SMTP send failed")

    msg = {
        "id": str(uuid.uuid4()),
        "direction": "out",
        "subject": subject,
        "body": body,
        "date": datetime.utcnow().isoformat(),
    }
    supplier.setdefault("messages", []).append(msg)
    supplier["status"] = "sent"
    supplier["last_error"] = None

    return RequestSupplierItemDTO(**{k: v for k, v in supplier.items() if k != "messages"})


@router.post("/requests/{request_id}/suppliers/{supplier_id}/simulate-reply", response_model=RequestSupplierItemDTO)
async def simulate_supplier_reply(
    request_id: int,
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    body: str = "Спасибо, отправим КП сегодня.",
):
    from sqlalchemy import text

    user_id = int(current_user.get("id"))
    owned = await db.execute(
        text("SELECT id FROM parsing_requests WHERE id = :id AND created_by = :uid"),
        {"id": int(request_id), "uid": user_id},
    )
    if not owned.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    await _ensure_request_suppliers_loaded(db=db, request_id=int(request_id))
    supplier = _request_suppliers_state.get(int(request_id), {}).get(int(supplier_id))
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    msg = {
        "id": str(uuid.uuid4()),
        "direction": "in",
        "subject": "Re: Запрос КП",
        "body": str(body or ""),
        "date": datetime.utcnow().isoformat(),
    }
    supplier.setdefault("messages", []).append(msg)
    supplier["status"] = "replied"

    return RequestSupplierItemDTO(**{k: v for k, v in supplier.items() if k != "messages"})


class CabinetParsingRequestCreate(BaseModel):
    title: str
    keys: List[str] = []
    depth: int = 25
    source: str = "google"
    comment: Optional[str] = None


class CabinetParsingRequestUpdate(BaseModel):
    title: Optional[str] = None
    keys: Optional[List[str]] = None
    depth: Optional[int] = None
    source: Optional[str] = None
    comment: Optional[str] = None

# In-memory storage for demo (replace with database in production)
_messages_storage = [
    {
        "id": "m-1",
        "subject": "Запрос коммерческого предложения",
        "from_email": "you@company.ru",
        "to_email": "sales@stroyopt.ru",
        "status": "replied",
        "date": "Сегодня, 12:40",
        "attachments_count": 1,
        "body": "Добрый день!\n\nПрошу направить коммерческое предложение на поставку.\n\nС уважением,\nООО 'СтройХолдинг'"
    },
    {
        "id": "m-2",
        "subject": "Арматура ГОСТ 5781-82",
        "from_email": "you@company.ru",
        "to_email": "info@betonmarket.ru",
        "status": "sent",
        "date": "Вчера, 18:10",
        "attachments_count": 0,
        "body": "Здравствуйте!\n\nИнтересует наличие и цена на арматуру ГОСТ 5781-82.\n\nСпасибо."
    },
    {
        "id": "m-3",
        "subject": "Поставка кирпича облицовочного",
        "from_email": "you@company.ru",
        "to_email": "ivanov@mail.ru",
        "status": "waiting",
        "date": "20 янв, 09:30",
        "attachments_count": 0,
        "body": "Добрый день!\n\nПодскажите, пожалуйста, условия поставки кирпича облицовочного."
    }
]

_settings_storage = {
    "email": "you@company.ru",
    "app_password": None,  # Never return actual password
    "two_fa_enabled": True,
    "organization_name": "ООО 'СтройХолдинг'",
    "organization_verified": True
}

@router.get("/messages", response_model=List[EmailMessageDTO])
async def get_user_messages():
    """Get user email messages history."""
    logger.info("Fetching user messages")
    return [EmailMessageDTO(**msg) for msg in _messages_storage]

@router.post("/messages/compose", response_model=EmailMessageDTO)
async def compose_email(request: EmailComposeRequest):
    """Compose and send a new email."""
    logger.info(f"Composing email to: {request.to_email}")
    
    # Create new message
    new_message = EmailMessageDTO(
        id=f"m-{len(_messages_storage) + 1}",
        subject=request.subject,
        from_email="you@company.ru",  # Get from user settings
        to_email=request.to_email,
        status="sent",
        date="Сегодня, сейчас",
        attachments_count=len(request.attachments) if request.attachments else 0,
        body=request.body,
    )
    
    # Add to storage (in production, actually send email)
    _messages_storage.append(new_message.dict())
    
    return new_message

@router.get("/settings", response_model=UserSettingsDTO)
async def get_user_settings(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user cabinet settings."""
    logger.info("Fetching user settings")
    from sqlalchemy import text
 
    openai_configured = False
    groq_configured = False
    try:
        r = await db.execute(
            text("SELECT openai_api_key_encrypted FROM users WHERE id = :id"),
            {"id": int(current_user.get("id"))},
        )
        row = r.fetchone()
        openai_configured = bool(row and row[0])
    except Exception:
        openai_configured = False

    try:
        r = await db.execute(
            text("SELECT groq_api_key_encrypted FROM users WHERE id = :id"),
            {"id": int(current_user.get("id"))},
        )
        row = r.fetchone()
        groq_configured = bool(row and row[0])
    except Exception:
        groq_configured = False
    return UserSettingsDTO(
        email=current_user.get("email"),
        app_password=None,
        two_fa_enabled=_settings_storage.get("two_fa_enabled", True),
        organization_name=_settings_storage.get("organization_name"),
        organization_verified=_settings_storage.get("organization_verified", False),
        openai_api_key=None,
        openai_api_key_configured=openai_configured,
        groq_api_key=None,
        groq_api_key_configured=groq_configured,
    )

@router.put("/settings", response_model=UserSettingsDTO)
async def update_user_settings(
    settings: UserSettingsDTO,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user cabinet settings."""
    logger.info("Updating user settings")
    
    # Update storage (in production, update in database)
    _settings_storage.update({
        "email": settings.email,
        "two_fa_enabled": settings.two_fa_enabled,
        "organization_name": settings.organization_name,
        "organization_verified": settings.organization_verified
    })
    
    # Only update password if provided (in production, hash it)
    if settings.app_password:
        logger.info("Updating app password")
        _settings_storage["app_password"] = "encrypted_password_placeholder"

    if settings.openai_api_key is not None:
        role = str(current_user.get("role") or "")
        if role not in {"admin", "moderator"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        from app.utils.secrets import encrypt_user_secret
 
        raw_key = (settings.openai_api_key or "").strip()
        encrypted = encrypt_user_secret(raw_key) if raw_key else None
        if raw_key and not encrypted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server encryption key is not configured")
        from sqlalchemy import text
        await db.execute(
            text("UPDATE users SET openai_api_key_encrypted = :v WHERE id = :id"),
            {"v": encrypted, "id": int(current_user.get("id"))},
        )
        await db.commit()

    if settings.groq_api_key is not None:
        role = str(current_user.get("role") or "")
        if role not in {"admin", "moderator"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        from app.utils.secrets import encrypt_user_secret

        raw_key = (settings.groq_api_key or "").strip()
        encrypted = encrypt_user_secret(raw_key) if raw_key else None
        if raw_key and not encrypted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server encryption key is not configured")
        from sqlalchemy import text
        await db.execute(
            text("UPDATE users SET groq_api_key_encrypted = :v WHERE id = :id"),
            {"v": encrypted, "id": int(current_user.get("id"))},
        )
        await db.commit()

    from sqlalchemy import text
    if settings.email and settings.email != current_user.get("email"):
        await db.execute(
            text("UPDATE users SET email = :email WHERE id = :id"),
            {"email": settings.email, "id": current_user.get("id")},
        )
        await db.commit()
        current_user["email"] = settings.email

    openai_configured = False
    groq_configured = False
    try:
        r = await db.execute(
            text("SELECT openai_api_key_encrypted FROM users WHERE id = :id"),
            {"id": int(current_user.get("id"))},
        )
        row = r.fetchone()
        openai_configured = bool(row and row[0])
    except Exception:
        openai_configured = False

    try:
        r = await db.execute(
            text("SELECT groq_api_key_encrypted FROM users WHERE id = :id"),
            {"id": int(current_user.get("id"))},
        )
        row = r.fetchone()
        groq_configured = bool(row and row[0])
    except Exception:
        groq_configured = False

    return UserSettingsDTO(
        email=current_user.get("email"),
        app_password=None,
        two_fa_enabled=_settings_storage.get("two_fa_enabled", True),
        organization_name=_settings_storage.get("organization_name"),
        organization_verified=_settings_storage.get("organization_verified", False),
        openai_api_key=None,
        openai_api_key_configured=openai_configured,
        groq_api_key=None,
        groq_api_key_configured=groq_configured,
    )

@router.post("/settings/change-password")
async def change_password(old_password: str, new_password: str):
    """Change user password."""
    logger.info("Changing user password")
    # In production, verify old password and update with new hashed password
    return {"message": "Password changed successfully"}

@router.get("/stats")
async def get_cabinet_stats():
    """Get cabinet statistics for overview page."""
    logger.info("Fetching cabinet stats")
    
    # Calculate stats from storage
    total_requests = len(_messages_storage)
    sent_messages = len([m for m in _messages_storage if m["status"] == "sent"])
    replied_messages = len([m for m in _messages_storage if m["status"] == "replied"])
    waiting_messages = len([m for m in _messages_storage if m["status"] == "waiting"])
    
    return {
        "total_requests": total_requests,
        "sent_messages": sent_messages,
        "replied_messages": replied_messages,
        "waiting_messages": waiting_messages,
        "email_configured": bool(_settings_storage.get("email")),
        "two_fa_enabled": _settings_storage.get("two_fa_enabled", False),
        "organization_verified": _settings_storage.get("organization_verified", False)
    }


@router.get("/requests", response_model=List[CabinetParsingRequestDTO])
async def list_user_requests(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, ProgrammingError

    user_id = int(current_user.get("id"))
    safe_limit = min(max(int(limit or 50), 1), 200)
    safe_offset = max(int(offset or 0), 0)
    try:
        result = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at, "
                "COALESCE(submitted_to_moderator, FALSE) AS submitted_to_moderator, submitted_at "
                "FROM parsing_requests WHERE created_by = :uid ORDER BY id DESC LIMIT :limit OFFSET :offset"
            ),
            {"uid": user_id, "limit": safe_limit, "offset": safe_offset},
        )
        rows = result.fetchall() or []
        return [
            CabinetParsingRequestDTO(
                id=int(r[0]),
                title=r[1],
                raw_keys_json=r[2],
                depth=r[3],
                source=r[4],
                comment=r[5],
                created_at=r[6].isoformat() if r[6] else None,
                updated_at=r[7].isoformat() if r[7] else None,
                submitted_to_moderator=bool(r[8]),
                submitted_at=r[9].isoformat() if r[9] else None,
            )
            for r in rows
        ]
    except (ProgrammingError, DBAPIError):
        # Backward-compatible fallback for DBs without submitted_to_moderator/submitted_at columns
        # Important: after a failed statement Postgres marks the transaction as aborted.
        # We must rollback before executing another statement.
        try:
            await db.rollback()
        except Exception:
            pass

        result = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at "
                "FROM parsing_requests WHERE created_by = :uid ORDER BY id DESC LIMIT :limit OFFSET :offset"
            ),
            {"uid": user_id, "limit": safe_limit, "offset": safe_offset},
        )
        rows = result.fetchall() or []
        return [
            CabinetParsingRequestDTO(
                id=int(r[0]),
                title=r[1],
                raw_keys_json=r[2],
                depth=r[3],
                source=r[4],
                comment=r[5],
                created_at=r[6].isoformat() if r[6] else None,
                updated_at=r[7].isoformat() if r[7] else None,
                submitted_to_moderator=False,
                submitted_at=None,
            )
            for r in rows
        ]


@router.post("/requests", response_model=CabinetParsingRequestDTO)
async def create_user_request(
    payload: CabinetParsingRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, ProgrammingError
    import json

    user_id = int(current_user.get("id"))
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title is required")

    keys = [k.strip() for k in (payload.keys or []) if k and k.strip()]
    keys = _clean_cabinet_keys(keys)
    raw_keys_json = json.dumps(keys, ensure_ascii=False)

    # Cabinet defaults: user does not choose engine. Always run Google with depth=25 unless explicitly overridden later by admins.
    params = {
        "created_by": user_id,
        "title": title,
        "raw_keys_json": raw_keys_json,
        "depth": int(payload.depth or 25),
        "source": "google",
        "comment": payload.comment,
    }

    try:
        created = await db.execute(
            text(
                "INSERT INTO parsing_requests (created_by, title, raw_keys_json, depth, source, comment) "
                "VALUES (:created_by, :title, :raw_keys_json, :depth, :source, :comment) "
                "RETURNING id, title, raw_keys_json, depth, source, comment, created_at, updated_at, "
                "COALESCE(submitted_to_moderator, FALSE) AS submitted_to_moderator, submitted_at"
            ),
            params,
        )
        row = created.fetchone()
        await db.commit()

        return CabinetParsingRequestDTO(
            id=int(row[0]),
            title=row[1],
            raw_keys_json=row[2],
            depth=row[3],
            source=row[4],
            comment=row[5],
            created_at=row[6].isoformat() if row[6] else None,
            updated_at=row[7].isoformat() if row[7] else None,
            submitted_to_moderator=bool(row[8]),
            submitted_at=row[9].isoformat() if row[9] else None,
        )
    except (ProgrammingError, DBAPIError):
        # Backward-compatible fallback for DBs without submitted_to_moderator/submitted_at columns
        try:
            await db.rollback()
        except Exception:
            pass

        created = await db.execute(
            text(
                "INSERT INTO parsing_requests (created_by, title, raw_keys_json, depth, source, comment) "
                "VALUES (:created_by, :title, :raw_keys_json, :depth, :source, :comment) "
                "RETURNING id, title, raw_keys_json, depth, source, comment, created_at, updated_at"
            ),
            params,
        )
        row = created.fetchone()
        await db.commit()

        return CabinetParsingRequestDTO(
            id=int(row[0]),
            title=row[1],
            raw_keys_json=row[2],
            depth=row[3],
            source=row[4],
            comment=row[5],
            created_at=row[6].isoformat() if row[6] else None,
            updated_at=row[7].isoformat() if row[7] else None,
            submitted_to_moderator=False,
            submitted_at=None,
        )


@router.post("/requests/{request_id}/positions/upload", response_model=CabinetParsingRequestDTO)
async def upload_cabinet_request_positions(
    request_id: int,
    file: UploadFile = FastAPIFile(...),
    engine: str = Query("auto", description="auto | structured | ocr | docling"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, ProgrammingError
    import json
    import os
    from pathlib import Path

    from app.config import settings

    from app.services.cabinet_recognition import (
        RecognitionDependencyError,
        RecognitionEngine,
        extract_item_names_via_groq,
        extract_item_names_via_groq_with_usage,
        extract_text_best_effort,
        normalize_item_names,
        parse_positions_from_text,
    )

    user_id = int(current_user.get("id"))

    if not file or not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is required")

    filename = (file.filename or "").lower()

    # Basic upload security
    max_size = int(os.getenv("CABINET_UPLOAD_MAX_BYTES", "10485760"))  # 10 MiB
    allowed_ext = {"pdf", "png", "jpg", "jpeg", "docx", "xlsx", "txt"}
    ext = filename.split(".")[-1] if "." in filename else ""
    if ext not in allowed_ext:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(content) > max_size:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is too large")

    try:
        engine_enum = RecognitionEngine((engine or "auto").strip().lower())
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid engine. Use auto|structured|ocr|docling")

    # Extract plain text locally (best-effort), then use Groq to extract item names.
    text_content = extract_text_best_effort(filename=filename, content=content, engine=engine_enum)
    if not text_content:
        text_content = ""

    # Prefer user-entered key from cabinet settings (override), then fall back to platform key.
    groq_key = ""
    groq_key_source = ""
    groq_error: str = ""
    groq_key_source_initial: str = ""

    def _is_probably_valid_groq_key(v: str) -> bool:
        vv = (v or "").strip()
        if not vv:
            return False
        # Minimal heuristic validation to avoid using obviously broken keys.
        if len(vv) < 20:
            return False
        return True

    platform_key = ""
    platform_key_source = ""

    # 1) User override key (cabinet)
    try:
        r = await db.execute(
            text("SELECT groq_api_key_encrypted FROM users WHERE id = :id"),
            {"id": int(current_user.get("id"))},
        )
        row = r.fetchone()
        enc = (row[0] if row else None)
        if enc:
            from app.utils.secrets import decrypt_user_secret

            groq_key = (decrypt_user_secret(str(enc)) or "").strip()
            if _is_probably_valid_groq_key(groq_key):
                groq_key_source = "user_db"
            else:
                groq_key = ""
    except Exception:
        groq_key = ""

    # 2) Platform key from process env
    if not platform_key:
        platform_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if _is_probably_valid_groq_key(platform_key):
            platform_key_source = "env"
        else:
            platform_key = ""

    # 3) Platform key from Settings (backend/.env)
    if not platform_key:
        platform_key = (getattr(settings, "GROQ_API_KEY", "") or "").strip()
        if _is_probably_valid_groq_key(platform_key):
            platform_key_source = "settings"
        else:
            platform_key = ""

    # 4) Platform key from DB (latest moderator/admin)
    if not platform_key:
        try:
            r = await db.execute(
                text(
                    "SELECT groq_api_key_encrypted FROM users "
                    "WHERE groq_api_key_encrypted IS NOT NULL AND groq_api_key_encrypted <> '' "
                    "AND role IN ('admin','moderator') "
                    "ORDER BY id DESC LIMIT 1"
                )
            )
            row = r.fetchone()
            enc = (row[0] if row else None)
            if enc:
                from app.utils.secrets import decrypt_user_secret

                platform_key = (decrypt_user_secret(str(enc)) or "").strip()
                if _is_probably_valid_groq_key(platform_key):
                    platform_key_source = "admin_db"
                else:
                    platform_key = ""
        except Exception:
            platform_key = ""
            platform_key_source = ""

    if not groq_key and platform_key:
        groq_key = platform_key
        groq_key_source = platform_key_source

    if groq_key_source:
        groq_key_source_initial = groq_key_source
        logger.info(f"Groq key source: {groq_key_source}")
    names: list[str] = []
    groq_usage: dict = {}
    groq_used = False
    if groq_key and text_content.strip():
        try:
            names, groq_usage = extract_item_names_via_groq_with_usage(text=text_content, api_key=groq_key)
            groq_used = True
        except RecognitionDependencyError as e:
            # If user-provided key is invalid/blocked (401/403), try platform key as fallback.
            err_text = str(e)
            is_auth_error = ("Groq request failed: 401" in err_text) or ("Groq request failed: 403" in err_text)
            if groq_key_source == "user_db" and platform_key and is_auth_error:
                try:
                    names, groq_usage = extract_item_names_via_groq_with_usage(text=text_content, api_key=platform_key)
                    groq_used = True
                    groq_key_source = f"{platform_key_source}_fallback"
                except Exception as e2:
                    groq_error = str(e2)
            else:
                groq_error = err_text
        except Exception as e:
            groq_error = f"Failed to extract item names: {e}"

        # If Groq failed, fall back to heuristic extraction instead of failing request.
        if not groq_used:
            try:
                names = parse_positions_from_text(text_content or "")
            except Exception:
                names = []
    else:
        # Fallback: extract positions heuristically from extracted text.
        try:
            names = parse_positions_from_text(text_content or "")
        except Exception:
            names = []

    # Proof headers (no secrets)
    proof_headers = {
        "X-Groq-Used": "1" if groq_used else "0",
        "X-Groq-Key-Source": groq_key_source or "",
    }
    if groq_key_source_initial and groq_key_source_initial != (groq_key_source or ""):
        proof_headers["X-Groq-Key-Source-Initial"] = groq_key_source_initial
    if groq_error:
        proof_headers["X-Groq-Error"] = (groq_error or "")[:200]
    if isinstance(groq_usage, dict) and groq_usage:
        tt = groq_usage.get("total_tokens")
        pt = groq_usage.get("prompt_tokens")
        ct = groq_usage.get("completion_tokens")
        if tt is not None:
            proof_headers["X-Groq-Total-Tokens"] = str(tt)
        if pt is not None:
            proof_headers["X-Groq-Prompt-Tokens"] = str(pt)
        if ct is not None:
            proof_headers["X-Groq-Completion-Tokens"] = str(ct)

    if not names:
        names = []

    names = normalize_item_names(names)

    # Ensure request exists and belongs to user
    existing = await db.execute(
        text("SELECT id FROM parsing_requests WHERE id = :id AND created_by = :uid"),
        {"id": int(request_id), "uid": user_id},
    )
    if not existing.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    raw_keys_json = json.dumps(names, ensure_ascii=False)

    await db.execute(
        text("UPDATE parsing_requests SET raw_keys_json = :raw_keys_json, updated_at = NOW() WHERE id = :id AND created_by = :uid"),
        {"raw_keys_json": raw_keys_json, "id": int(request_id), "uid": user_id},
    )
    await db.commit()

    try:
        current = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at, "
                "COALESCE(submitted_to_moderator, FALSE) AS submitted_to_moderator, submitted_at "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        row = current.fetchone()
        dto = CabinetParsingRequestDTO(
            id=int(row[0]),
            title=row[1],
            raw_keys_json=row[2],
            depth=row[3],
            source=row[4],
            comment=row[5],
            created_at=row[6].isoformat() if row[6] else None,
            updated_at=row[7].isoformat() if row[7] else None,
            submitted_to_moderator=bool(row[8]),
            submitted_at=row[9].isoformat() if row[9] else None,
        )
        return JSONResponse(status_code=200, content=dto.dict(), headers=proof_headers)
    except (ProgrammingError, DBAPIError):
        try:
            await db.rollback()
        except Exception:
            pass

        current = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        row = current.fetchone()
        dto = CabinetParsingRequestDTO(
            id=int(row[0]),
            title=row[1],
            raw_keys_json=row[2],
            depth=row[3],
            source=row[4],
            comment=row[5],
            created_at=row[6].isoformat() if row[6] else None,
            updated_at=row[7].isoformat() if row[7] else None,
            submitted_to_moderator=False,
            submitted_at=None,
        )
        return JSONResponse(status_code=200, content=dto.dict(), headers=proof_headers)


@router.put("/requests/{request_id}", response_model=CabinetParsingRequestDTO)
async def update_user_request(
    request_id: int,
    payload: CabinetParsingRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, ProgrammingError
    import json

    user_id = int(current_user.get("id"))

    # Backward-compatible: some DBs may not have submitted_to_moderator/submitted_at columns yet.
    try:
        existing = await db.execute(
            text(
                "SELECT id, COALESCE(submitted_to_moderator, FALSE) FROM parsing_requests "
                "WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        row = existing.fetchone()
    except (ProgrammingError, DBAPIError):
        try:
            await db.rollback()
        except Exception:
            pass
        existing = await db.execute(
            text("SELECT id FROM parsing_requests WHERE id = :id AND created_by = :uid"),
            {"id": int(request_id), "uid": user_id},
        )
        r = existing.fetchone()
        row = (r[0], False) if r else None

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if bool(row[1]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already submitted")

    patch: dict = {}
    if payload.title is not None:
        patch["title"] = payload.title.strip()
    if payload.depth is not None:
        patch["depth"] = int(payload.depth)
    if payload.source is not None:
        patch["source"] = str(payload.source)
    if payload.comment is not None:
        patch["comment"] = payload.comment
    if payload.keys is not None:
        keys = [k.strip() for k in (payload.keys or []) if k and k.strip()]
        keys = _clean_cabinet_keys(keys)
        patch["raw_keys_json"] = json.dumps(keys, ensure_ascii=False)

    if not patch:
        # Return current state
        try:
            current = await db.execute(
                text(
                    "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at, "
                    "COALESCE(submitted_to_moderator, FALSE) AS submitted_to_moderator, submitted_at "
                    "FROM parsing_requests WHERE id = :id AND created_by = :uid"
                ),
                {"id": int(request_id), "uid": user_id},
            )
            r = current.fetchone()
            return CabinetParsingRequestDTO(
                id=int(r[0]),
                title=r[1],
                raw_keys_json=r[2],
                depth=r[3],
                source=r[4],
                comment=r[5],
                created_at=r[6].isoformat() if r[6] else None,
                updated_at=r[7].isoformat() if r[7] else None,
                submitted_to_moderator=bool(r[8]),
                submitted_at=r[9].isoformat() if r[9] else None,
            )
        except (ProgrammingError, DBAPIError):
            try:
                await db.rollback()
            except Exception:
                pass
            current = await db.execute(
                text(
                    "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at "
                    "FROM parsing_requests WHERE id = :id AND created_by = :uid"
                ),
                {"id": int(request_id), "uid": user_id},
            )
            r = current.fetchone()
            return CabinetParsingRequestDTO(
                id=int(r[0]),
                title=r[1],
                raw_keys_json=r[2],
                depth=r[3],
                source=r[4],
                comment=r[5],
                created_at=r[6].isoformat() if r[6] else None,
                updated_at=r[7].isoformat() if r[7] else None,
                submitted_to_moderator=False,
                submitted_at=None,
            )

    set_parts = ", ".join([f"{k} = :{k}" for k in patch.keys()])
    try:
        await db.execute(
            text(
                f"UPDATE parsing_requests SET {set_parts}, updated_at = NOW() "
                "WHERE id = :id AND created_by = :uid"
            ),
            {**patch, "id": int(request_id), "uid": user_id},
        )
        await db.commit()

        # Return authoritative state from DB (avoid stale RETURNING values)
        current = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at, "
                "COALESCE(submitted_to_moderator, FALSE) AS submitted_to_moderator, submitted_at "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        r = current.fetchone()
        return CabinetParsingRequestDTO(
            id=int(r[0]),
            title=r[1],
            raw_keys_json=r[2],
            depth=r[3],
            source=r[4],
            comment=r[5],
            created_at=r[6].isoformat() if r[6] else None,
            updated_at=r[7].isoformat() if r[7] else None,
            submitted_to_moderator=bool(r[8]),
            submitted_at=r[9].isoformat() if r[9] else None,
        )
    except (ProgrammingError, DBAPIError):
        # Backward-compatible fallback for DBs without submitted_to_moderator/submitted_at columns
        try:
            await db.rollback()
        except Exception:
            pass

        await db.execute(
            text(
                f"UPDATE parsing_requests SET {set_parts}, updated_at = NOW() "
                "WHERE id = :id AND created_by = :uid"
            ),
            {**patch, "id": int(request_id), "uid": user_id},
        )
        await db.commit()

        current = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        r = current.fetchone()
        return CabinetParsingRequestDTO(
            id=int(r[0]),
            title=r[1],
            raw_keys_json=r[2],
            depth=r[3],
            source=r[4],
            comment=r[5],
            created_at=r[6].isoformat() if r[6] else None,
            updated_at=r[7].isoformat() if r[7] else None,
            submitted_to_moderator=False,
            submitted_at=None,
        )


@router.post("/requests/{request_id}/submit", response_model=CabinetParsingRequestDTO)
async def submit_user_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, ProgrammingError

    user_id = int(current_user.get("id"))

    # Backward-compatible: some DBs may not have submitted_to_moderator/submitted_at columns yet.
    try:
        fetch = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, COALESCE(submitted_to_moderator, FALSE) "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        r = fetch.fetchone()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
        if bool(r[5]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already submitted")

        await db.execute(
            text(
                "UPDATE parsing_requests SET submitted_to_moderator = TRUE, submitted_at = NOW(), updated_at = NOW() "
                "WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
    except (ProgrammingError, DBAPIError):
        try:
            await db.rollback()
        except Exception:
            pass

        fetch = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        r = fetch.fetchone()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        # Without submitted flags we still mark updated_at to indicate action.
        await db.execute(
            text(
                "UPDATE parsing_requests SET updated_at = NOW() "
                "WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )

    keyword = str(r[1] or "").strip()
    depth = int(r[3] or 25)
    source = str(r[4] or "google")
    if not keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request title is empty")

    # Start parsing for existing request
    # Cabinet invariant: user flow always uses Google. Depth defaults to 25 if not set.
    safe_depth = int(depth or 25)
    await start_parsing.execute(db=db, keyword=keyword, depth=safe_depth, source="google", background_tasks=None, request_id=int(request_id))
    await db.commit()

    try:
        current = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at, "
                "COALESCE(submitted_to_moderator, FALSE) AS submitted_to_moderator, submitted_at "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        row = current.fetchone()
        return CabinetParsingRequestDTO(
            id=int(row[0]),
            title=row[1],
            raw_keys_json=row[2],
            depth=row[3],
            source=row[4],
            comment=row[5],
            created_at=row[6].isoformat() if row[6] else None,
            updated_at=row[7].isoformat() if row[7] else None,
            submitted_to_moderator=bool(row[8]),
            submitted_at=row[9].isoformat() if row[9] else None,
        )
    except (ProgrammingError, DBAPIError):
        try:
            await db.rollback()
        except Exception:
            pass

        current = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": int(request_id), "uid": user_id},
        )
        row = current.fetchone()
        return CabinetParsingRequestDTO(
            id=int(row[0]),
            title=row[1],
            raw_keys_json=row[2],
            depth=row[3],
            source=row[4],
            comment=row[5],
            created_at=row[6].isoformat() if row[6] else None,
            updated_at=row[7].isoformat() if row[7] else None,
            submitted_to_moderator=False,
            submitted_at=None,
        )
