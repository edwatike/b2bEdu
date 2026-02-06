"""Pydantic schemas for domains queue."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.transport.schemas.common import BaseDTO


class DomainQueueEntryDTO(BaseDTO):
    """Domain queue entry DTO."""
    domain: str
    keyword: str
    url: str
    parsingRunId: Optional[str] = Field(None, alias="parsing_run_id")
    source: Optional[str] = Field(None, description="Source of the URL: google, yandex, or both")
    status: str
    createdAt: datetime = Field(alias="created_at")
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        # Use by_alias=True for JSON serialization to return camelCase
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    def model_dump(self, **kwargs):
        """Override model_dump to use by_alias=True by default for JSON serialization."""
        kwargs.setdefault("by_alias", True)
        kwargs.setdefault("mode", "json")
        return super().model_dump(**kwargs)


class DomainsQueueResponseDTO(BaseModel):
    """Response DTO for domains queue."""
    entries: List[DomainQueueEntryDTO]
    total: int
    limit: int
    offset: int


class PendingDomainDTO(BaseModel):
    """Pending domain DTO (not in blacklist and not a supplier)."""
    domain: str
    occurrences: int
    last_seen_at: Optional[datetime] = None


class PendingDomainsResponseDTO(BaseModel):
    """Response DTO for pending domains list."""
    entries: List[PendingDomainDTO]
    total: int
    limit: int
    offset: int
