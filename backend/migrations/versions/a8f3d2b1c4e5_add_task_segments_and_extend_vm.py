"""add task_segments table and extend vector_memories

Revision ID: a8f3d2b1c4e5
Revises: 4b71ac7dc194
Create Date: 2026-03-29 19:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a8f3d2b1c4e5"
down_revision = "4b71ac7dc194"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create task_segments table
    op.create_table(
        "task_segments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("task_type", sa.String(), nullable=True),
        sa.Column("turn_ids", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("first_turn_at", sa.DateTime(), nullable=False),
        sa.Column("last_turn_at", sa.DateTime(), nullable=False),
        sa.Column("segmentation_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("event_time", sa.DateTime(), nullable=False),
        sa.Column("ingestion_time", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_segments_session_id"), "task_segments", ["session_id"], unique=False)
    op.create_index(op.f("ix_task_segments_user_id"), "task_segments", ["user_id"], unique=False)

    # Extend vector_memories with task_segment_id and memory_subtype
    op.add_column("vector_memories", sa.Column("task_segment_id", sa.String(), nullable=True))
    op.add_column("vector_memories", sa.Column("memory_subtype", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_vector_memories_task_segment_id"), "vector_memories", ["task_segment_id"], unique=False
    )
    op.create_index(
        op.f("ix_vector_memories_memory_subtype"), "vector_memories", ["memory_subtype"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vector_memories_memory_subtype"), table_name="vector_memories")
    op.drop_index(op.f("ix_vector_memories_task_segment_id"), table_name="vector_memories")
    op.drop_column("vector_memories", "memory_subtype")
    op.drop_column("vector_memories", "task_segment_id")

    op.drop_index(op.f("ix_task_segments_user_id"), table_name="task_segments")
    op.drop_index(op.f("ix_task_segments_session_id"), table_name="task_segments")
    op.drop_table("task_segments")
