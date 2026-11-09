from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.employee import utcnow


class RosterStatus(StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"


class RosterPeriod(Base):
    __tablename__ = "roster_periods"
    __table_args__ = (
        UniqueConstraint("year", "month", "version", name="uq_roster_period_version"),
        Index(
            "uq_roster_period_published",
            "year",
            "month",
            unique=True,
            sqlite_where=text("status = 'published'"),
            postgresql_where=text("status = 'published'"),
        ),
        Index(
            "uq_roster_period_draft",
            "year",
            "month",
            unique=True,
            sqlite_where=text("status = 'draft'"),
            postgresql_where=text("status = 'draft'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[RosterStatus] = mapped_column(
        Enum(RosterStatus, native_enum=False, length=20), default=RosterStatus.draft
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assignments = relationship(
        "RosterAssignment",
        back_populates="period",
        cascade="all, delete-orphan",
        order_by="RosterAssignment.date",
    )
    generation_runs = relationship(
        "GenerationRun", back_populates="period", cascade="all, delete-orphan"
    )


class RosterAssignment(Base):
    __tablename__ = "roster_assignments"
    __table_args__ = (
        UniqueConstraint(
            "roster_period_id", "employee_id", "date", name="uq_assignment_period_employee_date"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roster_period_id: Mapped[int] = mapped_column(
        ForeignKey("roster_periods.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    status_id: Mapped[int] = mapped_column(ForeignKey("shift_statuses.id"))
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    period = relationship("RosterPeriod", back_populates="assignments")
    employee = relationship("Employee", back_populates="assignments")
    status = relationship("ShiftStatus")


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roster_period_id: Mapped[int] = mapped_column(
        ForeignKey("roster_periods.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="succeeded")
    shortages: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)

    period = relationship("RosterPeriod", back_populates="generation_runs")
