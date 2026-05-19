from decimal import Decimal
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from app.models.account import AccountType
from app.models.transaction import TransactionType
from app.services import transaction_service


class MockAccount:
    def __init__(self, account_type, balance=Decimal("0"), credit_limit=None, outstanding=Decimal("0")):
        self.type = account_type
        self.current_balance = balance
        self.credit_limit = credit_limit
        self.outstanding_balance = outstanding


def _mock_db():
    return AsyncMock()


def _uid():
    return uuid.uuid4()


# ── CC Expense ──────────────────────────────────────────────────────────────

async def test_cc_expense_increases_outstanding():
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("10000"), outstanding=Decimal("2000"))
    db = _mock_db()
    with patch.object(transaction_service, "_get_owned_account", AsyncMock(return_value=cc)):
        await transaction_service._apply_balance(
            db=db, user_id=_uid(),
            txn_type=TransactionType.expense, amount=Decimal("500"),
            from_account_id=_uid(), to_account_id=None,
        )
    assert cc.outstanding_balance == Decimal("2500")
    assert cc.current_balance == Decimal("0")


async def test_cc_expense_over_limit_raises():
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("1000"), outstanding=Decimal("900"))
    db = _mock_db()
    with patch.object(transaction_service, "_get_owned_account", AsyncMock(return_value=cc)):
        with pytest.raises(ValueError, match="exceeds available credit"):
            await transaction_service._apply_balance(
                db=db, user_id=_uid(),
                txn_type=TransactionType.expense, amount=Decimal("200"),
                from_account_id=_uid(), to_account_id=None,
            )


# ── Normal Expense ───────────────────────────────────────────────────────────

async def test_bank_expense_reduces_current_balance():
    bank = MockAccount(AccountType.bank, balance=Decimal("10000"))
    db = _mock_db()
    with patch.object(transaction_service, "_get_owned_account", AsyncMock(return_value=bank)):
        await transaction_service._apply_balance(
            db=db, user_id=_uid(),
            txn_type=TransactionType.expense, amount=Decimal("1000"),
            from_account_id=_uid(), to_account_id=None,
        )
    assert bank.current_balance == Decimal("9000")


# ── Income ───────────────────────────────────────────────────────────────────

async def test_income_to_bank_increases_balance():
    bank = MockAccount(AccountType.bank, balance=Decimal("5000"))
    db = _mock_db()
    with patch.object(transaction_service, "_get_owned_account", AsyncMock(return_value=bank)):
        await transaction_service._apply_balance(
            db=db, user_id=_uid(),
            txn_type=TransactionType.income, amount=Decimal("2000"),
            from_account_id=None, to_account_id=_uid(),
        )
    assert bank.current_balance == Decimal("7000")


async def test_income_to_cc_is_blocked():
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("10000"), outstanding=Decimal("0"))
    db = _mock_db()
    with patch.object(transaction_service, "_get_owned_account", AsyncMock(return_value=cc)):
        with pytest.raises(ValueError, match="Cannot record income directly to a credit card account"):
            await transaction_service._apply_balance(
                db=db, user_id=_uid(),
                txn_type=TransactionType.income, amount=Decimal("1000"),
                from_account_id=None, to_account_id=_uid(),
            )


# ── Transfer: CC as source (blocked) ─────────────────────────────────────────

async def test_transfer_from_cc_is_blocked():
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("10000"), outstanding=Decimal("500"))
    bank = MockAccount(AccountType.bank, balance=Decimal("0"))
    db = _mock_db()

    async def get_account(db, user_id, account_id):
        return cc if account_id == from_id else bank

    from_id = _uid()
    with patch.object(transaction_service, "_get_owned_account", side_effect=get_account):
        with pytest.raises(ValueError, match="Cannot transfer from a credit card account"):
            await transaction_service._apply_balance(
                db=db, user_id=_uid(),
                txn_type=TransactionType.transfer, amount=Decimal("500"),
                from_account_id=from_id, to_account_id=_uid(),
            )


# ── Transfer: bank → CC (credit card payment) ────────────────────────────────

