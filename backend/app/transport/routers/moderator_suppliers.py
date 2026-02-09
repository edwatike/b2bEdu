"""Router for moderator suppliers."""
import asyncio
import logging
from typing import Optional
import time
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.adapters.db.session import get_db
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator as _require_moderator
from app.config import settings
from app.transport.schemas.moderator_suppliers import (
    ModeratorSupplierDTO,
    CreateModeratorSupplierRequestDTO,
    UpdateModeratorSupplierRequestDTO,
    SupplierKeywordsResponseDTO,
    ModeratorSuppliersListResponseDTO,
)
from app.usecases import (
    create_moderator_supplier,
    get_moderator_supplier,
    list_moderator_suppliers,
    update_moderator_supplier,
    delete_moderator_supplier,
    get_supplier_keywords,
)
from app.utils.domain import normalize_domain_root

router = APIRouter()
logger = logging.getLogger(__name__)

_CHECKO_ENRICH_ALL_TASK: asyncio.Task | None = None
_CHECKO_ENRICH_ALL_LOCK = asyncio.Lock()
_CHECKO_ENRICH_ALL_STATE: dict[str, object] = {
    "running": False,
    "startedAt": None,
    "finishedAt": None,
    "processed": 0,
    "success": 0,
    "failed": 0,
    "skippedNoInn": 0,
    "lastInn": None,
    "lastError": None,
}


class EnrichAllCheckoRequestDTO(BaseModel):
    force_refresh: bool = True
    limit: int = 0


@router.post("/suppliers/checko/enrich-all")
async def enrich_all_suppliers_checko(
    payload: EnrichAllCheckoRequestDTO,
    current_user: dict = Depends(get_current_user),
):
    _require_moderator(current_user)

    async with _CHECKO_ENRICH_ALL_LOCK:
        global _CHECKO_ENRICH_ALL_TASK
        if _CHECKO_ENRICH_ALL_TASK is not None and not _CHECKO_ENRICH_ALL_TASK.done():
            return {"ok": True, "alreadyRunning": True, "state": dict(_CHECKO_ENRICH_ALL_STATE)}

        _CHECKO_ENRICH_ALL_STATE.update(
            {
                "running": True,
                "startedAt": int(time.time()),
                "finishedAt": None,
                "processed": 0,
                "success": 0,
                "failed": 0,
                "skippedNoInn": 0,
                "lastInn": None,
                "lastError": None,
            }
        )

        from app.adapters.db.session import AsyncSessionLocal
        from app.adapters.db.models import ModeratorSupplierModel
        from sqlalchemy import select
        from app.usecases import get_checko_data

        async def _run() -> None:
            try:
                processed = 0
                while True:
                    async with AsyncSessionLocal() as db:
                        q = (
                            select(ModeratorSupplierModel)
                            .where(
                                ModeratorSupplierModel.checko_data.is_(None),
                                ModeratorSupplierModel.inn.is_not(None),
                            )
                            .order_by(ModeratorSupplierModel.id.asc())
                            .limit(50)
                        )
                        res = await db.execute(q)
                        batch = list(res.scalars().all() or [])

                    if not batch:
                        break

                    for s in batch:
                        inn = str(getattr(s, "inn", "") or "").strip()
                        if not inn:
                            _CHECKO_ENRICH_ALL_STATE["skippedNoInn"] = int(_CHECKO_ENRICH_ALL_STATE.get("skippedNoInn") or 0) + 1
                            continue

                        _CHECKO_ENRICH_ALL_STATE["lastInn"] = inn
                        _CHECKO_ENRICH_ALL_STATE["lastError"] = None

                        try:
                            async with AsyncSessionLocal() as db:
                                await get_checko_data.execute(db=db, inn=inn, force_refresh=bool(payload.force_refresh))
                            _CHECKO_ENRICH_ALL_STATE["success"] = int(_CHECKO_ENRICH_ALL_STATE.get("success") or 0) + 1
                        except Exception as e:
                            _CHECKO_ENRICH_ALL_STATE["failed"] = int(_CHECKO_ENRICH_ALL_STATE.get("failed") or 0) + 1
                            _CHECKO_ENRICH_ALL_STATE["lastError"] = f"{type(e).__name__}: {e}"[:500]
                        finally:
                            processed += 1
                            _CHECKO_ENRICH_ALL_STATE["processed"] = processed

                            lim = int(payload.limit or 0)
                            if lim > 0 and processed >= lim:
                                return
            finally:
                _CHECKO_ENRICH_ALL_STATE["running"] = False
                _CHECKO_ENRICH_ALL_STATE["finishedAt"] = int(time.time())

        # Temporarily disable background task to test MissingGreenlet issue
        # _CHECKO_ENRICH_ALL_TASK = asyncio.create_task(_run())
        logger.info("Background Checko enrichment task disabled for testing")
        return {"ok": True, "started": False, "state": dict(_CHECKO_ENRICH_ALL_STATE)}


