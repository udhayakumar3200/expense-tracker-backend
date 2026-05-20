# Credit Card Transaction Logic — Design Spec

**Date:** 2026-05-19  
**Status:** Approved

---

## Overview

Extend the existing transaction service to correctly handle credit card accounts. Credit cards differ from normal accounts in that spending increases a debt (outstanding balance) rather than reducing available funds, and repayment is a bank-to-credit-card transfer that reduces that debt.

No new tables, no new routes, no architecture changes. This is a service-layer update.

---

## Scope

- Update `_apply_balance` in `transaction_service.py` to dispatch on account type
- Populate `credit_card_service.py` with CC-specific balance mutation and validation helpers
- Update `AccountCreate` schema to require `credit_limit` for credit card accounts
- Update `AccountResponse` schema to expose `credit_limit`, `outstanding_balance`, `available_credit`
- Update `account_service.create_account` to initialise CC fields on creation

**Out of scope:** New routes, model changes, migrations, auth, categories.

---

## Business Rules

### 1. Credit Card Expense
- Transaction type: `expense`, `from_account_id` = credit card account
- Increase `outstanding_balance` by amount
- Do not touch `current_balance`
- Blocked if amount exceeds available credit (`credit_limit - outstanding_balance`)

### 2. Credit Card Payment (Bank → CC)
- Transaction type: `transfer`, `from_account_id` = bank/cash/upi, `to_account_id` = credit card
- Reduce `from_acc.current_balance` by amount
- Reduce `cc_acc.outstanding_balance` by amount
- Blocked if amount exceeds `outstanding_balance` (no overpayment into negative)

### 3. Normal Bank Expense
- Transaction type: `expense`, `from_account_id` = non-credit-card
- Reduce `from_acc.current_balance` by amount (existing behaviour, unchanged)

### 4. Normal Income
- Transaction type: `income`, `to_account_id` = non-credit-card
- Increase `to_acc.current_balance` by amount (existing behaviour, unchanged)
- Income directly to a credit card account is blocked

### 5. Normal Transfer (Bank → Bank)
- Both accounts are non-credit-card
- Reduce `from_acc.current_balance`, increase `to_acc.current_balance` (existing behaviour, unchanged)

### 6. Transfer FROM a Credit Card
- Always blocked with a descriptive error

---

## Validation Rules

| Scenario | Error message |
|---|---|
| CC expense > available credit | `"Expense of {amount} exceeds available credit of {available}"` |
| CC payment > outstanding balance | `"Payment of {amount} exceeds outstanding balance of {outstanding}"` |
| Income to CC account | `"Cannot record income directly to a credit card account"` |
| Transfer from CC account | `"Cannot transfer from a credit card account"` |
| `credit_limit` missing on CC account creation | `"credit_limit is required for credit card accounts"` |
| `credit_limit` set on non-CC account | `"credit_limit is only valid for credit card accounts"` |

All errors propagate as `ValueError` and are caught by existing route handlers → HTTP 400.

---

## Revert Behaviour (Update / Delete)

`update_transaction` and `delete_transaction` revert the old transaction by calling `_apply_balance` with `-txn.amount`. The same dispatcher handles this correctly:

- For CC expense revert: `outstanding_balance -= amount` (amount is negative so balance decreases correctly)
- For CC payment revert: `from_acc.current_balance += amount`, `cc_acc.outstanding_balance += amount`

Validation (limit checks) is skipped when `amount <= 0` — reverts cannot violate credit limits.

---

## File Changes

### `app/schemas/account_schema.py`

**`AccountCreate`** — add `credit_limit: Decimal | None = None` with `model_validator`:
- Enforce `credit_limit` is present when `type == credit_card`
- Enforce `credit_limit` is absent when `type != credit_card`

**`AccountResponse`** — add:
- `credit_limit: Decimal | None`
- `outstanding_balance: Decimal | None`
- `available_credit: Decimal | None` — Pydantic `@computed_field` = `credit_limit - outstanding_balance` (None if either is None)

### `app/services/account_service.py`

`create_account` receives `credit_limit: Decimal | None = None`. When `account_type == credit_card`:
- Set `current_balance = Decimal("0")` — `initial_balance` is silently ignored; credit card accounts have no starting cash balance
- Set `credit_limit = credit_limit`
- Set `outstanding_balance = Decimal("0")` — always starts at zero (no pre-existing debt migration)

The `accounts.py` route passes `data.credit_limit` from the schema to the service.

### `app/services/credit_card_service.py`

Two synchronous helper functions (no DB calls — mutations are in-memory on ORM objects):

