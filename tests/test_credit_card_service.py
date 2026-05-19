from decimal import Decimal
import pytest
from app.models.account import AccountType
from app.services import credit_card_service


class MockCCAccount:
    type = AccountType.credit_card

    def __init__(self, credit_limit, outstanding_balance):
        self.credit_limit = credit_limit
        self.outstanding_balance = outstanding_balance
        self.current_balance = Decimal("0")


def test_apply_cc_expense_increases_outstanding():
    acc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("2000"))
    credit_card_service.apply_cc_expense(acc, Decimal("500"))
    assert acc.outstanding_balance == Decimal("2500")


def test_apply_cc_expense_does_not_touch_current_balance():
    acc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("0"))
    credit_card_service.apply_cc_expense(acc, Decimal("300"))
    assert acc.current_balance == Decimal("0")


def test_apply_cc_expense_at_exact_limit_is_allowed():
    acc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("9500"))
    credit_card_service.apply_cc_expense(acc, Decimal("500"))
    assert acc.outstanding_balance == Decimal("10000")


def test_apply_cc_expense_exceeding_limit_raises():
    acc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("9500"))
    with pytest.raises(ValueError, match="exceeds available credit"):
        credit_card_service.apply_cc_expense(acc, Decimal("501"))


def test_apply_cc_expense_no_credit_limit_skips_check():
    acc = MockCCAccount(credit_limit=None, outstanding_balance=Decimal("0"))
    credit_card_service.apply_cc_expense(acc, Decimal("99999"))
    assert acc.outstanding_balance == Decimal("99999")


def test_apply_cc_expense_revert_negative_amount_skips_validation():
    # revert path: amount is negative, should not raise even if it looks like overdraft
    acc = MockCCAccount(credit_limit=Decimal("1000"), outstanding_balance=Decimal("500"))
    credit_card_service.apply_cc_expense(acc, Decimal("-500"))
    assert acc.outstanding_balance == Decimal("0")


class MockBankAccount:
    type = AccountType.bank

    def __init__(self, balance):
        self.current_balance = balance


def test_apply_cc_payment_reduces_bank_balance():
    bank = MockBankAccount(balance=Decimal("50000"))
    cc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("8000"))
    credit_card_service.apply_cc_payment(bank, cc, Decimal("5000"))
    assert bank.current_balance == Decimal("45000")


def test_apply_cc_payment_reduces_outstanding():
    bank = MockBankAccount(balance=Decimal("50000"))
    cc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("8000"))
    credit_card_service.apply_cc_payment(bank, cc, Decimal("5000"))
    assert cc.outstanding_balance == Decimal("3000")


def test_apply_cc_payment_full_payoff_allowed():
    bank = MockBankAccount(balance=Decimal("50000"))
    cc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("8000"))
    credit_card_service.apply_cc_payment(bank, cc, Decimal("8000"))
    assert cc.outstanding_balance == Decimal("0")


def test_apply_cc_payment_exceeding_outstanding_raises():
    bank = MockBankAccount(balance=Decimal("50000"))
    cc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("3000"))
    with pytest.raises(ValueError, match="exceeds outstanding balance"):
        credit_card_service.apply_cc_payment(bank, cc, Decimal("3001"))


def test_apply_cc_payment_revert_restores_balances():
    # revert path: negative amount, no validation
    bank = MockBankAccount(balance=Decimal("45000"))
    cc = MockCCAccount(credit_limit=Decimal("10000"), outstanding_balance=Decimal("3000"))
    credit_card_service.apply_cc_payment(bank, cc, Decimal("-5000"))
    assert bank.current_balance == Decimal("50000")
    assert cc.outstanding_balance == Decimal("8000")