async def test_transfer_bank_to_cc_reduces_outstanding():
    bank = MockAccount(AccountType.bank, balance=Decimal("50000"))
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("10000"), outstanding=Decimal("8000"))
    db = _mock_db()

    call_count = {"n": 0}

    async def get_account(db, user_id, account_id):
        call_count["n"] += 1
        return bank if call_count["n"] == 1 else cc

    with patch.object(transaction_service, "_get_owned_account", side_effect=get_account):
        await transaction_service._apply_balance(
            db=db, user_id=_uid(),
            txn_type=TransactionType.transfer, amount=Decimal("5000"),
            from_account_id=_uid(), to_account_id=_uid(),
        )

    assert bank.current_balance == Decimal("45000")
    assert cc.outstanding_balance == Decimal("3000")


async def test_transfer_bank_to_cc_overpayment_blocked():
    bank = MockAccount(AccountType.bank, balance=Decimal("50000"))
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("10000"), outstanding=Decimal("3000"))
    db = _mock_db()

    call_count = {"n": 0}

    async def get_account(db, user_id, account_id):
        call_count["n"] += 1
        return bank if call_count["n"] == 1 else cc

    with patch.object(transaction_service, "_get_owned_account", side_effect=get_account):
        with pytest.raises(ValueError, match="exceeds outstanding balance"):
            await transaction_service._apply_balance(
                db=db, user_id=_uid(),
                txn_type=TransactionType.transfer, amount=Decimal("3001"),
                from_account_id=_uid(), to_account_id=_uid(),
            )


# ── Transfer: bank → bank ─────────────────────────────────────────────────────

async def test_transfer_bank_to_bank_unchanged():
    src = MockAccount(AccountType.bank, balance=Decimal("10000"))
    dst = MockAccount(AccountType.bank, balance=Decimal("2000"))
    db = _mock_db()

    call_count = {"n": 0}

    async def get_account(db, user_id, account_id):
        call_count["n"] += 1
        return src if call_count["n"] == 1 else dst

    with patch.object(transaction_service, "_get_owned_account", side_effect=get_account):
        await transaction_service._apply_balance(
            db=db, user_id=_uid(),
            txn_type=TransactionType.transfer, amount=Decimal("3000"),
            from_account_id=_uid(), to_account_id=_uid(),
        )

    assert src.current_balance == Decimal("7000")
    assert dst.current_balance == Decimal("5000")


# ── Revert behaviour (negative amounts) ──────────────────────────────────────

async def test_cc_expense_revert_reduces_outstanding():
    """Simulates delete_transaction reverting a CC expense."""
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("10000"), outstanding=Decimal("500"))
    db = _mock_db()
    with patch.object(transaction_service, "_get_owned_account", AsyncMock(return_value=cc)):
        await transaction_service._apply_balance(
            db=db, user_id=_uid(),
            txn_type=TransactionType.expense, amount=Decimal("-500"),
            from_account_id=_uid(), to_account_id=None,
        )
    assert cc.outstanding_balance == Decimal("0")


async def test_cc_payment_revert_restores_both_balances():
    """Simulates delete_transaction reverting a CC payment."""
    bank = MockAccount(AccountType.bank, balance=Decimal("45000"))
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("10000"), outstanding=Decimal("3000"))
    db = _mock_db()

    call_count = {"n": 0}

    async def get_account(db, user_id, account_id):
        call_count["n"] += 1
        return bank if call_count["n"] == 1 else cc

    with patch.object(transaction_service, "_get_owned_account", side_effect=get_account):
        await transaction_service._apply_balance(
            db=db, user_id=_uid(),
            txn_type=TransactionType.transfer, amount=Decimal("-5000"),
            from_account_id=_uid(), to_account_id=_uid(),
        )

    assert bank.current_balance == Decimal("50000")
    assert cc.outstanding_balance == Decimal("8000")


async def test_cc_expense_revert_does_not_validate_limit():
    """Revert must never fail due to limit checks even if it pushes below zero."""
    cc = MockAccount(AccountType.credit_card, credit_limit=Decimal("1000"), outstanding=Decimal("0"))
    db = _mock_db()
    # Negative amount on a CC expense: no ValueError should be raised
    with patch.object(transaction_service, "_get_owned_account", AsyncMock(return_value=cc)):
        await transaction_service._apply_balance(
            db=db, user_id=_uid(),
            txn_type=TransactionType.expense, amount=Decimal("-500"),
            from_account_id=_uid(), to_account_id=None,
        )
    assert cc.outstanding_balance == Decimal("-500")
