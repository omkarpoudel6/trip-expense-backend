"""add completed value to trip_status_enum

Revision ID: 6c45e73ec627
Revises: 61f2a10fe650
Create Date: 2026-09-25 07:38:12.790972

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c45e73ec627'
down_revision: Union[str, None] = '61f2a10fe650'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE trip_status_enum ADD VALUE IF NOT EXISTS 'completed'")


def downgrade() -> None:
    pass
