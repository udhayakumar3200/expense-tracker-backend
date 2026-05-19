from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas.account_schema import AccountCreate, AccountResponse
from app.models.account import AccountType
import uuid
from datetime import datetime, timezone


def test_account_create_cc_requires_credit_limit():
    with pytest.raises(ValidationError, match="credit_limit is required"):
        AccountCreate(name="My Visa", type=AccountType.credit_card)


def test_account_create_cc_with_credit_limit_is_valid():
    schema = AccountCreate(
        name="My Visa",
        type=AccountType.credit_card,
        credit_limit=Decimal("50000"),
    )
    assert schema.credit_limit == Decimal("50000")


def test_account_create_bank_rejects_credit_limit():
    with pytest.raises(ValidationError, match="credit_limit is only valid"):
        AccountCreate(name="HDFC", type=AccountType.bank, credit_limit=Decimal("10000"))


def test_account_create_bank_without_credit_limit_is_valid():
    schema = AccountCreate(name="HDFC", type=AccountType.bank)
    assert schema.credit_limit is None


def _make_base_response_data(account_type=AccountType.bank):
    return dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Test",
        type=account_type,
        current_balance=Decimal("1000"),
        credit_limit=None,
        outstanding_balance=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_account_response_available_credit_computed():
    data = _make_base_response_data(AccountType.credit_card)
    data["credit_limit"] = Decimal("10000")
    data["outstanding_balance"] = Decimal("3000")
    response = AccountResponse(**data)
    assert response.available_credit == Decimal("7000")


def test_account_response_available_credit_none_for_normal_account():
    data = _make_base_response_data(AccountType.bank)
    response = AccountResponse(**data)
    assert response.available_credit is None


def test_account_response_available_credit_none_when_no_limit():
    data = _make_base_response_data(AccountType.credit_card)
    data["outstanding_balance"] = Decimal("3000")
    response = AccountResponse(**data)
    assert response.available_credit is None
