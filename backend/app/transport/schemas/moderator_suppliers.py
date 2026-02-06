"""Pydantic schemas for moderator suppliers."""
from datetime import datetime, date
from typing import Optional, List, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, AliasChoices

from app.transport.schemas.common import BaseDTO


class SupplierType(str):
    """Supplier type enum."""
    SUPPLIER = "supplier"
    RESELLER = "reseller"


class ModeratorSupplierDTO(BaseDTO):
    """Supplier DTO."""
    id: int
    name: str
    inn: Optional[str] = None
    email: Optional[str] = None
    domain: Optional[str] = None
    address: Optional[str] = None
    type: str = "supplier"
    allowDuplicateInn: bool = Field(False, alias="allow_duplicate_inn", serialization_alias="allowDuplicateInn")
    dataStatus: str = Field("complete", alias="data_status", serialization_alias="dataStatus")
    domains: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    
    # Checko fields
    ogrn: Optional[str] = None
    kpp: Optional[str] = None
    okpo: Optional[str] = None
    companyStatus: Optional[str] = Field(None, alias="company_status", serialization_alias="companyStatus")
    registrationDate: Optional[str] = Field(None, alias="registration_date", serialization_alias="registrationDate")
    legalAddress: Optional[str] = Field(None, alias="legal_address", serialization_alias="legalAddress")
    phone: Optional[str] = None
    website: Optional[str] = None
    vk: Optional[str] = None
    telegram: Optional[str] = None
    authorizedCapital: Optional[int] = Field(None, alias="authorized_capital", serialization_alias="authorizedCapital")
    revenue: Optional[int] = None
    profit: Optional[int] = None
    financeYear: Optional[int] = Field(None, alias="finance_year", serialization_alias="financeYear")
    legalCasesCount: Optional[int] = Field(None, alias="legal_cases_count", serialization_alias="legalCasesCount")
    legalCasesSum: Optional[int] = Field(None, alias="legal_cases_sum", serialization_alias="legalCasesSum")
    legalCasesAsPlaintiff: Optional[int] = Field(None, alias="legal_cases_as_plaintiff", serialization_alias="legalCasesAsPlaintiff")
    legalCasesAsDefendant: Optional[int] = Field(None, alias="legal_cases_as_defendant", serialization_alias="legalCasesAsDefendant")
    checkoData: Optional[str] = Field(None, alias="checko_data", serialization_alias="checkoData")
    
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        # Use serialization_alias for JSON output
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Supplier Name",
                "registrationDate": "2003-11-04",
                "legalAddress": "г. Санкт-Петербург",
                "financeYear": 2021,
                "legalCasesCount": 1657
            }
        }
    )
    
    @field_validator('registrationDate', mode='before')
    @classmethod
    def convert_registration_date(cls, v):
        """Convert date object to string."""
        if isinstance(v, date):
            return v.isoformat()
        return v

    @field_validator("domains", mode="before")
    @classmethod
    def normalize_domains(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, str):
                    out.append(item)
                else:
                    domain = getattr(item, "domain", None)
                    if domain:
                        out.append(str(domain))
            return out
        return v

    @field_validator("emails", mode="before")
    @classmethod
    def normalize_emails(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, str):
                    out.append(item)
                else:
                    email = getattr(item, "email", None)
                    if email:
                        out.append(str(email))
            return out
        return v


class CreateModeratorSupplierRequestDTO(BaseModel):
    """Request DTO for creating supplier."""
    name: str
    inn: Optional[str] = None
    email: Optional[str] = None
    domain: Optional[str] = None
    address: Optional[str] = None
    type: str = "supplier"
    allowDuplicateInn: Optional[bool] = None
    dataStatus: Optional[str] = None
    domains: Optional[List[str]] = None
    emails: Optional[List[str]] = None
    
    # Checko fields
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
    checkoData: Optional[str] = None
    
    model_config = ConfigDict(
        # Preserve empty strings and None values
        # Don't coerce empty strings to None
        str_strip_whitespace=False,
        # Allow extra fields to be passed through
        extra="allow"
    )


class UpdateModeratorSupplierRequestDTO(BaseModel):
    """Request DTO for updating supplier."""
    name: Optional[str] = None
    inn: Optional[str] = None
    email: Optional[str] = None
    domain: Optional[str] = None
    address: Optional[str] = None
    type: Optional[str] = None
    allowDuplicateInn: Optional[bool] = None
    dataStatus: Optional[str] = None
    domains: Optional[List[str]] = None
    emails: Optional[List[str]] = None
    
    # Checko fields
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
    checkoData: Optional[str] = None


class SupplierKeywordsResponseDTO(BaseModel):
    """Response DTO for supplier keywords."""
    keywords: List[dict]


class ModeratorSuppliersListResponseDTO(BaseModel):
    """Response DTO for suppliers list."""
    suppliers: List[ModeratorSupplierDTO]
    total: int
    limit: int
    offset: int
