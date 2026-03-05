from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260228_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("question_set_id", sa.String(), nullable=False),
        sa.Column("scoring_policy_id", sa.String(), nullable=False),
        sa.Column("scaffold_policy_id", sa.String(), nullable=False),
        sa.Column("candidate", sa.JSON(), nullable=True),
        sa.Column("thresholds", sa.JSON(), nullable=True),
        sa.Column("last_next_action", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(op.f("ix_sessions_state"), "sessions", ["state"], unique=False)

    op.create_table(
        "turns",
        sa.Column("turn_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("state_before", sa.String(), nullable=False),
        sa.Column("state_after", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("turn_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("turn_id"),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_turn_session_idempotency"),
        sa.UniqueConstraint("session_id", "turn_index", name="uq_turn_session_index"),
    )
    op.create_index(op.f("ix_turns_session_id"), "turns", ["session_id"], unique=False)
    op.create_index("idx_turns_session_created_at", "turns", ["session_id", "created_at"], unique=False)

    op.create_table(
        "events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("turn_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(op.f("ix_events_event_type"), "events", ["event_type"], unique=False)
    op.create_index(op.f("ix_events_session_id"), "events", ["session_id"], unique=False)
    op.create_index(op.f("ix_events_turn_id"), "events", ["turn_id"], unique=False)
    op.create_index("idx_events_session_created_at", "events", ["session_id", "created_at"], unique=False)

    op.create_table(
        "reports",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("report_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("turn_id", sa.String(), nullable=False),
        sa.Column("human_scores", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_annotations_session_id"), "annotations", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_annotations_session_id"), table_name="annotations")
    op.drop_table("annotations")

    op.drop_table("reports")

    op.drop_index("idx_events_session_created_at", table_name="events")
    op.drop_index(op.f("ix_events_turn_id"), table_name="events")
    op.drop_index(op.f("ix_events_session_id"), table_name="events")
    op.drop_index(op.f("ix_events_event_type"), table_name="events")
    op.drop_table("events")

    op.drop_index("idx_turns_session_created_at", table_name="turns")
    op.drop_index(op.f("ix_turns_session_id"), table_name="turns")
    op.drop_table("turns")

    op.drop_index(op.f("ix_sessions_state"), table_name="sessions")
    op.drop_table("sessions")
