"""Router for keywords."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.db.session import get_db
from app.transport.routers.auth import can_access_moderator_zone, get_current_user
from app.transport.schemas.keywords import (
    KeywordDTO,
    CreateKeywordRequestDTO,
    KeywordsListResponseDTO,
)
from app.usecases import (
    create_keyword,
    list_keywords,
    delete_keyword,
)

router = APIRouter()


def _require_moderator(current_user: dict):
    if not can_access_moderator_zone(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("", response_model=KeywordsListResponseDTO)
async def list_keywords_endpoint(
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all keywords."""
    _require_moderator(current_user)
    keywords = await list_keywords.execute(db=db)
    return KeywordsListResponseDTO(
        keywords=[KeywordDTO.model_validate(k) for k in keywords]
    )


@router.post("", response_model=KeywordDTO, status_code=201)
async def create_keyword_endpoint(
    request: CreateKeywordRequestDTO,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new keyword."""
    _require_moderator(current_user)
    keyword = await create_keyword.execute(db=db, keyword=request.keyword)
    await db.commit()
    return KeywordDTO.model_validate(keyword)


@router.delete("/{keyword_id}", status_code=204)
async def delete_keyword_endpoint(
    keyword_id: int,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete keyword."""
    _require_moderator(current_user)
    success = await delete_keyword.execute(db=db, keyword_id=keyword_id)
    if not success:
        raise HTTPException(status_code=404, detail="Keyword not found")
    
    await db.commit()

