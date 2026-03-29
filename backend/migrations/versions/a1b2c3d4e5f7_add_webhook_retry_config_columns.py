"""Add webhook-level retry configuration columns.

Revision ID: a1b2c3d4e5f7
Revises: fa6e83f8d9a1
Create Date: 2026-03-29 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "fa6e83f8d9a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add max_retries and retry_backoff_seconds to board_webhooks."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {col["name"] for col in inspector.get_columns("board_webhooks")}

    if "max_retries" not in existing_columns:
        op.add_column(
            "board_webhooks",
            sa.Column("max_retries", sa.Integer(), nullable=True),
        )

    if "retry_backoff_seconds" not in existing_columns:
        op.add_column(
            "board_webhooks",
            sa.Column("retry_backoff_seconds", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    """Remove max_retries and retry_backoff_seconds from board_webhooks."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {col["name"] for col in inspector.get_columns("board_webhooks")}

    if "retry_backoff_seconds" in existing_columns:
        op.drop_column("board_webhooks", "retry_backoff_seconds")

    if "max_retries" in existing_columns:
        op.drop_column("board_webhooks", "max_retries")
