"""Pydantic schemas for blacklist."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.transport.schemas.common import BaseDTO


class BlacklistEntryDTO(BaseDTO):
    """Blacklist entry DTO."""
    domain: str
    reason: Optional[str] = None
    addedBy: Optional[str] = Field(None, alias="added_by")
    addedAt: Optional[str] = Field(None, alias="added_at")  # Строка вместо datetime для совместимости с Frontend
    parsingRunId: Optional[str] = Field(None, alias="parsing_run_id")
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class AddToBlacklistRequestDTO(BaseModel):
    """Request DTO for adding to blacklist."""
    domain: str
    reason: Optional[str] = None
    addedBy: Optional[str] = None
    parsingRunId: Optional[str] = None
    
    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate and normalize domain format to root domain."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Domain cannot be empty")
        if len(v) > 255:
            raise ValueError("Domain is too long (max 255 characters)")
        # Basic domain validation (can be enhanced)
        domain = v.strip().lower()
        if '.' not in domain:
            raise ValueError("Invalid domain format")
        # Remove protocol if present
        domain = domain.replace('http://', '').replace('https://', '').replace('www.', '')
        # Remove path if present (take only domain part)
        domain = domain.split('/')[0]
        # Extract root domain (last 2 parts)
        parts = domain.split('.')
        if len(parts) > 2:
            # Take last 2 parts (example.com from subdomain.example.com)
            domain = '.'.join(parts[-2:])
        if len(domain) < 3:
            raise ValueError("Domain is too short")
        return domain


class BlacklistResponseDTO(BaseModel):
    """Response DTO for blacklist."""
    entries: List[BlacklistEntryDTO]
    total: int
    limit: int
    offset: int

