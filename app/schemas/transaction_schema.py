import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.transaction import TransactionType


class TransactionCreate(BaseModel):
    amount: Decimal
    type: TransactionType
    transaction_date: datetime
    from_account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    description: str | None = None


class TransactionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    amount: Decimal
    type: TransactionType
    transaction_date: datetime
    from_account_id: uuid.UUID | None
    to_account_id: uuid.UUID | None
    category_id: uuid.UUID | None
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
