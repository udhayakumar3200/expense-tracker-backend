import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user_id
from app.schemas.account_schema import AccountCreate, AccountResponse
from app.services import account_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("/create_account", response_model=AccountResponse)
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    account = await account_service.create_account(
        db=db,
        user_id=user_id,
        name=data.name,
        account_type=data.type,
        initial_balance=data.initial_balance,
    )
    return account


@router.get("/get_accounts", response_model=list[AccountResponse])
async def get_accounts(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    accounts = await account_service.get_user_accounts(db=db, user_id=user_id)
    return accounts
