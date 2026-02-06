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
    source_url: Optional[str] = None
    source_urls: Optional[List[str]] = None
    keyword_urls: Optional[List[Dict[str, str]]] = None
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
    request_status: Optional[str] = None


async def _ensure_request_suppliers_loaded(*, db: AsyncSession, request_id: int) -> None:
    # Always recompute to reflect latest moderator_suppliers enrichment/moderation.
    _request_suppliers_state[int(request_id)] = {}

    from sqlalchemy import text

    def _norm_domain(d: str | None) -> str:
        s = str(d or "").strip().lower()
        if s.startswith("www."):
            s = s[4:]
        return s

    # 1) Get all parsing runs for this request
    runs_res = await db.execute(
        text("SELECT run_id FROM parsing_runs WHERE request_id = :rid ORDER BY created_at ASC"),
        {"rid": int(request_id)},
    )
    run_ids = [str(r[0]) for r in (runs_res.fetchall() or []) if r and r[0]]
    if not run_ids:
        return

    # 2) Get domains found for these runs
    dq_res = await db.execute(
        text(
            "SELECT id, domain, url, keyword "
            "FROM domains_queue "
            "WHERE parsing_run_id = ANY(:run_ids) "
            "ORDER BY id ASC"
        ),
        {"run_ids": list(run_ids)},
    )
    dq_rows = dq_res.fetchall() or []
    if not dq_rows:
        return

    # Deduplicate by normalized domain (keep first occurrence)
    uniq_by_domain: dict[str, tuple[int, str, Optional[str], Optional[str]]] = {}
    domain_urls_by_keyword: dict[str, list[dict[str, str]]] = {}
    for r in dq_rows:
        dq_id = int(r[0])
        domain_raw = str(r[1] or "").strip()
        source_url = str(r[2] or "").strip() or None
        keyword = str(r[3] or "").strip() or None
        if not domain_raw:
            continue
        nd = _norm_domain(domain_raw)
        if not nd:
            continue
        if source_url:
            domain_urls_by_keyword.setdefault(nd, [])
            item = {"keyword": keyword or "", "url": source_url}
            if item not in domain_urls_by_keyword[nd]:
                domain_urls_by_keyword[nd].append(item)
        if nd not in uniq_by_domain:
            uniq_by_domain[nd] = (dq_id, domain_raw, source_url, keyword)

    if not uniq_by_domain:
        return

    # 3) Fetch supplier cards for these domains (domain + www.domain)
    variants: list[str] = []
    for nd in uniq_by_domain.keys():
        variants.append(nd)
        variants.append(f"www.{nd}")
    variants = list(dict.fromkeys([v for v in variants if v]))

    suppliers_res = await db.execute(
        text(
            "SELECT ms.id, COALESCE(ms.name, ''), ms.email, ms.phone, "
            "COALESCE(sd.domain, ms.domain) AS matched_domain "
            "FROM moderator_suppliers ms "
            "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
            "WHERE (ms.domain IS NOT NULL OR sd.domain IS NOT NULL) "
            "AND replace(lower(COALESCE(sd.domain, ms.domain)), 'www.', '') = ANY(:domains)"
        ),
        {"domains": variants},
    )
    suppliers_rows = suppliers_res.fetchall() or []
    supplier_by_norm_domain: dict[str, tuple[int, str, str | None, str | None, str | None]] = {}
    for sr in suppliers_rows:
        sid = int(sr[0])
        sname = str(sr[1] or "").strip()
        semail = (str(sr[2]).strip() if sr[2] is not None else None)
        sphone = (str(sr[3]).strip() if sr[3] is not None else None)
        sdomain = (str(sr[4]).strip() if sr[4] is not None else None)
        supplier_by_norm_domain[_norm_domain(sdomain)] = (sid, sname, semail, sphone, sdomain)

    import re

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

    # Load supplier_emails for better email coverage
    supplier_emails_by_id: dict[int, list[str]] = {}
    if supplier_by_norm_domain:
        try:
            ids = list({int(v[0]) for v in supplier_by_norm_domain.values()})
            if ids:
                em_res = await db.execute(
                    text("SELECT supplier_id, email FROM supplier_emails WHERE supplier_id = ANY(:ids)"),
                    {"ids": ids},
                )
                for row in em_res.fetchall() or []:
                    sid = int(row[0])
                    email = str(row[1] or "").strip()
                    if not email:
                        continue
                    supplier_emails_by_id.setdefault(sid, [])
                    if email not in supplier_emails_by_id[sid]:
                        supplier_emails_by_id[sid].append(email)
        except Exception:
            supplier_emails_by_id = {}

    # Cabinet should show only suppliers that already exist in moderator_suppliers.
    for nd, (_dq_id, _domain_raw, source_url, _keyword) in uniq_by_domain.items():
        supplier = supplier_by_norm_domain.get(str(nd))
        if not supplier:
            continue
        supplier_id = int(supplier[0])
        name = supplier[1]
        emails = supplier_emails_by_id.get(supplier_id) or _split_emails(supplier[2])
        existing = _request_suppliers_state[int(request_id)].get(int(supplier_id))
        keyword_urls = domain_urls_by_keyword.get(nd, [])
        urls_only = [x["url"] for x in keyword_urls if x.get("url")]
        if not existing:
            _request_suppliers_state[int(request_id)][int(supplier_id)] = {
                "supplier_id": int(supplier_id),
                "name": name or "",
                "email": (emails[0] if emails else None),
                "emails": emails,
                "phone": supplier[3],
                "domain": supplier[4],
                "source_url": source_url,
                "source_urls": urls_only,
                "keyword_urls": keyword_urls,
                "status": "waiting",
                "messages": [],
                "last_error": None,
            }
            continue
        if (not existing.get("source_url")) and source_url:
            existing["source_url"] = source_url
        all_urls = list(existing.get("source_urls") or [])
        for u in urls_only:
            if u and u not in all_urls:
                all_urls.append(u)
        existing["source_urls"] = all_urls
        all_kw_urls = list(existing.get("keyword_urls") or [])
        for ku in keyword_urls:
            if ku not in all_kw_urls:
                all_kw_urls.append(ku)
        existing["keyword_urls"] = all_kw_urls


