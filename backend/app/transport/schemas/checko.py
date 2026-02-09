"""Pydantic schemas for Checko API."""
from typing import Optional
from pydantic import BaseModel


class CheckoDataResponseDTO(BaseModel):
    """Response DTO for Checko data."""
    name: Optional[str] = None
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    okpo: Optional[str] = None
    companyStatus: Optional[str] = None
    registrationDate: Optional[str] = None
    legalAddress: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    vk: Optional[str] = None
    telegram: Optional[str] = None
    authorizedCapital: Optional[int] = None
    revenue: Optional[int] = None
    profit: Optional[int] = None
    financeYear: Optional[int] = None
    legalCasesCount: Optional[int] = None
    legalCasesSum: Optional[int] = None
    legalCasesAsPlaintiff: Optional[int] = None
    legalCasesAsDefendant: Optional[int] = None
    checkoData: str  # Full JSON data as string









