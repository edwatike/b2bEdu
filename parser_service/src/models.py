"""Data models for Parser Service."""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class ParsedSupplier(BaseModel):
    """Model for parsed supplier data."""
    domain: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    inn: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    keywords: List[str] = []
    confidence: float = 0.0
    source: Optional[str] = None
    parsed_at: datetime = datetime.now()


class ParseRequest(BaseModel):
    """Request model for parsing."""
    keyword: str
    depth: int = 5
    source: Optional[str] = None  # "google", "yandex", or None for both


class ParseResponse(BaseModel):
    """Response model for parsing."""
    keyword: str
    suppliers: List[ParsedSupplier]
    total_found: int
    parsing_logs: Optional[Dict[str, Any]] = None  # Structured parsing logs with links found by each engine