async def _compute_request_status(*, db: AsyncSession, request_id: int, submitted_to_moderator: bool) -> str:
    if not submitted_to_moderator:
        return "draft"

    from sqlalchemy import text

    # 1) Get run ids
    runs_res = await db.execute(
        text("SELECT run_id FROM parsing_runs WHERE request_id = :rid ORDER BY created_at ASC"),
        {"rid": int(request_id)},
    )
    run_ids = [str(r[0]) for r in (runs_res.fetchall() or []) if r and r[0]]
    if not run_ids:
        return "in_progress"

    # 2) Get unique normalized domains for runs
    dq_res = await db.execute(
        text(
            "SELECT DISTINCT replace(lower(domain), 'www.', '') "
            "FROM domains_queue WHERE parsing_run_id = ANY(:run_ids)"
        ),
        {"run_ids": list(run_ids)},
    )
    domains = [str(r[0]) for r in (dq_res.fetchall() or []) if r and r[0]]
    if not domains:
        return "in_progress"

    # 3) Check blacklist + suppliers for these domains
    blacklist_res = await db.execute(
        text("SELECT replace(lower(domain), 'www.', '') FROM blacklist WHERE replace(lower(domain), 'www.', '') = ANY(:domains)"),
        {"domains": domains},
    )
    blacklisted = {str(r[0]) for r in (blacklist_res.fetchall() or []) if r and r[0]}

    suppliers_res = await db.execute(
        text(
            "SELECT DISTINCT replace(lower(COALESCE(sd.domain, ms.domain)), 'www.', '') "
            "FROM moderator_suppliers ms "
            "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
            "WHERE replace(lower(COALESCE(sd.domain, ms.domain)), 'www.', '') = ANY(:domains)"
        ),
        {"domains": domains},
    )
    suppliers = {str(r[0]) for r in (suppliers_res.fetchall() or []) if r and r[0]}

    unresolved = [d for d in domains if d not in blacklisted and d not in suppliers]
    if unresolved:
        return "in_progress"
    return "completed"


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
    supplier_map = _request_suppliers_state.get(int(request_id), {})
    return [RequestSupplierItemDTO(**{k: v for k, v in s.items() if k != "messages"}) for s in supplier_map.values()]


