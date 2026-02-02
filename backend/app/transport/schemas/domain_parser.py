"""Schemas for domain parser API."""
from typing import List, Optional
from pydantic import BaseModel, Field


class DomainParserRequestDTO(BaseModel):
    """Request to parse domains for INN and email."""
    
    runId: str = Field(..., description="Parsing run ID")
    domains: List[str] = Field(..., description="List of domains to parse", min_length=1)


class DomainParserResultDTO(BaseModel):
    """Result of parsing a single domain."""
    
    domain: str = Field(..., description="Domain name")
    inn: Optional[str] = Field(None, description="Extracted INN")
    emails: List[str] = Field(default_factory=list, description="Extracted emails")
    sourceUrls: List[str] = Field(default_factory=list, description="URLs where data was found")
    error: Optional[str] = Field(None, description="Error message if parsing failed")


class DomainParserBatchResponseDTO(BaseModel):
    """Response for batch domain parsing."""
    
    runId: str = Field(..., description="Parsing run ID")
    parserRunId: str = Field(..., description="Unique parser run ID")


class DomainParserStatusResponseDTO(BaseModel):
    """Status response for domain parser."""
    
    runId: str = Field(..., description="Parsing run ID")
    parserRunId: str = Field(..., description="Parser run ID")
    status: str = Field(..., description="Status: running, completed, failed")
    processed: int = Field(0, description="Number of domains processed")
    total: int = Field(0, description="Total domains to process")
    results: List[DomainParserResultDTO] = Field(default_factory=list, description="Parsing results")
