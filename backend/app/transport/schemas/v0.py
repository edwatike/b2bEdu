"""Pydantic schemas for V0 API integration."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class V0PromptRequest(BaseModel):
    """Request schema for V0 API prompt."""
    prompt: str = Field(..., description="The prompt to send to V0")
    context: Optional[str] = Field(None, description="Additional context for the prompt")
    framework: Optional[str] = Field("react", description="Target framework (react, vue, html, etc.)")
    style: Optional[str] = Field("apple-hig", description="Style preference")
    components: Optional[List[str]] = Field(None, description="Specific components to generate")


class V0CodeFile(BaseModel):
    """Individual code file from V0 response."""
    path: str = Field(..., description="File path")
    content: str = Field(..., description="File content")
    language: Optional[str] = Field(None, description="Programming language")


class V0Response(BaseModel):
    """Response schema from V0 API."""
    success: bool = Field(..., description="Whether the generation was successful")
    files: Optional[List[V0CodeFile]] = Field(None, description="Generated code files")
    preview_url: Optional[str] = Field(None, description="Preview URL for the generated interface")
    error: Optional[str] = Field(None, description="Error message if generation failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    generation_id: Optional[str] = Field(None, description="Unique generation ID")


class V0GenerationStatus(BaseModel):
    """Status of a V0 generation."""
    generation_id: str
    status: str  # pending, generating, completed, failed
    progress: Optional[int] = None  # 0-100
    files_count: Optional[int] = None
    error: Optional[str] = None