"""Router for Checko API integration."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.adapters.db.session import get_db
from app.transport.schemas.checko import CheckoDataResponseDTO
from app.usecases import get_checko_data

router = APIRouter()


@router.get("/checko/{inn}", response_model=CheckoDataResponseDTO)
async def get_checko_data_endpoint(
    inn: str,
    force_refresh: bool = Query(default=False, description="Force refresh from Checko API even if cache exists"),
    db: AsyncSession = Depends(get_db)
):
    """Get Checko data for company by INN with caching.
    
    Args:
        inn: Company INN (10 or 12 digits)
        force_refresh: If True, force refresh from API even if cache exists
        db: Database session
        
    Returns:
        Checko data formatted for frontend
        
    Raises:
        HTTPException: If INN is invalid, API key is not configured, or API request fails
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        data = await get_checko_data.execute(
            db=db,
            inn=inn,
            force_refresh=force_refresh
        )
        return CheckoDataResponseDTO(**data)
    except ValueError as e:
        logger.warning(f"Invalid INN {inn}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Checko API configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get Checko data for INN {inn}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка получения данных из Checko: {str(e)}")









