import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.account import AccountType


class AccountCreate(BaseModel):
    name: str
    type: AccountType
    initial_balance: Decimal = Decimal("0")


class AccountResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: AccountType
    current_balance: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
