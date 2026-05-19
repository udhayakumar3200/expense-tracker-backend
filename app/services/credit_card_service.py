from decimal import Decimal
from app.models.account import Account


def apply_cc_expense(account: Account, amount: Decimal) -> None:
    """Increase CC outstanding balance. Validates credit limit on positive amounts only."""
    if amount > 0 and account.credit_limit is not None:
        available = account.credit_limit - (account.outstanding_balance or Decimal(0))
        if amount > available:
            raise ValueError(
                f"Expense of {amount} exceeds available credit of {available}"
            )
    account.outstanding_balance = (account.outstanding_balance or Decimal(0)) + amount


def apply_cc_payment(from_acc: Account, cc_acc: Account, amount: Decimal) -> None:
    """Bank → CC transfer: reduce bank balance and CC outstanding. Validates no overpayment."""
    outstanding = cc_acc.outstanding_balance or Decimal(0)
    if amount > 0 and amount > outstanding:
        raise ValueError(
            f"Payment of {amount} exceeds outstanding balance of {outstanding}"
        )
    from_acc.current_balance -= amount
    cc_acc.outstanding_balance = outstanding - amount
