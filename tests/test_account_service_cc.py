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


# ── update_account: direct current_balance mutation on CC blocked ────────────


def _patched_get_account(account):
    return patch.object(account_service, "get_account", AsyncMock(return_value=account))


async def test_update_account_blocks_cc_current_balance_mutation():
    cc = Account(
        user_id=uuid.uuid4(),
        name="Visa",
        type=AccountType.credit_card,
        current_balance=Decimal("0"),
        credit_limit=Decimal("10000"),
        outstanding_balance=Decimal("2000"),
    )
    db = make_mock_db()
    with _patched_get_account(cc):
        with pytest.raises(ValueError, match="Cannot directly modify current_balance"):
            await account_service.update_account(
                db=db,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                current_balance=Decimal("5000"),
            )


async def test_update_account_allows_cc_name_change():
    cc = Account(
        user_id=uuid.uuid4(),
        name="Visa",
        type=AccountType.credit_card,
        current_balance=Decimal("0"),
        credit_limit=Decimal("10000"),
        outstanding_balance=Decimal("2000"),
    )
    db = make_mock_db()
    with _patched_get_account(cc):
        result = await account_service.update_account(
            db=db,
            user_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            name="Visa Platinum",
        )
    assert result is cc
    assert cc.name == "Visa Platinum"
    assert cc.current_balance == Decimal("0")


async def test_update_account_allows_bank_current_balance_change():
    bank = Account(
        user_id=uuid.uuid4(),
        name="HDFC",
        type=AccountType.bank,
        current_balance=Decimal("10000"),
    )
    db = make_mock_db()
    with _patched_get_account(bank):
        result = await account_service.update_account(
            db=db,
            user_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            current_balance=Decimal("12500"),
        )
    assert result is bank
    assert bank.current_balance == Decimal("12500")
