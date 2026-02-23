from collections.abc import AsyncGenerator
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db as get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def get_current_user_id() -> uuid.UUID:
    # TODO: Replace with actual auth logic
    return uuid.UUID("00000000-0000-0000-0000-000000000001")
