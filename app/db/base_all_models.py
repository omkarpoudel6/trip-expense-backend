"""
Import every model here so Alembic's autogenerate can see the full schema
via Base.metadata. Add each new model's import as milestones progress.
"""

from app.db.base import Base  # noqa: F401
from app.models.category import Category # noqa: F401
from app.models.expense import Expense, ExpenseSplit # noqa: F401
from app.models.trip import Trip # noqa: F401
from app.models.trip_invite import Invite # noqa: F401
from app.models.settlement import Settlement  # noqa: F401
from app.models.trip_member import TripMember # noqa: F401
from app.models.user import User # noqa: F401
from app.models.expense_audit_log import ExpenseAuditLog  # noqa: F401
from app.models.push_token import PushToken  # noqa: F401
