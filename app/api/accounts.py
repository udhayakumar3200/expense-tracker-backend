import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user_id
from app.schemas.account_schema import AccountCreate, AccountResponse, AccountUpdate
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
        credit_limit=data.credit_limit,
    )
    return account


@router.get("/get_accounts", response_model=list[AccountResponse])
async def get_accounts(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    accounts = await account_service.get_user_accounts(db=db, user_id=user_id)
    return accounts


@router.get("/get_account/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    account = await account_service.get_account(db=db, user_id=user_id, account_id=account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return account


@router.patch("/update_account/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    data: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        account = await account_service.update_account(
            db=db,
            user_id=user_id,
            account_id=account_id,
            name=data.name,
            current_balance=data.current_balance,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return account


@router.delete("/delete_account/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    try:
        deleted = await account_service.delete_account(
            db=db, user_id=user_id, account_id=account_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    return None
