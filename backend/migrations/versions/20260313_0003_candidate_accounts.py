from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260313_0003"
down_revision = "20260303_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_accounts",
        sa.Column("username", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "username ~ '^[A-Za-z0-9]{1,20}$'",
            name="ck_candidate_accounts_username_format",
        ),
        sa.PrimaryKeyConstraint("username"),
    )


def downgrade() -> None:
    op.drop_table("candidate_accounts")
