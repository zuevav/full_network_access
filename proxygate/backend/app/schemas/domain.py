from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DomainCreate(BaseModel):
    domains: List[str] = Field(..., min_length=1)
    include_subdomains: bool = True


class DomainResponse(BaseModel):
    id: int
    domain: str
    include_subdomains: bool
    is_active: bool
    added_at: datetime

    model_config = {"from_attributes": True}


class DomainTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=10)
    domains: List[str] = Field(..., min_length=1)


class DomainTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=10)
    domains: Optional[List[str]] = None
    is_active: Optional[bool] = None


class DomainTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    icon: Optional[str]
    domains: List[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplyTemplateRequest(BaseModel):
    template_id: int
