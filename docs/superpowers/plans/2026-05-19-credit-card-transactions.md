# Credit Card Transaction Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the transaction service credit-card-aware so that CC expenses update outstanding balance, CC payments reduce it, and invalid operations are blocked with clear errors.

**Architecture:** `credit_card_service.py` owns CC-specific balance mutations and validations (pure synchronous functions, no DB calls). `_apply_balance` in `transaction_service.py` becomes a dispatcher that reads account types and routes to the right handler. Schemas are updated to expose CC fields.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Pydantic v2, pytest + pytest-asyncio

---

## File Map

| File | Action | What changes |
|---|---|---|
| `pyproject.toml` | Modify | Add `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| `app/services/credit_card_service.py` | Replace | `apply_cc_expense` and `apply_cc_payment` helpers |
| `app/schemas/account_schema.py` | Modify | `AccountCreate` + `model_validator`; `AccountResponse` + `computed_field` |
| `app/services/account_service.py` | Modify | `create_account` sets CC fields |
| `app/api/accounts.py` | Modify | Route passes `credit_limit` to service |
| `app/services/transaction_service.py` | Modify | `_apply_balance` becomes a typed dispatcher |
| `tests/test_credit_card_service.py` | Create | Unit tests for `credit_card_service` helpers |
| `tests/test_account_schema_cc.py` | Create | Pydantic validation tests for schema changes |
| `tests/test_transaction_service_cc.py` | Create | Unit tests for `_apply_balance` dispatcher (mocked accounts) |

---

## Task 1: Configure pytest for async tests

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pytest config to `pyproject.toml`**

Open `pyproject.toml` and append:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Verify pytest runs without errors**

```bash
cd /home/udhay/projects/personal/backend/expense-tracker-backend
python -m pytest --collect-only 2>&1 | tail -5
```

Expected: `0 errors` in the collection output (no tests collected yet is fine).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: configure pytest asyncio_mode=auto"
```

---

## Task 2: Implement `credit_card_service.py` (TDD)

**Files:**
- Replace: `app/services/credit_card_service.py`
- Create: `tests/test_credit_card_service.py`

### Step 2a — CC expense helper

- [ ] **Step 1: Write failing tests for `apply_cc_expense`**

Create `tests/test_credit_card_service.py`:

```python
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
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/test_credit_card_service.py -v 2>&1 | tail -15
```

Expected: `ImportError` or `AttributeError` — `apply_cc_expense` does not exist yet.

- [ ] **Step 3: Implement `apply_cc_expense` in `credit_card_service.py`**

Replace the contents of `app/services/credit_card_service.py`:

```python
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
```

- [ ] **Step 4: Run CC expense tests to verify they pass**

```bash
python -m pytest tests/test_credit_card_service.py::test_apply_cc_expense_increases_outstanding tests/test_credit_card_service.py::test_apply_cc_expense_does_not_touch_current_balance tests/test_credit_card_service.py::test_apply_cc_expense_at_exact_limit_is_allowed tests/test_credit_card_service.py::test_apply_cc_expense_exceeding_limit_raises tests/test_credit_card_service.py::test_apply_cc_expense_no_credit_limit_skips_check tests/test_credit_card_service.py::test_apply_cc_expense_revert_negative_amount_skips_validation -v 2>&1 | tail -15
```

Expected: 6 PASSED.

### Step 2b — CC payment helper

- [ ] **Step 5: Write failing tests for `apply_cc_payment`**

Append to `tests/test_credit_card_service.py`:

```python
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
```

- [ ] **Step 6: Run to verify new tests fail**

```bash
python -m pytest tests/test_credit_card_service.py -k "payment" -v 2>&1 | tail -10
```

Expected: `AttributeError` — `apply_cc_payment` does not exist yet.

- [ ] **Step 7: Add `apply_cc_payment` to `credit_card_service.py`**

Append to `app/services/credit_card_service.py`:

```python

def apply_cc_payment(from_acc: Account, cc_acc: Account, amount: Decimal) -> None:
    """Bank → CC transfer: reduce bank balance and CC outstanding. Validates no overpayment."""
    outstanding = cc_acc.outstanding_balance or Decimal(0)
    if amount > 0 and amount > outstanding:
        raise ValueError(
            f"Payment of {amount} exceeds outstanding balance of {outstanding}"
        )
    from_acc.current_balance -= amount
    cc_acc.outstanding_balance = outstanding - amount
```

