"""merge webhook retry and task segments branches

Revision ID: 3d7e921899b3
Revises: a1b2c3d4e5f7, a8f3d2b1c4e5
Create Date: 2026-03-29 22:35:58.061029

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3d7e921899b3'
down_revision = ('a1b2c3d4e5f7', 'a8f3d2b1c4e5')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
