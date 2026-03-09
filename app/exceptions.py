"""Base module for HTTP Exceptions"""

from typing import Any

from fastapi import HTTPException


class HTTPExceptionMixin(HTTPException):
    """Base HTTP exception"""

    error_code = "internal_server_error"
    detail = "Internal Server Error"
    status_code = 500

    def __init__(
        self,
        *,
        status_code: int = None,
        detail: Any = None,
        error_code: str = None,
        **kwargs,
    ) -> None:
        self.error_code = error_code or self.error_code

        super().__init__(
            status_code=status_code or self.status_code,
            detail=detail or self.detail,
            **kwargs,
        )


class BadRequestError(HTTPExceptionMixin):
    """Bad request error"""

    error_code = "bad_request"
    detail = "Bad request"
    status_code = 400


class UnauthorizedError(HTTPExceptionMixin):
    error_code = "unauthorized"
    detail = "Invalid or missing API key"
    status_code = 401