- [ ] **Step 8: Run all CC service tests**

```bash
python -m pytest tests/test_credit_card_service.py -v 2>&1 | tail -20
```

Expected: 11 PASSED.

- [ ] **Step 9: Commit**

```bash
git add app/services/credit_card_service.py tests/test_credit_card_service.py
git commit -m "feat: implement credit card service helpers with validation"
```

---

## Task 3: Update `account_schema.py` (TDD)

**Files:**
- Modify: `app/schemas/account_schema.py`
- Create: `tests/test_account_schema_cc.py`

- [ ] **Step 1: Write failing tests for schema validation**

Create `tests/test_account_schema_cc.py`:

```python
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
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/test_account_schema_cc.py -v 2>&1 | tail -15
```

Expected: `ValidationError` or `TypeError` failures — `credit_limit` field and validator don't exist yet.

- [ ] **Step 3: Update `app/schemas/account_schema.py`**

Replace the entire file:

```python
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

    @model_validator(mode="after")
    def validate_credit_card_fields(self) -> "AccountCreate":
        if self.type == AccountType.credit_card and self.credit_limit is None:
            raise ValueError("credit_limit is required for credit card accounts")
        if self.type != AccountType.credit_card and self.credit_limit is not None:
            raise ValueError("credit_limit is only valid for credit card accounts")
        return self


class AccountUpdate(BaseModel):
    name: str | None = None
    type: AccountType | None = None
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
```

- [ ] **Step 4: Run schema tests**

