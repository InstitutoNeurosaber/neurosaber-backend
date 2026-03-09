import threading

from fastapi_injector.request_scope import _request_id_ctx
from pydantic import BaseModel


def req_or_thread_id():
    try:
        return _request_id_ctx.get()
    except LookupError:
        return threading.get_ident()


class RequestContext(BaseModel):
    jwt: dict | None = None
    user_id: str | None = None
    authenticated: bool = True


_request_context_cache = {}


def get_request_context():
    request_id = req_or_thread_id()
    if ctx := _request_context_cache.get(request_id):
        return ctx

    ctx = RequestContext()
    _request_context_cache[request_id] = ctx
    return ctx


