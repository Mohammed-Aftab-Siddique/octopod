from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index("uq_employees_employee_code_lower", text("lower(employee_code)"), unique=True),
        Index("uq_employees_email_lower", text("lower(email)"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rotation_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Primary shift code (e.g. "G"). ``None`` means derive it from
    # ``rotation_offset`` at generation time.
    default_shift: Mapped[str | None] = mapped_column(String(8), default=None, nullable=True)
    # Start of the employee's two-day week-off block, using ISO weekdays
    # (0 = Monday … 6 = Sunday). For example 5 means Saturday–Sunday and
    # 0 means Monday–Tuesday.
    week_off_start_day: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user = relationship("User", back_populates="employee", uselist=False)
    availability = relationship(
        "Availability", back_populates="employee", cascade="all, delete-orphan"
    )
    assignments = relationship("RosterAssignment", back_populates="employee")
