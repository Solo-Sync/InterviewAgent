from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260303_0002"
down_revision = "20260228_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("current_question_cursor", sa.JSON(), nullable=True))
    op.add_column("sessions", sa.Column("theta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "theta")
    op.drop_column("sessions", "current_question_cursor")
