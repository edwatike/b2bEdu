"""Router for moderator suppliers."""
import logging
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.adapters.db.session import get_db
from app.transport.routers.auth import can_access_moderator_zone, get_current_user
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

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_moderator(current_user: dict):
    if not can_access_moderator_zone(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

# Абсолютно минимальный endpoint для проверки
@router.get("/suppliers-empty")
async def suppliers_empty(current_user: dict = Depends(get_current_user)):
    """Absolute minimum endpoint - no parameters, no dependencies."""
    _require_moderator(current_user)
    try:
        logger.debug("=== EMPTY ENDPOINT CALLED ===")
    except Exception:
        pass  # Безопасное логирование
    return {"ok": True}


@router.get("/suppliers-debug")
async def debug_suppliers(current_user: dict = Depends(get_current_user)):
    """Debug endpoint without dependencies."""
    _require_moderator(current_user)
    try:
        logger.debug("=== DEBUG ENDPOINT CALLED ===")
    except Exception:
        pass
    return {"status": "ok", "message": "Debug endpoint works"}

@router.get("/suppliers-minimal")
async def minimal_suppliers(current_user: dict = Depends(get_current_user)):
    """Minimal endpoint without any parameters."""
    _require_moderator(current_user)
    try:
        logger.debug("=== MINIMAL ENDPOINT CALLED ===")
    except Exception:
        pass
    return {"status": "ok", "suppliers": []}

@router.get("/suppliers-simple")
async def simple_suppliers(current_user: dict = Depends(get_current_user)):
    """Simple endpoint - absolute minimum."""
    _require_moderator(current_user)
    try:
        logger.debug("=== SIMPLE ENDPOINT CALLED ===")
    except Exception:
        pass
    return {"ok": True}

@router.get("/test")
async def test_endpoint(current_user: dict = Depends(get_current_user)):
    """Test endpoint to verify router works."""
    _require_moderator(current_user)
    try:
        logger.debug("=== TEST ENDPOINT CALLED ===")
    except Exception:
        pass
    return {"status": "ok", "message": "Router works"}

@router.get("/suppliers-test")
async def test_suppliers(db = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Test endpoint with DB dependency."""
    _require_moderator(current_user)
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
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    supplier_type: Optional[str] = Query(default=None, alias="type"),
    current_user: dict = Depends(get_current_user),
):
    """List suppliers - new version for testing."""
    _require_moderator(current_user)
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
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List suppliers with pagination."""
    _require_moderator(current_user)
    suppliers, total = await list_moderator_suppliers.execute(
        db=db,
        limit=limit,
        offset=offset,
        type_filter=supplier_type
    )
    
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
        
        supplier_dict = {
            'id': s.id,
            'name': s.name,
            'inn': s.inn,
            'email': s.email,
            'domain': s.domain,
            'address': s.address,
            'type': s.type,
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
    
    # Use from_attributes=True to properly read from SQLAlchemy model
    return ModeratorSupplierDTO.model_validate(supplier, from_attributes=True)


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
    
    # CRITICAL: Check if data is actually present before calling usecase
    if not snake_case_data.get("registration_date") and not snake_case_data.get("legal_address"):
        print("WARNING: Key fields are missing from snake_case_data!")
        logger.error("Key fields (registration_date, legal_address) are missing from snake_case_data!")
        logger.error(f"snake_case_data keys: {list(snake_case_data.keys())}")
        logger.error(f"snake_case_data values: {snake_case_data}")
    
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
    
    # Create DTO with from_attributes=True to properly read from SQLAlchemy model
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
    }
    
    for key, value in update_data.items():
        db_key = field_mapping.get(key, key)
        # Log key fields for debugging
        if key in ["registrationDate", "legalAddress", "financeYear", "legalCasesCount", "checkoData"]:
            value_preview = str(value)[:50] if value and isinstance(value, str) else value
            logger.debug(f"Mapping {key} -> {db_key}: {type(value).__name__} = {value_preview}")
        snake_case_data[db_key] = value
    
    logger.info(f"update_supplier: mapped to {len(snake_case_data)} fields: {list(snake_case_data.keys())}")
    
    supplier = await update_moderator_supplier.execute(
        db=db,
        supplier_id=supplier_id,
        supplier_data=snake_case_data
    )
    
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    
    await db.commit()
    
    # Reload supplier from DB to ensure we have all data
    from app.adapters.db.repositories import ModeratorSupplierRepository
    repo = ModeratorSupplierRepository(db)
    supplier = await repo.get_by_id(supplier.id)
    
    # Decompress checko_data if it's compressed bytes
    from app.utils.checko_compression import decompress_checko_data_to_string
    if supplier.checko_data and isinstance(supplier.checko_data, bytes):
        try:
            supplier.checko_data = decompress_checko_data_to_string(supplier.checko_data)
        except ValueError as e:
            logger.warning(f"Failed to decompress checko_data for supplier {supplier.id}: {e}")
            supplier.checko_data = None
    
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

