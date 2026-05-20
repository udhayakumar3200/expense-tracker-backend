import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.transaction import TransactionType


class TransactionCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    type: TransactionType
    transaction_date: datetime
    from_account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    description: str | None = None


class TransactionUpdate(BaseModel):
    amount: Decimal | None = None
    type: TransactionType | None = None
    transaction_date: datetime | None = None
    from_account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    description: str | None = None

    @field_validator("amount")
    @classmethod
    def _amount_must_be_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("amount must be greater than 0")
        return v


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
