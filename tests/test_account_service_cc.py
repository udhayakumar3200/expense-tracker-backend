from decimal import Decimal
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.account import Account, AccountType
from app.services import account_service


def make_mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


async def test_create_cc_account_sets_outstanding_zero():
    db = make_mock_db()
    captured = {}

    def capture_add(obj):
        captured["account"] = obj

    db.add = capture_add

    user_id = uuid.uuid4()
    await account_service.create_account(
        db=db,
        user_id=user_id,
        name="Visa",
        account_type=AccountType.credit_card,
        credit_limit=Decimal("50000"),
    )
    acc = captured["account"]
    assert acc.outstanding_balance == Decimal("0")


async def test_create_cc_account_sets_credit_limit():
    db = make_mock_db()
    captured = {}

    def capture_add(obj):
        captured["account"] = obj

    db.add = capture_add

    await account_service.create_account(
        db=db,
        user_id=uuid.uuid4(),
        name="Visa",
        account_type=AccountType.credit_card,
        credit_limit=Decimal("50000"),
    )
    assert captured["account"].credit_limit == Decimal("50000")


async def test_create_cc_account_ignores_initial_balance():
    db = make_mock_db()
    captured = {}

    def capture_add(obj):
        captured["account"] = obj

    db.add = capture_add

    await account_service.create_account(
        db=db,
        user_id=uuid.uuid4(),
        name="Visa",
        account_type=AccountType.credit_card,
        initial_balance=Decimal("99999"),
        credit_limit=Decimal("50000"),
    )
    assert captured["account"].current_balance == Decimal("0")


async def test_create_bank_account_does_not_set_cc_fields():
    db = make_mock_db()
    captured = {}

    def capture_add(obj):
        captured["account"] = obj

    db.add = capture_add

    await account_service.create_account(
        db=db,
        user_id=uuid.uuid4(),
        name="HDFC",
        account_type=AccountType.bank,
        initial_balance=Decimal("10000"),
    )
    acc = captured["account"]
    assert acc.credit_limit is None
    assert acc.outstanding_balance is None
    assert acc.current_balance == Decimal("10000")
