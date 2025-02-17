from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class BaseSchema(BaseModel):
    """기본 스키마"""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True
    )

class TimestampSchema(BaseSchema):
    """타임스탬프 스키마"""
    created_at: datetime
    updated_at: datetime

class ResponseSchema(BaseSchema):
    """기본 응답 스키마"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
