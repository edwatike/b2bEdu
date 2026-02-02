"""Pydantic schemas for parsing."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

from app.transport.schemas.common import BaseDTO


class StartParsingRequestDTO(BaseModel):
    """Request DTO for starting parsing."""
    keyword: str
    depth: int = Field(default=50, description="Number of search result pages to parse (depth)")
    source: str = Field(default="google", description="Source for parsing: 'google', 'yandex', or 'both'")


class StartParsingResponseDTO(BaseModel):
    """Response DTO for parsing start."""
    runId: str  # Use camelCase directly (no alias needed for response)
    keyword: str
    status: str
    
    model_config = ConfigDict(
        populate_by_name=True,
    )


class ParsingStatusResponseDTO(BaseModel):
    """Response DTO for parsing status."""
    runId: str = Field(alias="run_id")
    keyword: str
    status: str
    startedAt: Optional[datetime] = Field(None, alias="started_at")
    finishedAt: Optional[datetime] = Field(None, alias="finished_at")
    error: Optional[str] = Field(None, alias="error_message")
    resultsCount: Optional[int] = None  # Not in DB, can be calculated from parsing_hits


class ParsingRunDTO(BaseDTO):
    """Parsing run DTO."""
    runId: str = Field(alias="run_id")
    keyword: str  # Will be extracted from request.title or raw_keys_json
    status: str
    startedAt: Optional[str] = Field(None, alias="started_at")
    finishedAt: Optional[str] = Field(None, alias="finished_at")
    error: Optional[str] = Field(None, alias="error_message")
    resultsCount: Optional[int] = None  # Not in DB, can be calculated from parsing_hits
    createdAt: str = Field(alias="created_at")
    depth: Optional[int] = None  # Depth of parsing (number of pages)
    source: Optional[str] = Field(None, description="Source for parsing: 'google', 'yandex', or 'both'")
    processLog: Optional[Dict[str, Any]] = Field(None, alias="process_log", description="Detailed parsing process information")
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        # Используем by_alias=True для сериализации в JSON
        json_schema_extra={
            "example": {
                "runId": "123e4567-e89b-12d3-a456-426614174000",
                "keyword": "test keyword",
                "status": "running",
                "startedAt": "2025-12-26T14:00:00Z",
                "finishedAt": None,
                "error": None,
                "resultsCount": None,
                "createdAt": "2025-12-26T14:00:00Z"
            }
        }
    )
    
    def model_dump(self, **kwargs):
        """Override model_dump to use by_alias=True by default for JSON serialization."""
        kwargs.setdefault("by_alias", True)
        kwargs.setdefault("mode", "json")
        return super().model_dump(**kwargs)


class ParsingRunsListResponseDTO(BaseModel):
    """Response DTO for parsing runs list."""
    runs: List[ParsingRunDTO]
    total: int
    limit: int
    offset: int

