"""Use case for updating a moderator supplier."""
import logging
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.repositories import ModeratorSupplierRepository
from app.utils.checko_compression import compress_checko_data_string

logger = logging.getLogger(__name__)


async def execute(db: AsyncSession, supplier_id: int, supplier_data: dict):
    """Update moderator supplier."""
    logger.info(f"update_moderator_supplier.execute called with supplier_id={supplier_id}, data keys: {list(supplier_data.keys())}")
    # Log all key fields
    for key in ["registration_date", "legal_address", "finance_year", "legal_cases_count", "checko_data"]:
        if key in supplier_data:
            value = supplier_data[key]
            if isinstance(value, str) and len(value) > 50:
                logger.info(f"  {key}: [string, length={len(value)}]")
            else:
                logger.info(f"  {key}: {type(value).__name__} = {repr(value)}")
        else:
            logger.debug(f"  {key}: not present")
    
    # Log checkoData size if present
    if "checko_data" in supplier_data and supplier_data["checko_data"]:
        checko_size = len(str(supplier_data["checko_data"]))
        logger.info(f"checko_data size: {checko_size} bytes")
    elif "checkoData" in supplier_data and supplier_data["checkoData"]:
        checko_size = len(str(supplier_data["checkoData"]))
        logger.info(f"checkoData size: {checko_size} bytes")
    
    # Log types and values of key fields being updated
    key_fields = ["ogrn", "kpp", "registration_date", "legal_address", 
                  "phone", "website", "revenue", "profit", "finance_year", 
                  "legal_cases_count", "checko_data"]
    for field in key_fields:
        if field in supplier_data:
            value = supplier_data[field]
            value_type = type(value).__name__
            if isinstance(value, str) and len(value) > 50:
                logger.debug(f"Updating {field}: {value_type}, length: {len(value)}")
            else:
                logger.debug(f"Updating {field}: {value_type}, value: {value}")
    
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
    
    # Log final data before update
    logger.info(f"Final supplier_data keys before update: {list(supplier_data.keys())}")
    for key in ["registration_date", "legal_address", "finance_year", "legal_cases_count", "checko_data"]:
        if key in supplier_data:
            value = supplier_data[key]
            if isinstance(value, str) and len(value) > 50:
                logger.info(f"  {key}: [string, length={len(value)}]")
            elif isinstance(value, bytes):
                logger.info(f"  {key}: [bytes, length={len(value)}]")
            else:
                logger.info(f"  {key}: {type(value).__name__} = {repr(value)}")
    
    repo = ModeratorSupplierRepository(db)
    result = await repo.update(supplier_id, supplier_data)
    if result:
        logger.info(f"update_moderator_supplier.execute completed successfully, supplier_id: {result.id}")
    else:
        logger.warning(f"update_moderator_supplier.execute failed, supplier_id: {supplier_id} not found")
    return result

