import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType


async def _get_owned_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> Account:
    result = await db.execute(
        select(Account).where(
            and_(Account.id == account_id, Account.user_id == user_id)
        )
    )
    acc = result.scalar_one_or_none()
    if acc is None:
        raise ValueError("account not found")
    return acc


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
        from_acc.current_balance -= amount
    elif txn_type == TransactionType.income:
        if to_account_id is None:
            raise ValueError("Income requires to_account_id")
        to_acc = await _get_owned_account(db, user_id, to_account_id)
        to_acc.current_balance += amount
    elif txn_type == TransactionType.transfer:
        if from_account_id is None or to_account_id is None:
            raise ValueError("Transfer requires both from_account_id and to_account_id")
        from_acc = await _get_owned_account(db, user_id, from_account_id)
        to_acc = await _get_owned_account(db, user_id, to_account_id)
        from_acc.current_balance -= amount
        to_acc.current_balance += amount


async def _validate_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(Category).where(
            and_(Category.id == category_id, Category.user_id == user_id)
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("category not found")


async def create_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: Decimal,
    transaction_type: TransactionType,
    transaction_date: datetime,
    from_account_id: uuid.UUID | None = None,
    to_account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    description: str | None = None,
    reference_hash: str | None = None,
) -> Transaction:
    async with db.begin_nested():
        if category_id is not None:
            await _validate_category(db, user_id, category_id)

        await _apply_balance(
            db,
            user_id,
            transaction_type,
            amount,
            from_account_id,
            to_account_id,
        )

        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            type=transaction_type,
            transaction_date=transaction_date,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            category_id=category_id,
            description=description,
            reference_hash=reference_hash,
        )
        db.add(transaction)
        await db.flush()
        await db.refresh(transaction)

    return transaction


async def get_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> Transaction | None:
    result = await db.execute(
        select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def list_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    transaction_date_from: datetime | None = None,
    transaction_date_to: datetime | None = None,
    txn_type: TransactionType | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
) -> list[Transaction]:
    conditions = [Transaction.user_id == user_id]
    if transaction_date_from is not None:
        conditions.append(Transaction.transaction_date >= transaction_date_from)
    if transaction_date_to is not None:
        conditions.append(Transaction.transaction_date <= transaction_date_to)
    if txn_type is not None:
        conditions.append(Transaction.type == txn_type)
    if account_id is not None:
        conditions.append(
            or_(
                Transaction.from_account_id == account_id,
                Transaction.to_account_id == account_id,
            )
        )
    if category_id is not None:
        conditions.append(Transaction.category_id == category_id)

    stmt = (
        select(Transaction)
        .where(and_(*conditions))
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
    updates: dict[str, Any],
) -> Transaction | None:
    txn = await get_transaction(db, user_id, transaction_id)
    if txn is None:
        return None

    new_type: TransactionType = updates.get("type", txn.type)
    new_amount: Decimal = updates.get("amount", txn.amount)
    new_from = updates.get("from_account_id", txn.from_account_id)
    new_to = updates.get("to_account_id", txn.to_account_id)

    async with db.begin_nested():
        if "category_id" in updates and updates["category_id"] is not None:
            await _validate_category(db, user_id, updates["category_id"])

        await _apply_balance(
            db, user_id, txn.type, -txn.amount, txn.from_account_id, txn.to_account_id
        )
        await _apply_balance(db, user_id, new_type, new_amount, new_from, new_to)

        for field in (
            "amount",
            "type",
            "transaction_date",
            "from_account_id",
            "to_account_id",
            "category_id",
            "description",
        ):
            if field in updates:
                setattr(txn, field, updates[field])

        await db.flush()
        await db.refresh(txn)

    return txn


async def delete_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> bool:
    txn = await get_transaction(db, user_id, transaction_id)
    if txn is None:
        return False

    async with db.begin_nested():
        await _apply_balance(
            db, user_id, txn.type, -txn.amount, txn.from_account_id, txn.to_account_id
        )
        await db.execute(delete(Transaction).where(Transaction.id == transaction_id))
        await db.flush()

    return True
