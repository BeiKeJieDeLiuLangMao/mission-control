"""merge heads for task segments

Revision ID: 4b71ac7dc194
Revises: 3704ddb4afd1, a1b2c3d4e5f7
Create Date: 2026-03-29 19:02:27.406632

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b71ac7dc194'
down_revision = ('3704ddb4afd1', 'a1b2c3d4e5f7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
