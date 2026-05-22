import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, computed_field, model_validator

from app.models.account import AccountType


class AccountCreate(BaseModel):
    name: str
    type: AccountType
    initial_balance: Decimal = Decimal("0")
    credit_limit: Decimal | None = None
    outstanding_balance: Decimal | None = None

    @model_validator(mode="after")
    def validate_credit_card_fields(self) -> "AccountCreate":
        if self.type == AccountType.credit_card and self.credit_limit is None:
            raise ValueError("credit_limit is required for credit card accounts")
        if self.type == AccountType.credit_card and self.credit_limit is not None and self.credit_limit <= 0:
            raise ValueError("credit_limit must be greater than zero")
        if self.type != AccountType.credit_card and self.credit_limit is not None:
            raise ValueError("credit_limit is only valid for credit card accounts")
        if self.type != AccountType.credit_card and self.outstanding_balance is not None:
            raise ValueError("outstanding_balance is only valid for credit card accounts")
        return self


class AccountUpdate(BaseModel):
    name: str | None = None
    current_balance: Decimal | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: AccountType
    current_balance: Decimal
    credit_limit: Decimal | None
    outstanding_balance: Decimal | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def available_credit(self) -> Decimal | None:
        if self.credit_limit is not None and self.outstanding_balance is not None:
            return self.credit_limit - self.outstanding_balance
        return None

    model_config = {"from_attributes": True}
