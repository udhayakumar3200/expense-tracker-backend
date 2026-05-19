import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, String, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
import enum


class AccountType(str, enum.Enum):
    upi = "upi"
    bank = "bank"
    cash = "cash"
    credit_card = "credit_card"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    name: Mapped[str] = mapped_column(String, nullable=False)

    type: Mapped[AccountType] = mapped_column(
        Enum(AccountType),
        nullable=False
    )

    current_balance: Mapped[float] = mapped_column(
        Numeric(12, 2),
        default=0
    )

    credit_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    outstanding_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    statement_due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    minimum_due: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )