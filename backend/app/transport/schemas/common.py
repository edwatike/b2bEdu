"""Common Pydantic schemas."""
from pydantic import BaseModel, ConfigDict


class BaseDTO(BaseModel):
    """Base DTO with common configuration."""
    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str