```python
def apply_cc_expense(account: Account, amount: Decimal) -> None:
    if amount > 0 and account.credit_limit is not None:
        available = account.credit_limit - (account.outstanding_balance or Decimal(0))
        if amount > available:
            raise ValueError(f"Expense of {amount} exceeds available credit of {available}")
    account.outstanding_balance = (account.outstanding_balance or Decimal(0)) + amount


def apply_cc_payment(from_acc: Account, cc_acc: Account, amount: Decimal) -> None:
    outstanding = cc_acc.outstanding_balance or Decimal(0)
    if amount > 0 and amount > outstanding:
        raise ValueError(f"Payment of {amount} exceeds outstanding balance of {outstanding}")
    from_acc.current_balance -= amount
    cc_acc.outstanding_balance = outstanding - amount
```

### `app/services/transaction_service.py`

`_apply_balance` is updated to:

```
expense:
  from_account is credit_card → cc_service.apply_cc_expense(from_acc, amount)
  from_account is normal      → from_acc.current_balance -= amount

income:
  to_account is credit_card   → ValueError (blocked)
  to_account is normal        → to_acc.current_balance += amount

transfer:
  from_account is credit_card → ValueError (blocked)
  to_account is credit_card   → cc_service.apply_cc_payment(from_acc, to_acc, amount)
  both normal                 → from_acc.current_balance -= amount; to_acc.current_balance += amount
```

---

## Dashboard / Account Response

`AccountResponse` exposes for credit card accounts:
- `credit_limit` — the hard limit set at creation
- `outstanding_balance` — current debt owed
- `available_credit` — `credit_limit - outstanding_balance` (computed, not stored)

For normal accounts these fields are `null`.

---

## Edge Cases Covered

| Scenario | Handling |
|---|---|
| Partial CC payment | Allowed — any amount ≤ outstanding |
| Multiple credit cards | Each card's outstanding tracked independently |
| Normal account → normal account transfer | Unchanged existing logic |
| CC → any transfer | Blocked |
| Income → CC | Blocked |
| No credit limit set | Limit check skipped (nil guard in apply_cc_expense) |
| Update transaction (type/amount changes) | Revert old balance then apply new — both paths use same dispatcher |
| Delete transaction | Revert via negative amount — same dispatcher |

---

## Addendum 2026-05-20 — Boundary Validations

The initial spec covered CC-specific behaviour but left several general transaction invariants unguarded. This addendum closes those gaps.

### A1. Amount must be positive

- `TransactionCreate.amount`: rejected if `<= 0`. Pydantic `Field(gt=0)`.
- `TransactionUpdate.amount`: if explicitly set, must be `> 0`. Validator at the field level.

Service-layer revert paths continue to receive negative amounts internally — the schema check applies only to API input.

### A2. Invalid account combinations

`_apply_balance` enforces shape invariants for each transaction type:

| Type | `from_account_id` | `to_account_id` |
|---|---|---|
| `expense` | required | must be `None` |
| `income` | must be `None` | required |
| `transfer` | required | required |

Errors:
- `"Expense must not have a to_account_id"`
- `"Income must not have a from_account_id"`
- (existing) `"Expense requires from_account_id"`, `"Income requires to_account_id"`, `"Transfer requires both from_account_id and to_account_id"`

These checks always apply — stored data should never violate them, so revert paths are unaffected.

### A3. Same-account transfer blocked

`_apply_balance` transfer branch rejects `from_account_id == to_account_id` with `"Cannot transfer to the same account"`. Applies on positive amounts only (reverts of valid stored transactions cannot violate this).

### A4. Direct `current_balance` mutation on credit card accounts blocked

`update_account` rejects any update that sets `current_balance` when the target account `type == credit_card`. CC accounts track debt via `outstanding_balance`; the cash-balance concept does not apply.

Error: `"Cannot directly modify current_balance of a credit card account"`.

The `PATCH /update_account/{id}` route wraps the service call in `try/except ValueError → HTTPException(400)` to match the pattern used by the transactions route.

### Test coverage

| Scenario | Test file |
|---|---|
| Reject zero / negative amount on create | `tests/test_transaction_schema_validation.py` (new) |
| Reject zero / negative amount on update | `tests/test_transaction_schema_validation.py` (new) |
| Expense with `to_account_id` blocked | `tests/test_transaction_service_cc.py` (extend) |
| Income with `from_account_id` blocked | `tests/test_transaction_service_cc.py` (extend) |
| Transfer with same from/to blocked | `tests/test_transaction_service_cc.py` (extend) |
| CC `current_balance` direct update blocked | `tests/test_account_service_cc.py` (extend) |
| Non-CC `current_balance` update still works | `tests/test_account_service_cc.py` (extend) |
