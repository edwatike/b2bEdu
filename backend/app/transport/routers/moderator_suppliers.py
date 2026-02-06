"""Router for moderator suppliers."""
import logging
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.adapters.db.session import get_db
from app.transport.routers.auth import can_access_moderator_zone, get_current_user
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


def _require_moderator(current_user: dict):
    if not can_access_moderator_zone(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

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
    if not re.match(r"^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$", str(email).strip()):
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
        recent_days=recent_days
    )

    from app.adapters.db.repositories import ModeratorSupplierRepository
    repo = ModeratorSupplierRepository(db)
    
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
        
        supplier_domains = await repo.list_domains(s.id)
        supplier_emails = await repo.list_emails(s.id)

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
    
    # Decompress checko_data if it's compressed bytes or memoryview
    from app.utils.checko_compression import decompress_checko_data_to_string
    if supplier.checko_data:
        # Convert memoryview to bytes if needed
        if isinstance(supplier.checko_data, memoryview):
            supplier.checko_data = bytes(supplier.checko_data)
        
        if isinstance(supplier.checko_data, bytes):
            try:
                supplier.checko_data = decompress_checko_data_to_string(supplier.checko_data)
            except ValueError as e:
                logger.warning(f"Failed to decompress checko_data for supplier {supplier_id}: {e}")
                supplier.checko_data = None

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
        "checko_data": supplier.checko_data,
        "created_at": supplier.created_at,
        "updated_at": supplier.updated_at,
    }

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


@router.put("/suppliers/{supplier_id}", response_model=ModeratorSupplierDTO)
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
    
    # Convert camelCase to snake_case for database fields
    # exclude_unset=True: only update fields that were explicitly set
    # exclude_none=False: allow updating fields to None
    update_data = request.model_dump(exclude_unset=True, exclude_none=False)
    logger.info(f"update_supplier: received {len(update_data)} fields: {list(update_data.keys())}")

    from app.adapters.db.repositories import ModeratorSupplierRepository
    repo = ModeratorSupplierRepository(db)
    current = await repo.get_by_id(supplier_id)
    if not current:
        raise HTTPException(status_code=404, detail="Supplier not found")

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
    
    for key, value in update_data.items():
        db_key = field_mapping.get(key, key)
        # Log key fields for debugging
        if key in ["registrationDate", "legalAddress", "financeYear", "legalCasesCount", "checkoData"]:
            value_preview = str(value)[:50] if value and isinstance(value, str) else value
            logger.debug(f"Mapping {key} -> {db_key}: {type(value).__name__} = {value_preview}")
        snake_case_data[db_key] = value
    
    logger.info(f"update_supplier: mapped to {len(snake_case_data)} fields: {list(snake_case_data.keys())}")
    
    # Normalize domains/emails
    domains = _normalize_domains(update_data.get("domains"), update_data.get("domain"))
    emails = _normalize_emails(update_data.get("emails"), update_data.get("email"))
    if domains:
        snake_case_data["domain"] = domains[0]
    if emails:
        snake_case_data["email"] = emails[0]
    if "data_status" in snake_case_data and snake_case_data.get("data_status") in (None, ""):
        snake_case_data.pop("data_status", None)

    # Enforce required INN+email after update
    final_inn = str(snake_case_data.get("inn") or current.inn or "").strip()
    final_email = str(snake_case_data.get("email") or current.email or "").strip()
    _validate_required_inn_email(final_inn, final_email)

    # INN uniqueness (unless allow_duplicate_inn)
    allow_dup = snake_case_data.get("allow_duplicate_inn")
    if allow_dup is None:
        allow_dup = getattr(current, "allow_duplicate_inn", False)
    if not bool(allow_dup):
        if final_inn:
            existing = await repo.get_by_inn(final_inn)
            if existing is not None and int(existing.id) != int(supplier_id):
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

    supplier = await update_moderator_supplier.execute(
        db=db,
        supplier_id=supplier_id,
        supplier_data=snake_case_data
    )
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    await db.commit()
    
    # Reload supplier from DB to ensure we have all data
    supplier = await repo.get_by_id(supplier.id)

    # Update domains/emails if provided
    if domains:
        try:
            await repo.replace_domains(supplier.id, domains)
            await db.commit()
        except Exception:
            await db.rollback()
    if emails:
        try:
            await repo.replace_emails(supplier.id, emails)
            await db.commit()
        except Exception:
            await db.rollback()
    
    # Decompress checko_data if it's compressed bytes
    from app.utils.checko_compression import decompress_checko_data_to_string
    if supplier.checko_data and isinstance(supplier.checko_data, bytes):
        try:
            supplier.checko_data = decompress_checko_data_to_string(supplier.checko_data)
        except ValueError as e:
            logger.warning(f"Failed to decompress checko_data for supplier {supplier.id}: {e}")
            supplier.checko_data = None
    
    # Attach domains/emails
    try:
        supplier.domains = await repo.list_domains(supplier.id)
        supplier.emails = await repo.list_emails(supplier.id)
    except Exception:
        pass

    return ModeratorSupplierDTO.model_validate(supplier, from_attributes=True)


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
