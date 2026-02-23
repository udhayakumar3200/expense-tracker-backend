import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, AccountType


async def create_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    account_type: AccountType,
    initial_balance: Decimal = Decimal("0"),
) -> Account:
    account = Account(
        user_id=user_id,
        name=name,
        type=account_type,
        current_balance=initial_balance,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account


async def get_user_accounts(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[Account]:
    result = await db.execute(
        select(Account).where(Account.user_id == user_id)
    )
    return list(result.scalars().all())


async def update_balance(
    db: AsyncSession,
    account_id: uuid.UUID,
    new_balance: Decimal,
) -> Account | None:
    result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        return None
    account.current_balance = new_balance
    await db.flush()
    await db.refresh(account)
    return account
