"""Audit logging utility for tracking data changes."""
import json
import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def log_audit(
    db: AsyncSession,
    table_name: str,
    operation: str,
    record_id: str,
    old_data: Optional[Dict[str, Any]] = None,
    new_data: Optional[Dict[str, Any]] = None,
    changed_by: Optional[str] = None
) -> None:
    """
    Log audit entry for data change.
    
    Args:
        db: Database session
        table_name: Name of the table that was modified
        operation: Type of operation (INSERT, UPDATE, DELETE)
        record_id: ID of the record that was modified
        old_data: Previous data (for UPDATE and DELETE)
        new_data: New data (for INSERT and UPDATE)
        changed_by: User or system that made the change
    """
    try:
        old_data_json = json.dumps(old_data) if old_data else None
        new_data_json = json.dumps(new_data) if new_data else None
        
        await db.execute(
            text("""
                INSERT INTO audit_log (table_name, operation, record_id, old_data, new_data, changed_by)
                VALUES (:table_name, :operation, :record_id, :old_data, :new_data, :changed_by)
            """),
            {
                "table_name": table_name,
                "operation": operation,
                "record_id": str(record_id),
                "old_data": old_data_json,
                "new_data": new_data_json,
                "changed_by": changed_by or "system"
            }
        )
        await db.flush()
        logger.debug(f"Audit log entry created: {operation} on {table_name}.{record_id}")
    except Exception as e:
        # Не прерываем выполнение при ошибке аудита, только логируем
        logger.error(f"Failed to create audit log entry: {e}", exc_info=True)



