```bash
python -m pytest tests/test_account_schema_cc.py -v 2>&1 | tail -15
```

Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add app/schemas/account_schema.py tests/test_account_schema_cc.py
git commit -m "feat: add credit_limit to AccountCreate and available_credit to AccountResponse"
```

---

## Task 4: Update `account_service.py` and `accounts.py` route (TDD)

**Files:**
- Modify: `app/services/account_service.py`
- Modify: `app/api/accounts.py`
- Create: `tests/test_account_service_cc.py`

- [ ] **Step 1: Write failing tests for `create_account`**

Create `tests/test_account_service_cc.py`:

```python
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
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/test_account_service_cc.py -v 2>&1 | tail -15
```

Expected: `TypeError` — `create_account` doesn't accept `credit_limit` yet.

- [ ] **Step 3: Update `app/services/account_service.py`**

Replace only the `create_account` function (lines 11–27):

```python
async def create_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    account_type: AccountType,
    initial_balance: Decimal = Decimal("0"),
    credit_limit: Decimal | None = None,
) -> Account:
    is_cc = account_type == AccountType.credit_card
    account = Account(
        user_id=user_id,
        name=name,
        type=account_type,
        current_balance=Decimal("0") if is_cc else initial_balance,
        credit_limit=credit_limit if is_cc else None,
        outstanding_balance=Decimal("0") if is_cc else None,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account
```

- [ ] **Step 4: Update `app/api/accounts.py` — pass `credit_limit` from schema to service**

In the `create_account` route (lines 19–26), update the service call:

```python
    account = await account_service.create_account(
        db=db,
        user_id=user_id,
        name=data.name,
        account_type=data.type,
        initial_balance=data.initial_balance,
        credit_limit=data.credit_limit,
    )
```

- [ ] **Step 5: Run account service tests**

```bash
python -m pytest tests/test_account_service_cc.py -v 2>&1 | tail -15
```

Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add app/services/account_service.py app/api/accounts.py tests/test_account_service_cc.py
git commit -m "feat: create_account initialises credit card fields on creation"
```

---

## Task 5: Update `_apply_balance` dispatcher in `transaction_service.py` (TDD)

**Files:**
- Modify: `app/services/transaction_service.py`
- Create: `tests/test_transaction_service_cc.py`

- [ ] **Step 1: Write failing tests for all dispatcher paths**

Create `tests/test_transaction_service_cc.py`:

```python
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
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/test_transaction_service_cc.py -v 2>&1 | tail -20
```

Expected: Most tests fail — CC paths don't exist in `_apply_balance` yet.

- [ ] **Step 3: Update `_apply_balance` in `app/services/transaction_service.py`**

Replace the `_apply_balance` function (lines 30–59) with:

```python
async def _apply_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
    txn_type: TransactionType,
    amount: Decimal,
    from_account_id: uuid.UUID | None,
    to_account_id: uuid.UUID | None,
) -> None:
    """Apply a signed amount to the relevant account balances.

    Pass a negative amount to revert a previously applied transaction.
    Validates account ownership for any account touched.
    """
    if txn_type == TransactionType.expense:
        if from_account_id is None:
            raise ValueError("Expense requires from_account_id")
        from_acc = await _get_owned_account(db, user_id, from_account_id)
        if from_acc.type == AccountType.credit_card:
            credit_card_service.apply_cc_expense(from_acc, amount)
        else:
            from_acc.current_balance -= amount

    elif txn_type == TransactionType.income:
        if to_account_id is None:
            raise ValueError("Income requires to_account_id")
        to_acc = await _get_owned_account(db, user_id, to_account_id)
        if to_acc.type == AccountType.credit_card:
            raise ValueError("Cannot record income directly to a credit card account")
        to_acc.current_balance += amount

    elif txn_type == TransactionType.transfer:
        if from_account_id is None or to_account_id is None:
            raise ValueError("Transfer requires both from_account_id and to_account_id")
        from_acc = await _get_owned_account(db, user_id, from_account_id)
        to_acc = await _get_owned_account(db, user_id, to_account_id)
        if from_acc.type == AccountType.credit_card:
            raise ValueError("Cannot transfer from a credit card account")
        if to_acc.type == AccountType.credit_card:
            credit_card_service.apply_cc_payment(from_acc, to_acc, amount)
        else:
            from_acc.current_balance -= amount
            to_acc.current_balance += amount
```

- [ ] **Step 4: Add missing imports to `transaction_service.py`**

At the top of `app/services/transaction_service.py`, update the imports to include `AccountType` and `credit_card_service`:

```python
from app.models.account import Account, AccountType
from app.services import credit_card_service
```

The existing import `from app.models.account import Account` should become `from app.models.account import Account, AccountType`.

- [ ] **Step 5: Run all dispatcher tests**

```bash
python -m pytest tests/test_transaction_service_cc.py -v 2>&1 | tail -25
```

Expected: 9 PASSED.

- [ ] **Step 6: Run the full test suite**

```bash
python -m pytest -v 2>&1 | tail -30
```

Expected: All tests pass. No regressions.

- [ ] **Step 7: Commit**

```bash
git add app/services/transaction_service.py tests/test_transaction_service_cc.py
git commit -m "feat: make _apply_balance credit-card-aware with typed dispatch"
```

---

## Task 6: Test revert behaviour (update and delete with CC accounts)

**Files:**
- Modify: `tests/test_transaction_service_cc.py`

- [ ] **Step 1: Append revert tests to `tests/test_transaction_service_cc.py`**

```python
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
```

- [ ] **Step 2: Run revert tests**

```bash
python -m pytest tests/test_transaction_service_cc.py -v 2>&1 | tail -20
```

Expected: 12 PASSED (9 original + 3 new).

- [ ] **Step 3: Run full suite one final time**

```bash
python -m pytest -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_transaction_service_cc.py
git commit -m "test: add revert behaviour tests for CC expense and payment"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Covered by |
|---|---|
| CC expense increases outstanding, not current_balance | Task 5 tests + implementation |
| CC expense blocked if over credit limit | Task 2 (`apply_cc_expense`) + Task 5 |
| CC payment reduces bank balance + outstanding | Task 2 (`apply_cc_payment`) + Task 5 |
| CC payment blocked if over outstanding | Task 2 + Task 5 |
| Normal bank expense reduces current_balance | Task 5 test |
| Normal income increases current_balance | Task 5 test |
| Income to CC blocked | Task 5 test |
| Transfer from CC blocked | Task 5 test |
| Normal bank→bank transfer unchanged | Task 5 test |
| Update/delete revert works for CC | Task 6 |
| `credit_limit` required for CC account creation | Task 3 schema test |
| `credit_limit` rejected for non-CC accounts | Task 3 schema test |
| `available_credit` = `credit_limit - outstanding_balance` | Task 3 schema test |
| CC account created with outstanding=0 | Task 4 |
| CC account initial_balance ignored | Task 4 |
| No new routes, migrations, or models | N/A — by omission |

**Placeholder scan:** None found.

**Type consistency:** `apply_cc_expense` / `apply_cc_payment` names are consistent across Task 2, Task 5, and the `transaction_service.py` implementation.
