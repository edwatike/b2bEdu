"""Absolutely minimal endpoint to test MissingGreenlet issue."""
import logging
from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)

@router.put("/suppliers/{supplier_id}/test-absolute-minimal")
async def absolute_minimal_test(supplier_id: int):
    """Absolutely minimal test - no database, no dependencies."""
    logger.info(f"=== ABSOLUTE MINIMAL TEST: supplier_id={supplier_id} ===")
    
    try:
        # Just return a success response
        return {
            "status": "success",
            "message": f"Minimal test completed for supplier {supplier_id}",
            "timestamp": str(__import__('datetime').datetime.now())
        }
        
    except Exception as e:
        logger.error(f"=== ABSOLUTE MINIMAL TEST ERROR: {type(e).__name__}: {e} ===", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {e}")
