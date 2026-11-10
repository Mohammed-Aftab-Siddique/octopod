"""fixed shift rotation

Revision ID: c2d3e4f5a6b7
Revises: b1f2c3d4e5f6
Create Date: 2026-11-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1f2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("default_shift", sa.String(length=8), nullable=True))
    op.add_column(
        "employees",
        sa.Column("weekly_off_days", sa.Integer(), nullable=False, server_default=sa.text("2")),
    )


def downgrade() -> None:
    op.drop_column("employees", "weekly_off_days")
    op.drop_column("employees", "default_shift")