@router.get("/requests/{request_id}", response_model=CabinetParsingRequestDTO)
async def get_user_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, ProgrammingError

    user_id = int(current_user.get("id"))
    rid = int(request_id)

    try:
        result = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at, "
                "COALESCE(submitted_to_moderator, FALSE) AS submitted_to_moderator, submitted_at "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": rid, "uid": user_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
        status_val = await _compute_request_status(db=db, request_id=rid, submitted_to_moderator=bool(row[8]))
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
            request_status=status_val,
        )
    except (ProgrammingError, DBAPIError):
        try:
            await db.rollback()
        except Exception:
            pass
        result = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at "
                "FROM parsing_requests WHERE id = :id AND created_by = :uid"
            ),
            {"id": rid, "uid": user_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
        status_val = await _compute_request_status(db=db, request_id=rid, submitted_to_moderator=False)
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
            request_status=status_val,
        )


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
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


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


class CabinetParsingRequestBulkDelete(BaseModel):
    ids: List[int]


class CabinetParsingRequestBulkDeleteResult(BaseModel):
    requested: int
    deleted: int
    skipped_submitted: int
    not_found: int

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


@router.get("/groq/status")
async def get_groq_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    import os
    import httpx

    from app.config import settings

    try:
        logger.info(f"Groq status check: user_id={int(current_user.get('id') or 0)}")
    except Exception:
        logger.info("Groq status check")

    def _is_probably_valid_groq_key(v: str) -> bool:
        vv = (v or "").strip()
        if not vv:
            return False
        if len(vv) < 20:
            return False
        return True

    groq_key = ""

    # 1) User key
    try:
        r = await db.execute(
            text("SELECT groq_api_key_encrypted FROM users WHERE id = :id"),
            {"id": int(current_user.get("id"))},
        )
        row = r.fetchone()
        enc = (row[0] if row else None)
        if enc:
            from app.utils.secrets import decrypt_user_secret

            candidate = (decrypt_user_secret(str(enc)) or "").strip()
            if _is_probably_valid_groq_key(candidate):
                groq_key = candidate
    except Exception:
        groq_key = ""

    # 2) Platform key: env -> settings -> admin/moderator DB
    if not groq_key:
        candidate = (os.getenv("GROQ_API_KEY") or "").strip()
        if _is_probably_valid_groq_key(candidate):
            groq_key = candidate

    if not groq_key:
        candidate = (getattr(settings, "GROQ_API_KEY", "") or "").strip()
        if _is_probably_valid_groq_key(candidate):
            groq_key = candidate

    if not groq_key:
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

                candidate = (decrypt_user_secret(str(enc)) or "").strip()
                if _is_probably_valid_groq_key(candidate):
                    groq_key = candidate
        except Exception:
            groq_key = ""

    configured = bool(groq_key)
    if not configured:
        return {"configured": False, "available": False}

    base = (os.getenv("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
    url = f"{base}/models"
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {groq_key}"})
        if resp.status_code == 200:
            return {"configured": True, "available": True, "status_code": 200}

        snippet = ""
        try:
            snippet = (resp.text or "").strip()
        except Exception:
            snippet = ""
        if snippet:
            snippet = snippet[:400]

        out = {
            "configured": True,
            "available": False,
            "status_code": int(resp.status_code),
            "error": (resp.reason_phrase or ""),
            "body_snippet": snippet,
        }

        # Try chat/completions to get a more specific error message (model permissions, etc.)
        chat_url = f"{base}/chat/completions"
        model = (os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant").strip()
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                chat_resp = await client.post(
                    chat_url,
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                        "temperature": 0,
                    },
                )
            chat_snippet = ""
            try:
                chat_snippet = (chat_resp.text or "").strip()
            except Exception:
                chat_snippet = ""
            if chat_snippet:
                chat_snippet = chat_snippet[:400]
            out.update(
                {
                    "chat_status_code": int(chat_resp.status_code),
                    "chat_error": (chat_resp.reason_phrase or ""),
                    "chat_body_snippet": chat_snippet,
                    "model": model,
                }
            )
        except Exception:
            out.update({"chat_status_code": None, "chat_error": "request_failed", "model": model})

        return out
    except Exception:
        return {"configured": True, "available": False, "status_code": None, "error": "request_failed"}


@router.get("/requests", response_model=List[CabinetParsingRequestDTO])
async def list_user_requests(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    submitted: Optional[bool] = Query(None),
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, ProgrammingError

    user_id = int(current_user.get("id"))
    safe_limit = min(max(int(limit or 50), 1), 200)
    safe_offset = max(int(offset or 0), 0)
    try:
        where_submitted = ""
        params = {"uid": user_id, "limit": safe_limit, "offset": safe_offset}
        if submitted is True:
            where_submitted = " AND COALESCE(submitted_to_moderator, FALSE) = TRUE "
        elif submitted is False:
            where_submitted = " AND COALESCE(submitted_to_moderator, FALSE) = FALSE "

        result = await db.execute(
            text(
                "SELECT id, title, raw_keys_json, depth, source, comment, created_at, updated_at, "
                "COALESCE(submitted_to_moderator, FALSE) AS submitted_to_moderator, submitted_at "
                "FROM parsing_requests WHERE created_by = :uid" + where_submitted + " ORDER BY id DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        rows = result.fetchall() or []
        out: list[CabinetParsingRequestDTO] = []
        for r in rows:
            status_val = await _compute_request_status(
                db=db,
                request_id=int(r[0]),
                submitted_to_moderator=bool(r[8]),
            )
            out.append(
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
                    request_status=status_val,
                )
            )
        return out
    except (ProgrammingError, DBAPIError):
        # Backward-compatible fallback for DBs without submitted_to_moderator/submitted_at columns.
        # In this mode we cannot reliably filter drafts vs submitted, so return full list.
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
        out: list[CabinetParsingRequestDTO] = []
        for r in rows:
            status_val = await _compute_request_status(
                db=db,
                request_id=int(r[0]),
                submitted_to_moderator=False,
            )
            out.append(
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
                    request_status=status_val,
                )
            )
        return out


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
async def upload_request_positions_with_engine_proof(
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
    import re
    from pathlib import Path

    from app.config import settings

    from app.services.cabinet_recognition import (
        RecognitionDependencyError,
        RecognitionEngine,
        extract_item_names_via_groq,
        extract_item_names_via_groq_with_usage,
        extract_search_keys_via_groq,
        extract_text_best_effort,
        group_similar_item_names,
        normalize_item_names,
        parse_positions_from_text,
    )

    user_id = int(current_user.get("id"))

    try:
        msg0 = f"Cabinet recognize start: request_id={int(request_id)} user_id={int(user_id)} engine={str(engine or '')} filename={str(getattr(file, 'filename', '') or '')}"
        logger.warning(msg0)
        print(msg0)
    except Exception:
        logger.warning("Cabinet recognize start")
        try:
            print("Cabinet recognize start")
        except Exception:
            pass

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

    try:
        msg1 = f"Cabinet recognize text_extracted: request_id={int(request_id)} chars={len(text_content or '')}"
        logger.warning(msg1)
        print(msg1)
    except Exception:
        pass

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
            search_keys, _categories, groq_usage = extract_search_keys_via_groq(text=text_content, api_key=groq_key)
            names = search_keys
            groq_used = True
        except RecognitionDependencyError as e:
            # If user-provided key is invalid/blocked (401/403), try platform key as fallback.
            err_text = str(e)
            is_auth_error = ("Groq request failed: 401" in err_text) or ("Groq request failed: 403" in err_text)
            if groq_key_source == "user_db" and platform_key and is_auth_error:
                try:
                    search_keys, _categories, groq_usage = extract_search_keys_via_groq(text=text_content, api_key=platform_key)
                    names = search_keys
                    groq_used = True
                    groq_key_source = f"{platform_key_source}_fallback"
                except Exception as e2:
                    groq_error = str(e2)
            else:
                groq_error = err_text
        except Exception as e:
            groq_error = f"Failed to extract item names: {e}"

        try:
            msg2 = f"Cabinet recognize groq_done: request_id={int(request_id)} groq_used={1 if groq_used else 0} source={groq_key_source or ''} err={(groq_error or '')[:120]}"
            logger.warning(msg2)
            print(msg2)
        except Exception:
            pass

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

    # If Groq returned a minimal key set, ensure we don't lose important accessories
    # (e.g. 'Заглушка') that may be omitted due to key limits.
    accessory_re = re.compile(r"\b(заглушк\w*|прокладк\w*|болт\w*|гайк\w*|шайб\w*|креп[её]ж\w*)\b", re.IGNORECASE)
    try:
        if groq_used:
            heur_positions = parse_positions_from_text(text_content or "")
            heur_positions = normalize_item_names(heur_positions)
            heur_keys = group_similar_item_names(heur_positions)
            accessories = [k for k in heur_keys if accessory_re.search(str(k or ""))]
            if accessories:
                merged: list[str] = []
                seen_m: set[str] = set()
                for k in (names or []) + accessories:
                    s = " ".join(str(k or "").split()).strip()
                    if not s:
                        continue
                    low = s.lower()
                    if low in seen_m:
                        continue
                    seen_m.add(low)
                    merged.append(s)
                names = merged
    except Exception:
        pass

    # Hard safety: if the extracted text contains 'заглушк*' then ensure key 'Заглушка' exists.
    try:
        zag_in_text = bool(re.search(r"\bзаглушк\w*\b", text_content or "", re.IGNORECASE))
        try:
            logger.warning(f"Cabinet recognize zaglushka_in_text: request_id={int(request_id)} val={1 if zag_in_text else 0}")
            print(f"Cabinet recognize zaglushka_in_text: request_id={int(request_id)} val={1 if zag_in_text else 0}")
        except Exception:
            pass

        if zag_in_text:
            low_set = {str(x or "").strip().lower() for x in (names or [])}
            if "заглушка" not in low_set:
                names = list(names or []) + ["Заглушка"]
                try:
                    logger.warning(f"Cabinet recognize zaglushka_forced_add: request_id={int(request_id)}")
                    print(f"Cabinet recognize zaglushka_forced_add: request_id={int(request_id)}")
                except Exception:
                    pass
    except Exception:
        pass

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

    names = group_similar_item_names(normalize_item_names(names))

    try:
        msg3 = f"Cabinet recognize done: request_id={int(request_id)} user_id={int(user_id)} groq_used={1 if groq_used else 0} keys={len(names or [])}"
        logger.warning(msg3)
        print(msg3)
    except Exception:
        logger.warning("Cabinet recognize done")
        try:
            print("Cabinet recognize done")
        except Exception:
            pass

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


@router.post("/requests/bulk-delete", response_model=CabinetParsingRequestBulkDeleteResult)
async def bulk_delete_user_requests(
    payload: CabinetParsingRequestBulkDelete,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError, ProgrammingError

    user_id = int(current_user.get("id"))
    ids_in = [int(x) for x in (payload.ids or []) if isinstance(x, int) or str(x).isdigit()]
    # Unique + keep input bounded
    ids: list[int] = []
    seen: set[int] = set()
    for x in ids_in:
        if x <= 0:
            continue
        if x in seen:
            continue
        seen.add(x)
        ids.append(x)
        if len(ids) >= 500:
            break

    if not ids:
        return CabinetParsingRequestBulkDeleteResult(requested=0, deleted=0, skipped_submitted=0, not_found=0)

    requested = len(ids)
    deleted = 0
    skipped_submitted = 0
    not_found = 0

    try:
        # Determine which are drafts vs submitted and exist for this user.
        q = await db.execute(
            text(
                "SELECT id, COALESCE(submitted_to_moderator, FALSE) AS submitted "
                "FROM parsing_requests WHERE created_by = :uid AND id = ANY(:ids)"
            ),
            {"uid": user_id, "ids": ids},
        )
        rows = q.fetchall() or []
        found_ids = {int(r[0]) for r in rows}
        not_found = requested - len(found_ids)
        draft_ids = [int(r[0]) for r in rows if not bool(r[1])]
        skipped_submitted = len([r for r in rows if bool(r[1])])

        if draft_ids:
            await db.execute(
                text("DELETE FROM parsing_requests WHERE created_by = :uid AND id = ANY(:ids)"),
                {"uid": user_id, "ids": draft_ids},
            )
            deleted = len(draft_ids)
        await db.commit()

        return CabinetParsingRequestBulkDeleteResult(
            requested=requested,
            deleted=deleted,
            skipped_submitted=skipped_submitted,
            not_found=not_found,
        )
    except (ProgrammingError, DBAPIError):
        # Backward-compatible fallback for DBs without submitted_to_moderator column.
        try:
            await db.rollback()
        except Exception:
            pass

        q = await db.execute(
            text("SELECT id FROM parsing_requests WHERE created_by = :uid AND id = ANY(:ids)"),
            {"uid": user_id, "ids": ids},
        )
        rows = q.fetchall() or []
        found_ids = [int(r[0]) for r in rows]
        not_found = requested - len(found_ids)
        if found_ids:
            await db.execute(
                text("DELETE FROM parsing_requests WHERE created_by = :uid AND id = ANY(:ids)"),
                {"uid": user_id, "ids": found_ids},
            )
            deleted = len(found_ids)
        await db.commit()
        return CabinetParsingRequestBulkDeleteResult(
            requested=requested,
            deleted=deleted,
            skipped_submitted=0,
            not_found=not_found,
        )


@router.post("/requests/{request_id}/submit", response_model=CabinetParsingRequestDTO)
async def submit_user_request(
    request_id: int,
    background_tasks: BackgroundTasks,
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

    import json

    keyword = str(r[1] or "").strip()
    depth = int(r[3] or 25)
    source = str(r[4] or "google")
    if not keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request title is empty")

    keys: List[str] = []
    try:
        parsed = json.loads(r[2] or "[]")
        if isinstance(parsed, list):
            keys = [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        keys = []

    if not keys:
        # Fallback: at least run for title
        keys = [keyword]

    try:
        logger.warning(
            "Cabinet submit: request_id=%s title=%s keys_count=%s keys_preview=%s",
            int(request_id),
            keyword,
            int(len(keys)),
            ", ".join(keys[:5]),
        )
    except Exception:
        pass

    # Best-effort task creation (must not break request submit transaction)
    try:
        await db.execute(text("SAVEPOINT sp_moderator_task"))
        await db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS moderator_tasks ("
                "id BIGSERIAL PRIMARY KEY, "
                "request_id BIGINT NOT NULL, "
                "created_by BIGINT NOT NULL, "
                "title TEXT, "
                "status VARCHAR(32) NOT NULL DEFAULT 'new', "
                "source VARCHAR(16) NOT NULL DEFAULT 'google', "
                "depth INTEGER NOT NULL DEFAULT 30, "
                "created_at TIMESTAMP NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        # Add column for existing DBs
        await db.execute(text("ALTER TABLE moderator_tasks ADD COLUMN IF NOT EXISTS title TEXT"))
        await db.execute(
            text(
                "INSERT INTO moderator_tasks (request_id, created_by, title, status, source, depth) "
                "VALUES (:request_id, :created_by, :title, :status, :source, :depth)"
            ),
            {
                "request_id": int(request_id),
                "created_by": int(user_id),
                "title": keyword,
                "status": "new",
                "source": source,
                "depth": depth,
            },
        )
        await db.execute(text("RELEASE SAVEPOINT sp_moderator_task"))
    except Exception:
        try:
            await db.execute(text("ROLLBACK TO SAVEPOINT sp_moderator_task"))
        except Exception:
            pass

    # Start parsing asynchronously (do not block submit response)
    async def _start_parsing_bg(keys_: List[str], request_id_: int, depth_: int, source_: str) -> None:
        from app.adapters.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as bg_db:
            for k in keys_ or []:
                kw = str(k or "").strip()
                if not kw:
                    continue
                try:
                    await start_parsing.execute(
                        db=bg_db,
                        keyword=kw,
                        depth=int(depth_),
                        source=str(source_ or "google"),
                        background_tasks=None,
                        request_id=int(request_id_),
                    )
                except Exception:
                    # Do not abort the whole submit on a single keyword failure.
                    try:
                        import logging
                        logging.getLogger(__name__).exception(
                            "Cabinet submit: failed to start parsing for keyword=%s request_id=%s",
                            kw,
                            int(request_id_),
                        )
                    except Exception:
                        pass
            await bg_db.commit()

    background_tasks.add_task(_start_parsing_bg, list(keys), int(request_id), int(depth), str(source))

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
