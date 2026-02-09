"""Sync workaround for MissingGreenlet issue."""
import logging
from fastapi import APIRouter, HTTPException
import asyncio
from functools import wraps

router = APIRouter()
logger = logging.getLogger(__name__)

def sync_to_async(func):
    """Decorator to convert sync function to async."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    return wrapper

@sync_to_async
def sync_update_supplier(supplier_id: int):
    """Synchronous update function."""
    from app.adapters.db.session import AsyncSessionLocal
    from sqlalchemy import create_engine, text
    from app.config import settings
    
    # Create sync engine
    sync_engine = create_engine(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    
    with sync_engine.begin() as conn:
        result = conn.execute(
            text("UPDATE moderator_suppliers SET address = :address WHERE id = :id"),
            {"address": f"Sync test at {__import__('datetime').datetime.now()}", "id": supplier_id}
        )
        return result.rowcount > 0

@router.put("/suppliers/{supplier_id}/sync-workaround")
async def sync_workaround_update(supplier_id: int):
    """Test update using sync-to-async workaround."""
    logger.info(f"=== SYNC WORKAROUND UPDATE START: supplier_id={supplier_id} ===")
    
    try:
        success = await sync_update_supplier(supplier_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Supplier not found")
        
        logger.info(f"=== SYNC WORKAROUND UPDATE SUCCESS ===")
        
        return {
            "status": "success",
            "message": f"Sync workaround completed for supplier {supplier_id}",
            "timestamp": str(__import__('datetime').datetime.now())
        }
        
    except Exception as e:
        logger.error(f"=== SYNC WORKAROUND UPDATE ERROR: {type(e).__name__}: {e} ===", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {e}")
