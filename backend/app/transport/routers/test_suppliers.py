"""Test endpoint to isolate the MissingGreenlet issue."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from app.adapters.db.session import get_db
from app.transport.routers.auth import get_current_user
from app.utils.authz import require_moderator as _require_moderator

router = APIRouter()
logger = logging.getLogger(__name__)

@router.put("/suppliers/{supplier_id}/test-minimal")
async def test_minimal_update(
    supplier_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Minimal test update to isolate MissingGreenlet issue."""
    _require_moderator(current_user)
    
    logger.info(f"=== TEST MINIMAL UPDATE START: supplier_id={supplier_id} ===")
    logger.info(f"DB session type: {type(db)}")
    
    try:
        # Test 1: Simple get_by_id
        from app.adapters.db.repositories import ModeratorSupplierRepository
        repo = ModeratorSupplierRepository(db)
        
        logger.info("Test 1: Getting supplier by ID...")
        supplier = await repo.get_by_id(supplier_id)
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        logger.info(f"Test 1 SUCCESS: Got supplier {supplier.name}")
        
        # Test 2: Simple update with minimal data
        logger.info("Test 2: Testing simple update...")
        test_data = {"address": f"Test address at {__import__('datetime').datetime.now()}"}
        
        result = await repo.update(supplier_id, test_data)
        if not result:
            raise HTTPException(status_code=404, detail="Update failed")
        logger.info(f"Test 2 SUCCESS: Updated address to {result.address}")
        
        # Test 3: Simple commit
        logger.info("Test 3: Testing commit...")
        await db.commit()
        logger.info("Test 3 SUCCESS: Committed")
        
        # Test 4: Another get after commit
        logger.info("Test 4: Getting supplier after commit...")
        supplier_after = await repo.get_by_id(supplier_id)
        logger.info(f"Test 4 SUCCESS: Got supplier after commit: {supplier_after.address}")
        
        logger.info("=== ALL TESTS PASSED ===")
        return {"status": "success", "message": "All tests passed", "address": result.address}
        
    except Exception as e:
        logger.error(f"=== TEST FAILED: {type(e).__name__}: {e} ===", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Test failed: {e}")
