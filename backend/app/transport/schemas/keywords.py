"""Pydantic schemas for keywords."""
from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict, Field

from app.transport.schemas.common import BaseDTO


class KeywordDTO(BaseDTO):
    """Keyword DTO."""
    id: int
    keyword: str
    createdAt: datetime = Field(alias="created_at")
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class CreateKeywordRequestDTO(BaseModel):
    """Request DTO for creating keyword."""
    keyword: str


class KeywordsListResponseDTO(BaseModel):
    """Response DTO for keywords list."""
    keywords: List[KeywordDTO]

