"""seed default expense categories

Revision ID: <keep the auto-generated value>
Revises: <keep the auto-generated value>
Create Date: <keep the auto-generated value>

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e29f6ff945b7"
down_revision: Union[str, None] = "c7ffa8dbf83d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_CATEGORIES = [
    ("Food", "utensils"),
    ("Hotel", "bed"),
    ("Transport", "car"),
    ("Fuel", "gas-pump"),
    ("Shopping", "shopping-bag"),
    ("Activities", "hiking"),
    ("Entertainment", "film"),
    ("Visa", "passport"),
    ("Flight", "plane"),
    ("Miscellaneous", "more-horizontal"),
]

categories_table = sa.table(
    "categories",
    sa.column("id", sa.UUID()),
    sa.column("trip_id", sa.UUID()),
    sa.column("name", sa.String()),
    sa.column("icon", sa.String()),
)


def upgrade() -> None:
    op.bulk_insert(
        categories_table,
        [
            {"id": uuid.uuid4(), "trip_id": None, "name": name, "icon": icon}
            for name, icon in DEFAULT_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.execute(categories_table.delete().where(categories_table.c.trip_id.is_(None)))