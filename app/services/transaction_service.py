import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.transaction import Transaction, TransactionType


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
        if transaction_type == TransactionType.expense:
            if from_account_id is None:
                raise ValueError("Expense requires from_account_id")
            result = await db.execute(
                select(Account).where(Account.id == from_account_id)
            )
            from_account = result.scalar_one_or_none()
            if from_account is None:
                raise ValueError("from_account not found")
            from_account.current_balance -= amount

        elif transaction_type == TransactionType.income:
            if to_account_id is None:
                raise ValueError("Income requires to_account_id")
            result = await db.execute(
                select(Account).where(Account.id == to_account_id)
            )
            to_account = result.scalar_one_or_none()
            if to_account is None:
                raise ValueError("to_account not found")
            to_account.current_balance += amount

        elif transaction_type == TransactionType.transfer:
            if from_account_id is None or to_account_id is None:
                raise ValueError("Transfer requires both from_account_id and to_account_id")
            result = await db.execute(
                select(Account).where(Account.id == from_account_id)
            )
            from_account = result.scalar_one_or_none()
            if from_account is None:
                raise ValueError("from_account not found")

            result = await db.execute(
                select(Account).where(Account.id == to_account_id)
            )
            to_account = result.scalar_one_or_none()
            if to_account is None:
                raise ValueError("to_account not found")

            from_account.current_balance -= amount
            to_account.current_balance += amount

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
