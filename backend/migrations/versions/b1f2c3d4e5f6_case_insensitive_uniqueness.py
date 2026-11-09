"""case-insensitive identifiers and single draft per month

Revision ID: b1f2c3d4e5f6
Revises: 9c94dbe2bb07
Create Date: 2026-11-07 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1f2c3d4e5f6"
down_revision: str | None = "9c94dbe2bb07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Normalise existing identifiers before adding case-insensitive indexes.
    op.execute("UPDATE employees SET employee_code = lower(employee_code)")
    op.execute("UPDATE employees SET email = lower(email)")
    op.execute("UPDATE users SET email = lower(email)")

    op.create_index(
        "uq_employees_employee_code_lower",
        "employees",
        [sa.text("lower(employee_code)")],
        unique=True,
    )
    op.create_index(
        "uq_employees_email_lower",
        "employees",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )

    op.create_index(
        "uq_roster_period_draft",
        "roster_periods",
        ["year", "month"],
        unique=True,
        sqlite_where=sa.text("status = 'draft'"),
        postgresql_where=sa.text("status = 'draft'"),
    )


def downgrade() -> None:
    op.drop_index("uq_roster_period_draft", table_name="roster_periods")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_index("uq_employees_email_lower", table_name="employees")
    op.drop_index("uq_employees_employee_code_lower", table_name="employees")
