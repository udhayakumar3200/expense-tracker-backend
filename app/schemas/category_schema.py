import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.category import CategoryType


class CategoryCreate(BaseModel):
    name: str
    type: CategoryType


class CategoryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: CategoryType
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
