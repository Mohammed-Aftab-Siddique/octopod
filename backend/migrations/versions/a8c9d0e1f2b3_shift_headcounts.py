"""shift headcounts

Revision ID: a8c9d0e1f2b3
Revises: f6a7b8c9d0e1
Create Date: 2026-11-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c9d0e1f2b3"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Copy the largest weekday value onto every row before collapsing the
    # weekday dimension.
    op.execute(
        "UPDATE staffing_requirements SET required_count = ("
        "SELECT MAX(r2.required_count) FROM staffing_requirements r2 "
        "WHERE r2.status_id = staffing_requirements.status_id)"
    )
    op.execute(
        "DELETE FROM staffing_requirements WHERE id NOT IN ("
        "SELECT MAX(id) FROM staffing_requirements GROUP BY status_id)"
    )
    with op.batch_alter_table("staffing_requirements", schema=None) as batch_op:
        batch_op.drop_constraint("uq_staffing_weekday_status", type_="unique")
        batch_op.drop_column("weekday")
        batch_op.create_unique_constraint("uq_staffing_status", ["status_id"])


def downgrade() -> None:
    with op.batch_alter_table("staffing_requirements", schema=None) as batch_op:
        batch_op.drop_constraint("uq_staffing_status", type_="unique")
        batch_op.add_column(
            sa.Column("weekday", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.create_unique_constraint(
            "uq_staffing_weekday_status", ["weekday", "status_id"]
        )
