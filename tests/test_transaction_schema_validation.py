import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.transaction import TransactionType
from app.schemas.transaction_schema import TransactionCreate, TransactionUpdate


def _base_create_kwargs():
    return dict(
        type=TransactionType.expense,
        transaction_date=datetime.now(timezone.utc),
        from_account_id=uuid.uuid4(),
    )


def test_transaction_create_rejects_zero_amount():
    with pytest.raises(ValidationError, match="greater than 0"):
        TransactionCreate(amount=Decimal("0"), **_base_create_kwargs())


def test_transaction_create_rejects_negative_amount():
    with pytest.raises(ValidationError, match="greater than 0"):
        TransactionCreate(amount=Decimal("-100"), **_base_create_kwargs())


def test_transaction_create_accepts_positive_amount():
    txn = TransactionCreate(amount=Decimal("100"), **_base_create_kwargs())
    assert txn.amount == Decimal("100")


def test_transaction_update_rejects_zero_amount():
    with pytest.raises(ValidationError, match="greater than 0"):
        TransactionUpdate(amount=Decimal("0"))


def test_transaction_update_rejects_negative_amount():
    with pytest.raises(ValidationError, match="greater than 0"):
        TransactionUpdate(amount=Decimal("-50"))


def test_transaction_update_accepts_positive_amount():
    upd = TransactionUpdate(amount=Decimal("250"))
    assert upd.amount == Decimal("250")


def test_transaction_update_allows_amount_absent():
    upd = TransactionUpdate(description="updated note")
    assert upd.amount is None
