from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.context import get_request_context
from app.core.config import settings
from app.exceptions import UnauthorizedError


class AuthenticatedUser:
    @classmethod
    def current_user_id(
        cls,
        request: Request,
        http_auth: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    ) -> str:
        return getattr(request.state, "user_id", cls.get_user_data(request, http_auth))

    @classmethod
    def current_user_email(
        cls,
        request: Request,
        http_auth: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    ) -> str:
        return getattr(request.state, "email", cls.get_user_data(request, http_auth))

    @classmethod
    def get_user_data(
        cls,
        request: Request,
        http_auth: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    ) -> str:
        try:
            payload = jwt.decode(
                http_auth.credentials,
                settings.AUTH_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            request.state.user_id = payload.get("sub")
            request.state.email = payload.get("email")
            # If request comming from API we should check the apikey is still valid

            req_ctx = get_request_context()
            req_ctx.jwt = payload
            req_ctx.user_id = payload.get("sub")

            return payload.get("sub")
        except (JWTError, AttributeError):
            raise HTTPException(  # noqa: B904
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )


admin_api_key_header = APIKeyHeader(name="x-admin-api-key", auto_error=False)


def verify_admin_api_key(api_key: str = Depends(admin_api_key_header)) -> bool:
    if not settings.ADMIN_API_KEY or api_key != settings.ADMIN_API_KEY:
        raise UnauthorizedError()
    return True
