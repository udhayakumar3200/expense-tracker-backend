import uuid
from decimal import Decimal

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, AccountType
from app.models.transaction import Transaction


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


async def get_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> Account | None:
    result = await db.execute(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def update_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    name: str | None = None,
    account_type: AccountType | None = None,
    current_balance: Decimal | None = None,
) -> Account | None:
    account = await get_account(db, user_id, account_id)
    if account is None:
        return None
    if name is not None:
        account.name = name
    if account_type is not None:
        account.type = account_type
    if current_balance is not None:
        account.current_balance = current_balance
    await db.flush()
    await db.refresh(account)
    return account


async def delete_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> bool:
    account = await get_account(db, user_id, account_id)
    if account is None:
        return False
    ref = await db.execute(
        select(Transaction.id).where(
            or_(
                Transaction.from_account_id == account_id,
                Transaction.to_account_id == account_id,
            )
        ).limit(1)
    )
    if ref.first() is not None:
        raise ValueError("account has transactions")
    await db.execute(delete(Account).where(Account.id == account_id))
    await db.flush()
    return True
