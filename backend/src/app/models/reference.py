from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.employee import utcnow


class ShiftStatus(Base):
    __tablename__ = "shift_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(60))
    color: Mapped[str] = mapped_column(String(20))
    text_color: Mapped[str] = mapped_column(String(20), default="#111827")
    is_working: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class StaffingRequirement(Base):
    __tablename__ = "staffing_requirements"
    __table_args__ = (UniqueConstraint("weekday", "status_id", name="uq_staffing_weekday_status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = Monday, 6 = Sunday
    status_id: Mapped[int] = mapped_column(ForeignKey("shift_statuses.id", ondelete="CASCADE"))
    required_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status = relationship("ShiftStatus")


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
