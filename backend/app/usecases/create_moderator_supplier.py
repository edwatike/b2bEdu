"""Use case for creating a moderator supplier."""
import logging
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ModeratorSupplierRepository
from app.utils.checko_compression import compress_checko_data_string

logger = logging.getLogger(__name__)


async def execute(db: AsyncSession, supplier_data: dict):
    """Create a new moderator supplier."""
    logger.info(f"create_moderator_supplier.execute called with data keys: {list(supplier_data.keys())}")
    
    # Log checkoData size if present (check both camelCase and snake_case)
    checko_value = supplier_data.get("checko_data") or supplier_data.get("checkoData")
    if checko_value:
        checko_size = len(str(checko_value))
        logger.info(f"checko_data size: {checko_size} bytes")
    else:
        logger.warning("checko_data is missing or empty in supplier_data")
    
    # Log types of key fields (check both camelCase and snake_case)
    key_fields_mapping = {
        "name": ["name"],
        "inn": ["inn"],
        "ogrn": ["ogrn"],
        "kpp": ["kpp"],
        "registration_date": ["registrationDate", "registration_date"],
        "legal_address": ["legalAddress", "legal_address"],
        "phone": ["phone"],
        "website": ["website"],
        "revenue": ["revenue"],
        "profit": ["profit"],
        "finance_year": ["financeYear", "finance_year"],
        "legal_cases_count": ["legalCasesCount", "legal_cases_count"],
        "checko_data": ["checkoData", "checko_data"]
    }
    for field_name, possible_keys in key_fields_mapping.items():
        value = None
        for key in possible_keys:
            if key in supplier_data:
                value = supplier_data[key]
                break
        if value is not None:
            value_type = type(value).__name__
            if isinstance(value, str) and len(value) > 50:
                logger.debug(f"{field_name}: {value_type}, length: {len(value)}")
            else:
                logger.debug(f"{field_name}: {value_type}, value: {repr(value)}")
        else:
            logger.debug(f"{field_name}: not present in supplier_data")
    
    # Normalize camelCase to snake_case for all mapped fields FIRST
    field_mapping = {
        "registrationDate": "registration_date",
        "legalAddress": "legal_address",
        "companyStatus": "company_status",
        "authorizedCapital": "authorized_capital",
        "financeYear": "finance_year",
        "legalCasesCount": "legal_cases_count",
        "legalCasesSum": "legal_cases_sum",
        "legalCasesAsPlaintiff": "legal_cases_as_plaintiff",
        "legalCasesAsDefendant": "legal_cases_as_defendant",
        "checkoData": "checko_data"
    }
    for camel_key, snake_key in field_mapping.items():
        if camel_key in supplier_data and snake_key not in supplier_data:
            supplier_data[snake_key] = supplier_data.pop(camel_key)
            logger.debug(f"Normalized {camel_key} -> {snake_key}")
    
    # Handle registration_date conversion to date object AFTER normalization
    if "registration_date" in supplier_data:
        value = supplier_data["registration_date"]
        if value and isinstance(value, str) and value.strip():
            try:
                supplier_data["registration_date"] = date.fromisoformat(value.strip())
                logger.info(f"Converted registration_date to date: {supplier_data['registration_date']}")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse registration_date: {e}, setting to None")
                supplier_data["registration_date"] = None
        elif not value or (isinstance(value, str) and not value.strip()):
            # Empty string or None -> set to None
            supplier_data["registration_date"] = None
            logger.debug(f"Set registration_date to None (empty or None value)")
        elif isinstance(value, date):
            # Already a date object, keep it
            logger.debug(f"registration_date is already a date object: {value}")
    
    # Compress checko_data if present (string -> compressed bytes)
    if "checko_data" in supplier_data and supplier_data["checko_data"]:
        checko_data_value = supplier_data["checko_data"]
        if isinstance(checko_data_value, str):
            try:
                compressed = compress_checko_data_string(checko_data_value)
                supplier_data["checko_data"] = compressed
                logger.info(f"Compressed checko_data: {len(checko_data_value)} -> {len(compressed)} bytes")
            except ValueError as e:
                logger.warning(f"Failed to compress checko_data: {e}, storing as-is")
        elif isinstance(checko_data_value, bytes):
            # Already compressed, keep as-is
            logger.debug("checko_data is already bytes (compressed)")
    
    # Final check - log all key fields before passing to repository
    print(f"\n=== FINAL DATA BEFORE REPOSITORY ===")
    for key in ["registration_date", "legal_address", "finance_year", "legal_cases_count", "checko_data"]:
        if key in supplier_data:
            value = supplier_data[key]
            if isinstance(value, str) and len(value) > 50:
                print(f"  {key}: [string, length={len(value)}]")
            elif isinstance(value, bytes):
                print(f"  {key}: [bytes, length={len(value)}]")
            else:
                print(f"  {key}: {type(value).__name__} = {repr(value)}")
        else:
            print(f"  {key}: MISSING!")
    logger.info(f"Final supplier_data keys before repository: {list(supplier_data.keys())}")
    
    repo = ModeratorSupplierRepository(db)
    result = await repo.create(supplier_data)
    logger.info(f"create_moderator_supplier.execute completed, supplier_id: {result.id}")
    return result