@router.get("/suppliers/checko/enrich-all/status")
async def enrich_all_suppliers_checko_status(current_user: dict = Depends(get_current_user)):
    _require_moderator(current_user)
    running = False
    if _CHECKO_ENRICH_ALL_TASK is not None and not _CHECKO_ENRICH_ALL_TASK.done():
        running = True
    st = dict(_CHECKO_ENRICH_ALL_STATE)
    st["running"] = running
    return {"ok": True, "state": st}


def _require_debug():
    if str(getattr(settings, "ENV", "")).lower() != "development":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _normalize_domains(domains: list[str] | None, domain: str | None) -> list[str]:
    out: list[str] = []
    candidates = []
    if domain:
        candidates.append(domain)
    if domains:
        candidates.extend(domains)
    for d in candidates:
        nd = normalize_domain_root(d)
        if not nd:
            continue
        if nd not in out:
            out.append(nd)
    return out


def _normalize_emails(emails: list[str] | None, email: str | None) -> list[str]:
    out: list[str] = []
    candidates = []
    if email:
        candidates.append(email)
    if emails:
        candidates.extend(emails)
    for e in candidates:
        s = str(e or "").strip().lower()
        if not s:
            continue
        if s not in out:
            out.append(s)
    return out


def _validate_required_inn_email(inn: str | None, email: str | None) -> None:
    if not inn or not str(inn).strip():
        raise HTTPException(status_code=422, detail="ИНН обязателен")
    if not email or not str(email).strip():
        raise HTTPException(status_code=422, detail="Email обязателен")
    inn_s = str(inn).strip()
    if not inn_s.isdigit() or len(inn_s) not in (10, 12):
        raise HTTPException(status_code=422, detail="ИНН должен содержать 10 или 12 цифр")
    import re
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", str(email).strip()):
        raise HTTPException(status_code=422, detail="Некорректный формат email")


def _build_inn_conflict_detail(existing_supplier: dict) -> dict:
    return {
        "code": "inn_conflict",
        "message": "ИНН уже существует в базе",
        "existingSupplierId": existing_supplier.get("id"),
        "existingSupplierName": existing_supplier.get("name"),
        "existingSupplierDomains": existing_supplier.get("domains") or [],
        "existingSupplierEmails": existing_supplier.get("emails") or [],
    }


class AttachDomainRequestDTO(BaseModel):
    domain: str
    email: str | None = None

# Абсолютно минимальный endpoint для проверки
@router.get("/suppliers-empty")
async def suppliers_empty(current_user: dict = Depends(get_current_user)):
    """Absolute minimum endpoint - no parameters, no dependencies."""
    _require_moderator(current_user)
    _require_debug()
    try:
        logger.debug("=== EMPTY ENDPOINT CALLED ===")
    except Exception:
        pass  # Безопасное логирование
    return {"ok": True}


@router.get("/suppliers-debug")
async def debug_suppliers(current_user: dict = Depends(get_current_user)):
    """Debug endpoint without dependencies."""
    _require_moderator(current_user)
    _require_debug()
    try:
        logger.debug("=== DEBUG ENDPOINT CALLED ===")
    except Exception:
        pass
    return {"status": "ok", "message": "Debug endpoint works"}

@router.get("/suppliers-minimal")
async def minimal_suppliers(current_user: dict = Depends(get_current_user)):
    """Minimal endpoint without any parameters."""
    _require_moderator(current_user)
    _require_debug()
    try:
        logger.debug("=== MINIMAL ENDPOINT CALLED ===")
    except Exception:
        pass
    return {"status": "ok", "suppliers": []}

