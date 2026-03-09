from typing import Callable
from contextlib import contextmanager
from sqlalchemy.orm import Session

from sqlalchemy import Insert

OnConflictClause = Callable[[Insert], Insert]


def do_nothing_on_conflict(insert: Insert, **kwargs) -> Insert:
    return insert.on_conflict_do_nothing(**kwargs)


def do_update_on_conflict(insert: Insert, **kwargs) -> Insert:
    return insert.on_conflict_do_update(**kwargs)


def do_default_on_conflict(insert: Insert) -> Insert:
    return insert


@contextmanager
def bulk_operation_context(session: Session):
    """Context manager to mark bulk operations in session info."""
    session.info['bulk_operation'] = True
    try:
        yield
    finally:
        session.info.pop('bulk_operation', None)
