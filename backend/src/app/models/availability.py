from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.employee import utcnow


class AvailabilityKind(StrEnum):
    leave = "leave"
    comp_off = "comp_off"
    unavailable = "unavailable"


class Availability(Base):
    __tablename__ = "availability"
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_availability_employee_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[AvailabilityKind] = mapped_column(
        Enum(AvailabilityKind, native_enum=False, length=20), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee = relationship("Employee", back_populates="availability")
