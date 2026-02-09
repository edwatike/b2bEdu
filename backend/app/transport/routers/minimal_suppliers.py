"""Minimal update endpoint to test MissingGreenlet issue."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.adapters.db.session import get_db
from app.adapters.db.models import ModeratorSupplierModel
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator as _require_moderator

router = APIRouter()
logger = logging.getLogger(__name__)

@router.put("/suppliers/{supplier_id}/minimal")
async def minimal_update(
    supplier_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Minimal update to test MissingGreenlet issue."""
    _require_moderator(current_user)
    
    logger.info(f"=== MINIMAL UPDATE START: supplier_id={supplier_id} ===")
    
    try:
        # Direct SQLAlchemy update without repository
        result = await db.execute(
            select(ModeratorSupplierModel).where(ModeratorSupplierModel.id == supplier_id)
        )
        supplier = result.scalar_one_or_none()
        
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        
        # Simple field update
        supplier.address = f"Minimal test at {__import__('datetime').datetime.now()}"
        
        # No explicit commit - let FastAPI handle it
        logger.info(f"=== MINIMAL UPDATE SUCCESS ===")
        
        return {"status": "success", "address": supplier.address}
        
    except Exception as e:
        logger.error(f"=== MINIMAL UPDATE ERROR: {type(e).__name__}: {e} ===", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {e}")
