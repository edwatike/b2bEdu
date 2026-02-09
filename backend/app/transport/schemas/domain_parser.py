"""Schemas for domain parser API."""
from typing import List, Optional
from pydantic import BaseModel, Field


class DomainParserRequestDTO(BaseModel):
    """Request to parse domains for INN and email."""
    
    runId: str = Field(..., description="Parsing run ID")
    domains: List[str] = Field(..., description="List of domains to parse", min_length=1)
    force: Optional[bool] = Field(
        False,
        description="When true, do not skip globally moderated domains (domain_moderation) and attempt parsing anyway",
    )


class DomainParserResultDTO(BaseModel):
    """Result of parsing a single domain."""
    
    domain: str = Field(..., description="Domain name")
    inn: Optional[str] = Field(None, description="Extracted INN")
    emails: List[str] = Field(default_factory=list, description="Extracted emails")
    sourceUrls: List[str] = Field(default_factory=list, description="URLs where data was found")
    extractionLog: Optional[list] = Field(default_factory=list, description="Per-page extraction details")
    error: Optional[str] = Field(None, description="Error message if parsing failed")
    learned: Optional[bool] = Field(None, description="True if re-parse found data that was missing previously")
    previousInn: Optional[str] = Field(None, description="Previous INN before re-parse")
    previousEmails: Optional[List[str]] = Field(default_factory=list, description="Previous emails before re-parse")
    innSourceUrl: Optional[str] = Field(None, description="URL where INN was found")
    emailSourceUrl: Optional[str] = Field(None, description="URL where email was found")
    status: Optional[str] = Field(None, description="run_domains status snapshot")
    reason: Optional[str] = Field(None, description="run_domains reason snapshot")
    conflictInn: Optional[bool] = Field(None, description="True if INN conflicts with existing supplier")
    conflictSupplierId: Optional[int] = Field(None, description="Existing supplier ID on INN conflict")
    supplierCreated: Optional[bool] = Field(None, description="Supplier was created automatically")
    supplierUpdated: Optional[bool] = Field(None, description="Supplier was updated automatically")
    dataStatus: Optional[str] = Field(None, description="Supplier data status if created/updated")
    strategyUsed: Optional[str] = Field(None, description="Parsing strategy used (http_probe, api_sniff, playwright)")
    strategyTimeMs: Optional[int] = Field(None, description="Time taken by the strategy in milliseconds")


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
    currentDomain: Optional[str] = Field(None, description="Current domain being processed")
    currentSourceUrls: List[str] = Field(default_factory=list, description="Source URLs currently being checked")
    results: List[DomainParserResultDTO] = Field(default_factory=list, description="Parsing results")
