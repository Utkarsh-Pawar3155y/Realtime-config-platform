from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ServiceRegisterRequest(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    environment: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class ServiceRegisterResponse(BaseModel):
    id: int
    service_name: str
    environment: str
    description: Optional[str] = None
    auth_token: str
    status: str

    class Config:
        from_attributes = True


class ServiceDeleteResponse(BaseModel):
    message: str
    service_id: int
    service_name: str


class ConfigChangeRequest(BaseModel):
    new_value: Any
    reason: Optional[str] = None


class RollbackRequest(BaseModel):
    version_id: int
    reason: Optional[str] = None


class ApprovalRejectRequest(BaseModel):
    comment: Optional[str] = None