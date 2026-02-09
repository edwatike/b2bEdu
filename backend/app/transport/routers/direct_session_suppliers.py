"""Direct session test to isolate MissingGreenlet issue."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from app.adapters.db.session import AsyncSessionLocal
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator as _require_moderator

router = APIRouter()
logger = logging.getLogger(__name__)

@router.put("/suppliers/{supplier_id}/direct-session")
async def direct_session_update(
    supplier_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Test update using direct session creation (no dependency injection)."""
    _require_moderator(current_user)
    
    logger.info(f"=== DIRECT SESSION UPDATE START: supplier_id={supplier_id} ===")
    
    async with AsyncSessionLocal() as db:
        try:
            from sqlalchemy import select
            from app.adapters.db.models import ModeratorSupplierModel
            
            # Direct SQLAlchemy operations
            result = await db.execute(
                select(ModeratorSupplierModel).where(ModeratorSupplierModel.id == supplier_id)
            )
            supplier = result.scalar_one_or_none()
            
            if not supplier:
                raise HTTPException(status_code=404, detail="Supplier not found")
            
            # Simple update
            supplier.address = f"Direct session test at {__import__('datetime').datetime.now()}"
            
            await db.commit()
            
            logger.info(f"=== DIRECT SESSION UPDATE SUCCESS ===")
            return {"status": "success", "address": supplier.address}
            
        except Exception as e:
            logger.error(f"=== DIRECT SESSION UPDATE ERROR: {type(e).__name__}: {e} ===", exc_info=True)
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Error: {e}")