@router.get("/suppliers-simple")
async def simple_suppliers(current_user: dict = Depends(get_current_user)):
    """Simple endpoint - absolute minimum."""
    _require_moderator(current_user)
    _require_debug()
    try:
        logger.debug("=== SIMPLE ENDPOINT CALLED ===")
    except Exception:
        pass
    return {"ok": True}

@router.get("/test")
async def test_endpoint(current_user: dict = Depends(get_current_user)):
    """Test endpoint to verify router works."""
    _require_moderator(current_user)
    _require_debug()
    try:
        logger.debug("=== TEST ENDPOINT CALLED ===")
    except Exception:
        pass
    return {"status": "ok", "message": "Router works"}

@router.get("/suppliers-test")
async def test_suppliers(db = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Test endpoint with DB dependency."""
    _require_moderator(current_user)
    _require_debug()
    try:
        logger.debug("=== TEST ENDPOINT CALLED ===")
        logger.debug("=== DB session obtained ===")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        try:
            logger.error(f"=== TEST ERROR: {e} ===", exc_info=True)
        except Exception:
            pass
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


# Временно переименуем endpoint для проверки
@router.get("/suppliers-new")
async def list_suppliers_new(
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    supplier_type: Optional[str] = Query(default=None, alias="type"),
    current_user: dict = Depends(get_current_user),
):
    """List suppliers - new version for testing."""
    _require_moderator(current_user)
    _require_debug()
    try:
        try:
            logger.debug(f"=== SUPPLIERS-NEW ENDPOINT CALLED ===")
            logger.debug(f"=== Parameters: limit={limit}, offset={offset}, type={supplier_type} ===")
        except Exception:
            pass  # Безопасное логирование
        
        result = {
            "suppliers": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "status": "test_mode"
        }
        try:
            logger.debug("=== Returning result ===")
        except Exception:
            pass
        return result
    except Exception as e:
        try:
            logger.error(f"=== ENDPOINT EXCEPTION: {type(e).__name__}: {e} ===", exc_info=True)
        except Exception:
            pass
        raise

@router.get("/suppliers", response_model=ModeratorSuppliersListResponseDTO)
async def list_suppliers(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    supplier_type: Optional[str] = Query(default=None, alias="type"),
    recent_days: Optional[int] = Query(default=None, alias="recentDays"),
    search: Optional[str] = Query(default=None),
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List suppliers with pagination."""
    _require_moderator(current_user)
    suppliers, total = await list_moderator_suppliers.execute(
        db=db,
        limit=limit,
        offset=offset,
        type_filter=supplier_type,
        recent_days=recent_days,
        search=search,
    )

    from app.adapters.db.repositories import ModeratorSupplierRepository
    repo = ModeratorSupplierRepository(db)
    
    # Batch-load domains and emails for all suppliers (2 queries instead of N*2)
    supplier_ids = [s.id for s in suppliers]
    all_domains_map = await repo.batch_list_domains(supplier_ids)
    all_emails_map = await repo.batch_list_emails(supplier_ids)

    # Convert suppliers to DTOs, handling date fields
    supplier_dtos = []
    for s in suppliers:
        # Convert date fields to strings before validation
        registration_date_str = None
        if s.registration_date:
            if isinstance(s.registration_date, date):
                registration_date_str = s.registration_date.isoformat()
            else:
                registration_date_str = str(s.registration_date)
        
        supplier_domains = all_domains_map.get(s.id, [])
        supplier_emails = all_emails_map.get(s.id, [])

        raw_data_status = getattr(s, "data_status", None)
        has_checko_data = bool(getattr(s, "checko_data", None))
        data_status = raw_data_status or "complete"
        if data_status == "complete" and not has_checko_data:
            data_status = "needs_checko"

        supplier_dict = {
            'id': s.id,
            'name': s.name,
            'inn': s.inn,
            'email': s.email,
            'domain': s.domain,
            'address': s.address,
            'type': s.type,
            'allow_duplicate_inn': getattr(s, "allow_duplicate_inn", False),
            'data_status': data_status,
            'domains': supplier_domains,
            'emails': supplier_emails,
            'ogrn': s.ogrn,
            'kpp': s.kpp,
            'okpo': s.okpo,
            'company_status': s.company_status,
            'registration_date': registration_date_str,
            'legal_address': s.legal_address,
            'phone': s.phone,
            'website': s.website,
            'vk': s.vk,
            'telegram': s.telegram,
            'authorized_capital': s.authorized_capital,
            'revenue': s.revenue,
            'profit': s.profit,
            'finance_year': s.finance_year,
            'legal_cases_count': s.legal_cases_count,
            'legal_cases_sum': s.legal_cases_sum,
            'legal_cases_as_plaintiff': s.legal_cases_as_plaintiff,
            'legal_cases_as_defendant': s.legal_cases_as_defendant,
            'checko_data': s.checko_data,
            'created_at': s.created_at,
            'updated_at': s.updated_at,
        }
        # Decompress checko_data if it's compressed bytes
        from app.utils.checko_compression import decompress_checko_data_to_string
        if supplier_dict.get("checko_data") and isinstance(supplier_dict["checko_data"], bytes):
            try:
                supplier_dict["checko_data"] = decompress_checko_data_to_string(supplier_dict["checko_data"])
            except ValueError:
                supplier_dict["checko_data"] = None

        # Derive structured fields from Checko payload for response-only (do not persist).
        if supplier_dict.get("checko_data"):
            try:
                import json
                from app.usecases.get_checko_data import _format_checko_data_for_frontend

                formatted = _format_checko_data_for_frontend(json.loads(str(supplier_dict["checko_data"])))
                mapping = {
                    "authorizedCapital": "authorized_capital",
                    "financeYear": "finance_year",
                    "legalCasesCount": "legal_cases_count",
                    "legalCasesSum": "legal_cases_sum",
                    "legalCasesAsPlaintiff": "legal_cases_as_plaintiff",
                    "legalCasesAsDefendant": "legal_cases_as_defendant",
                }

                # Direct keys in supplier_dict already match (revenue/profit/website/phone/...)
                for key in ("revenue", "profit", "website", "phone", "vk", "telegram"):
                    if supplier_dict.get(key) in (None, "") and formatted.get(key) not in (None, ""):
                        supplier_dict[key] = formatted.get(key)

                for src_key, dst_key in mapping.items():
                    if supplier_dict.get(dst_key) in (None, "") and formatted.get(src_key) not in (None, ""):
                        supplier_dict[dst_key] = formatted.get(src_key)

                # Fill basic legal fields if missing
                for src_key, dst_key in (
                    ("ogrn", "ogrn"),
                    ("kpp", "kpp"),
                    ("okpo", "okpo"),
                    ("companyStatus", "company_status"),
                    ("registrationDate", "registration_date"),
                    ("legalAddress", "legal_address"),
                ):
                    if supplier_dict.get(dst_key) in (None, "") and formatted.get(src_key) not in (None, ""):
                        supplier_dict[dst_key] = formatted.get(src_key)
            except Exception:
                pass
        
        supplier_dtos.append(ModeratorSupplierDTO.model_validate(supplier_dict, from_attributes=False))
    
    return ModeratorSuppliersListResponseDTO(
        suppliers=supplier_dtos,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/suppliers/{supplier_id}", response_model=ModeratorSupplierDTO)
async def get_supplier(
    supplier_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get supplier by ID."""
    _require_moderator(current_user)
    supplier = await get_moderator_supplier.execute(db=db, supplier_id=supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    # Decompress checko_data for response without mutating ORM state
    from app.utils.checko_compression import decompress_checko_data_to_string
    checko_data_payload = supplier.checko_data
    if checko_data_payload:
        if isinstance(checko_data_payload, memoryview):
            checko_data_payload = bytes(checko_data_payload)
        if isinstance(checko_data_payload, bytes):
            try:
                checko_data_payload = decompress_checko_data_to_string(checko_data_payload)
            except ValueError as e:
                logger.warning(f"Failed to decompress checko_data for supplier {supplier_id}: {e}")
                checko_data_payload = None

    # Ensure data_status reflects missing Checko data
    try:
        if getattr(supplier, "data_status", None) in (None, "", "complete") and not supplier.checko_data:
            supplier.data_status = "needs_checko"
    except Exception:
        pass

    # Avoid lazy-loading in Pydantic validation (async SQLAlchemy relationships).
    from app.adapters.db.repositories import ModeratorSupplierRepository
    repo = ModeratorSupplierRepository(db)
    domains = await repo.list_domains(supplier.id)
    emails = await repo.list_emails(supplier.id)

    payload = {
        "id": supplier.id,
        "name": supplier.name,
        "inn": supplier.inn,
        "email": supplier.email,
        "domain": supplier.domain,
        "address": supplier.address,
        "type": supplier.type,
        "allow_duplicate_inn": supplier.allow_duplicate_inn,
        "data_status": supplier.data_status,
        "domains": domains,
        "emails": emails,
        "ogrn": supplier.ogrn,
        "kpp": supplier.kpp,
        "okpo": supplier.okpo,
        "company_status": supplier.company_status,
        "registration_date": supplier.registration_date,
        "legal_address": supplier.legal_address,
        "phone": supplier.phone,
        "website": supplier.website,
        "vk": supplier.vk,
        "telegram": supplier.telegram,
        "authorized_capital": supplier.authorized_capital,
        "revenue": supplier.revenue,
        "profit": supplier.profit,
        "finance_year": supplier.finance_year,
        "legal_cases_count": supplier.legal_cases_count,
        "legal_cases_sum": supplier.legal_cases_sum,
        "legal_cases_as_plaintiff": supplier.legal_cases_as_plaintiff,
        "legal_cases_as_defendant": supplier.legal_cases_as_defendant,
        "checko_data": checko_data_payload,
        "created_at": supplier.created_at,
        "updated_at": supplier.updated_at,
    }

    if checko_data_payload:
        try:
            import json
            from app.usecases.get_checko_data import _format_checko_data_for_frontend

            formatted = _format_checko_data_for_frontend(json.loads(checko_data_payload))
            for key, value in formatted.items():
                if payload.get(key) in (None, "") and value not in (None, ""):
                    payload[key] = value
        except Exception:
            pass

    return ModeratorSupplierDTO.model_validate(payload, from_attributes=False)


@router.post("/suppliers", response_model=ModeratorSupplierDTO, status_code=201)
async def create_supplier(
    request: CreateModeratorSupplierRequestDTO,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new supplier."""
    _require_moderator(current_user)
    import logging
    logger = logging.getLogger(__name__)
    
    # DEBUG: Log raw request object
    print(f"\n=== CREATE SUPPLIER: RAW REQUEST ===")
    print(f"Request type: {type(request)}")
    print(f"Request fields: {list(request.model_fields.keys())}")
    print(f"registrationDate attribute: {getattr(request, 'registrationDate', 'NOT FOUND')}")
    print(f"legalAddress attribute: {getattr(request, 'legalAddress', 'NOT FOUND')}")
    print(f"financeYear attribute: {getattr(request, 'financeYear', 'NOT FOUND')}")
    print(f"legalCasesCount attribute: {getattr(request, 'legalCasesCount', 'NOT FOUND')}")
    print(f"checkoData attribute length: {len(getattr(request, 'checkoData', '')) if getattr(request, 'checkoData', None) else 0}")
    
    # Convert camelCase to snake_case for database fields
    # Include None values to allow SQLAlchemy to set them as NULL
    # Use exclude_unset=False to include all fields, even if not explicitly set
    supplier_data = request.model_dump(exclude_unset=False, exclude_none=False)
    logger.info(f"create_supplier: received {len(supplier_data)} fields: {list(supplier_data.keys())}")
    
    # Log key fields - use print for immediate visibility
    print(f"\n=== CREATE SUPPLIER: AFTER model_dump ===")
    print(f"Fields received: {list(supplier_data.keys())}")
    for key in ["registrationDate", "legalAddress", "financeYear", "legalCasesCount", "checkoData"]:
        if key in supplier_data:
            value = supplier_data[key]
            if isinstance(value, str) and len(value) > 50:
                print(f"  {key}: [string, length={len(value)}]")
                logger.info(f"  {key}: [string, length={len(value)}]")
            else:
                print(f"  {key}: {type(value).__name__} = {repr(value)}")
                logger.info(f"  {key}: {type(value).__name__} = {repr(value)}")
        else:
            print(f"  {key}: MISSING!")
            logger.warning(f"  {key}: MISSING from supplier_data!")
    
    snake_case_data = {}
    field_mapping = {
        "companyStatus": "company_status",
        "registrationDate": "registration_date",
        "legalAddress": "legal_address",
        "authorizedCapital": "authorized_capital",
        "financeYear": "finance_year",
        "legalCasesCount": "legal_cases_count",
        "legalCasesSum": "legal_cases_sum",
        "legalCasesAsPlaintiff": "legal_cases_as_plaintiff",
        "legalCasesAsDefendant": "legal_cases_as_defendant",
        "checkoData": "checko_data",
        "allowDuplicateInn": "allow_duplicate_inn",
        "dataStatus": "data_status",
    }
    
    # Explicitly include all fields, even if they are None or empty strings
    for key, value in supplier_data.items():
        db_key = field_mapping.get(key, key)
        # Preserve None, empty strings, and 0 as valid values
        snake_case_data[db_key] = value
        if key in ["registrationDate", "legalAddress", "financeYear", "legalCasesCount", "checkoData"]:
            logger.debug(f"Mapped {key} -> {db_key}: {type(value).__name__}")
    
    logger.info(f"create_supplier: mapped to {len(snake_case_data)} fields: {list(snake_case_data.keys())}")
    
    # Log key mapped fields - use print for immediate visibility
    print(f"\n=== MAPPED FIELDS ===")
    for key in ["registration_date", "legal_address", "finance_year", "legal_cases_count", "checko_data"]:
        if key in snake_case_data:
            value = snake_case_data[key]
            if isinstance(value, str) and len(value) > 50:
                print(f"  {key}: [string, length={len(value)}]")
                logger.info(f"  {key}: [string, length={len(value)}]")
            else:
                print(f"  {key}: {type(value).__name__} = {repr(value)}")
                logger.info(f"  {key}: {type(value).__name__} = {repr(value)}")
        else:
            print(f"  {key}: MISSING!")
            logger.warning(f"  {key}: MISSING from snake_case_data!")
    
    # Normalize domains/emails (root domain)
    domains = _normalize_domains(supplier_data.get("domains"), supplier_data.get("domain"))
    emails = _normalize_emails(supplier_data.get("emails"), supplier_data.get("email"))
    primary_domain = domains[0] if domains else None
    primary_email = emails[0] if emails else None
    snake_case_data["domain"] = primary_domain
    snake_case_data["email"] = primary_email
    if snake_case_data.get("data_status") in (None, ""):
        snake_case_data.pop("data_status", None)
    if snake_case_data.get("allow_duplicate_inn") is None:
        snake_case_data["allow_duplicate_inn"] = False

    # Required INN + email
    _validate_required_inn_email(snake_case_data.get("inn"), primary_email)

    # CRITICAL: Check if data is actually present before calling usecase
    if not snake_case_data.get("registration_date") and not snake_case_data.get("legal_address"):
        print("WARNING: Key fields are missing from snake_case_data!")
        logger.error("Key fields (registration_date, legal_address) are missing from snake_case_data!")
        logger.error(f"snake_case_data keys: {list(snake_case_data.keys())}")
        logger.error(f"snake_case_data values: {snake_case_data}")

    # INN uniqueness (unless allow_duplicate_inn)
    from app.adapters.db.repositories import ModeratorSupplierRepository
    repo = ModeratorSupplierRepository(db)
    if not bool(snake_case_data.get("allow_duplicate_inn")):
        existing = await repo.get_by_inn(str(snake_case_data.get("inn") or "").strip())
        if existing is not None:
            existing_domains = await repo.list_domains(existing.id)
            existing_emails = await repo.list_emails(existing.id)
            detail = _build_inn_conflict_detail(
                {
                    "id": existing.id,
                    "name": existing.name,
                    "domains": existing_domains,
                    "emails": existing_emails,
                }
            )
            raise HTTPException(status_code=409, detail=detail)
    
    supplier = await create_moderator_supplier.execute(
        db=db,
        supplier_data=snake_case_data
    )
    await db.commit()
    
    # CRITICAL FIX: Reload supplier from DB to ensure we have all data
    # Refresh doesn't always work correctly, so we reload the object
    from app.adapters.db.repositories import ModeratorSupplierRepository
    repo = ModeratorSupplierRepository(db)
    supplier = await repo.get_by_id(supplier.id)

    # Persist domains/emails
    try:
        await repo.replace_domains(supplier.id, domains)
        await repo.replace_emails(supplier.id, emails)
        await db.commit()
    except Exception:
        await db.rollback()
    
    # Log what was actually saved
    print(f"\n=== AFTER RELOAD FROM DB ===")
    print(f"  registration_date: {supplier.registration_date} (type: {type(supplier.registration_date)})")
    print(f"  legal_address: {supplier.legal_address}")
    print(f"  finance_year: {supplier.finance_year}")
    print(f"  legal_cases_count: {supplier.legal_cases_count}")
    print(f"  checko_data length: {len(supplier.checko_data) if supplier.checko_data else 0}")
    logger.info("=== After reload from DB ===")
    logger.info(f"  registration_date: {supplier.registration_date}")
    logger.info(f"  legal_address: {supplier.legal_address[:50] if supplier.legal_address else None}")
    logger.info(f"  finance_year: {supplier.finance_year}")
    logger.info(f"  legal_cases_count: {supplier.legal_cases_count}")
    logger.info(f"  checko_data length: {len(supplier.checko_data) if supplier.checko_data else 0}")
    
    # Decompress checko_data if it's compressed bytes
    from app.utils.checko_compression import decompress_checko_data_to_string
    if supplier.checko_data and isinstance(supplier.checko_data, bytes):
        try:
            supplier.checko_data = decompress_checko_data_to_string(supplier.checko_data)
            logger.debug(f"Decompressed checko_data for supplier {supplier.id}")
        except ValueError as e:
            logger.warning(f"Failed to decompress checko_data for supplier {supplier.id}: {e}")
            supplier.checko_data = None

    # Load domains/emails
    from app.adapters.db.repositories import ModeratorSupplierRepository
    repo = ModeratorSupplierRepository(db)
    try:
        supplier.domains = await repo.list_domains(supplier.id)
        supplier.emails = await repo.list_emails(supplier.id)
    except Exception:
        pass
    
    # Create DTO with from_attributes=True to properly read from SQLAlchemy model
    # Attach domains/emails for DTO
    try:
        supplier.domains = await repo.list_domains(supplier.id)
        supplier.emails = await repo.list_emails(supplier.id)
    except Exception:
        pass
    dto = ModeratorSupplierDTO.model_validate(supplier, from_attributes=True)
    
    return dto


@router.put("/suppliers/{supplier_id}")
async def update_supplier(
    supplier_id: int,
    request: UpdateModeratorSupplierRequestDTO,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update supplier."""
    _require_moderator(current_user)
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== UPDATE SUPPLIER START: supplier_id={supplier_id} ===")
    
    try:
        # Workaround: Use text() instead of update() to avoid MissingGreenlet
        from app.adapters.db.repositories import ModeratorSupplierRepository

        repo = ModeratorSupplierRepository(db)
        existing = await repo.get_by_id(supplier_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Supplier not found")

        patch = request.model_dump(exclude_unset=True, exclude_none=False)

        domains_in_payload = "domains" in patch or "domain" in patch
        emails_in_payload = "emails" in patch or "email" in patch
        domains = _normalize_domains(patch.get("domains"), patch.get("domain")) if domains_in_payload else None
        emails = _normalize_emails(patch.get("emails"), patch.get("email")) if emails_in_payload else None

        patch.pop("domains", None)
        patch.pop("emails", None)
        if domains_in_payload:
            patch["domain"] = domains[0] if domains else None
        if emails_in_payload:
            patch["email"] = emails[0] if emails else None

        # Block updates that would remove required INN/email
        merged_inn = patch.get("inn") if "inn" in patch else getattr(existing, "inn", None)
        merged_email = patch.get("email") if "email" in patch else getattr(existing, "email", None)
        _validate_required_inn_email(merged_inn, merged_email)

        supplier = await update_moderator_supplier.execute(db=db, supplier_id=supplier_id, supplier_data=patch)
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")

        if domains_in_payload:
            await repo.replace_domains(supplier_id, domains or [])
        if emails_in_payload:
            await repo.replace_emails(supplier_id, emails or [])

        await db.commit()

        supplier = await repo.get_by_id(supplier_id)
        domains_list = await repo.list_domains(supplier_id)
        emails_list = await repo.list_emails(supplier_id)

        from app.utils.checko_compression import decompress_checko_data_to_string
        checko_data_payload = supplier.checko_data if supplier else None
        if checko_data_payload:
            if isinstance(checko_data_payload, memoryview):
                checko_data_payload = bytes(checko_data_payload)
            if isinstance(checko_data_payload, bytes):
                try:
                    checko_data_payload = decompress_checko_data_to_string(checko_data_payload)
                except ValueError as e:
                    logger.warning(f"Failed to decompress checko_data for supplier {supplier_id}: {e}")
                    checko_data_payload = None

        payload = {
            "id": supplier.id,
            "name": supplier.name,
            "inn": supplier.inn,
            "email": supplier.email,
            "domain": supplier.domain,
            "address": supplier.address,
            "type": supplier.type,
            "allow_duplicate_inn": supplier.allow_duplicate_inn,
            "data_status": supplier.data_status,
            "domains": domains_list,
            "emails": emails_list,
            "ogrn": supplier.ogrn,
            "kpp": supplier.kpp,
            "okpo": supplier.okpo,
            "company_status": supplier.company_status,
            "registration_date": supplier.registration_date,
            "legal_address": supplier.legal_address,
            "phone": supplier.phone,
            "website": supplier.website,
            "vk": supplier.vk,
            "telegram": supplier.telegram,
            "authorized_capital": supplier.authorized_capital,
            "revenue": supplier.revenue,
            "profit": supplier.profit,
            "finance_year": supplier.finance_year,
            "legal_cases_count": supplier.legal_cases_count,
            "legal_cases_sum": supplier.legal_cases_sum,
            "legal_cases_as_plaintiff": supplier.legal_cases_as_plaintiff,
            "legal_cases_as_defendant": supplier.legal_cases_as_defendant,
            "checko_data": checko_data_payload,
            "created_at": supplier.created_at,
            "updated_at": supplier.updated_at,
        }

        logger.info(f"=== UPDATE SUPPLIER SUCCESS ===")
        return ModeratorSupplierDTO.model_validate(payload, from_attributes=False)
        
    except Exception as e:
        logger.error(f"=== UPDATE SUPPLIER ERROR: {type(e).__name__}: {e} ===", exc_info=True)
        await db.rollback()
        raise


@router.post("/suppliers/{supplier_id}/attach-domain", response_model=ModeratorSupplierDTO)
async def attach_domain(
    supplier_id: int,
    payload: AttachDomainRequestDTO,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Attach a domain (and optional email) to an existing supplier."""
    _require_moderator(current_user)
    from app.adapters.db.repositories import ModeratorSupplierRepository

    repo = ModeratorSupplierRepository(db)
    supplier = await repo.get_by_id(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    domain = normalize_domain_root(payload.domain)
    if not domain:
        raise HTTPException(status_code=422, detail="Domain is required")
    await repo.add_domain(supplier.id, domain, is_primary=not bool(supplier.domain))
    if not supplier.domain:
        supplier.domain = domain

    if payload.email:
        email = str(payload.email).strip().lower()
        if email:
            await repo.add_email(supplier.id, email, is_primary=not bool(supplier.email))
            if not supplier.email:
                supplier.email = email

    await db.commit()

    supplier = await repo.get_by_id(supplier.id)
    try:
        supplier.domains = await repo.list_domains(supplier.id)
        supplier.emails = await repo.list_emails(supplier.id)
    except Exception:
        pass
    return ModeratorSupplierDTO.model_validate(supplier, from_attributes=True)


@router.delete("/suppliers/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete supplier."""
    _require_moderator(current_user)
    success = await delete_moderator_supplier.execute(db=db, supplier_id=supplier_id)
    if not success:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    await db.commit()


@router.get("/suppliers/{supplier_id}/keywords", response_model=SupplierKeywordsResponseDTO)
async def get_supplier_keywords_endpoint(
    supplier_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get supplier keywords."""
    _require_moderator(current_user)
    keywords = await get_supplier_keywords.execute(db=db, supplier_id=supplier_id)
    return SupplierKeywordsResponseDTO(keywords=keywords)
