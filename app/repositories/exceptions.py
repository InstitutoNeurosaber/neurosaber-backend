"""Repository exceptions"""

import re

from app.exceptions import HTTPExceptionMixin
from app.repositories.base_repository import BaseRepository

DUPLICATE_ERROR_TEMPLATE = re.compile(
    r'ERROR:  duplicate key value violates unique constraint "(?P<key>[^"]+)"'
)


class RepositoryError(HTTPExceptionMixin):
    """Base repository error"""

    detail = "Repository error"
    error_code = "repository_error"
    status_code = 500


class NotFoundError(RepositoryError):
    """Repository not found error"""

    detail = "Item not found"
    error_code = "not_found"
    status_code = 404


class DuplicateError(RepositoryError):
    """Item already exists in the repository"""

    detail = "Item already exists"
    error_code = "duplicate_item"
    status_code = 400

    @staticmethod
    def from_db_string(db_string: str, model: BaseRepository) -> "DuplicateError":
        """
        Create a DuplicateError from a database error string

        We deal with psycopg2 and Postgres error strings here.
        """
        res = DUPLICATE_ERROR_TEMPLATE.match(db_string)
        if not res:
            return DuplicateError(
                detail=f"Duplicate item found in {model._display_name()}"
            )

        key = res.group("key")
        field = key.removeprefix(model.__tablename__).removesuffix("_idx").strip("_")

        return DuplicateError(
            detail=f"Duplicate item found: {model._display_name()} on field {field}"
        )


class ReferencedError(RepositoryError):
    """Item is referenced by other items"""

    detail = "Item is referenced by other items"
    error_code = "referenced_item"
    status_code = 400
