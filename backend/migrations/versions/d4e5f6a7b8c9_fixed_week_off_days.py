"""fixed week-off days

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-11-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column(
            "week_off_start_day",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.execute("UPDATE employees SET week_off_start_day = rotation_offset % 7")
    op.execute("UPDATE availability SET kind = 'unavailable' WHERE kind = 'week_off'")


def downgrade() -> None:
    op.drop_column("employees", "week_off_start_day")
