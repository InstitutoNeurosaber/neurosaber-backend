from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, status
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

from app.core.config import settings
from app.core.logging import AccessLoggerMiddleware
from app.core.scheduler import start_scheduler, stop_scheduler
from .dependencies import DependencyInjector
from .routers import get_app_router


def create_app(
    dp_injector: DependencyInjector = DependencyInjector(
        db_url=settings.DB_URL
    )
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.GURU_API_KEY:
            start_scheduler(dp_injector)
        yield
        stop_scheduler()

    app = FastAPI(
        middleware=[Middleware(AccessLoggerMiddleware)],
        redirect_slashes=False,
        lifespan=lifespan,
    )

    dp_injector.setup_injections(app)
    dp_injector.apply_bindings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://faculdadeneurosaber.com.br",
            "https://www.faculdadeneurosaber.com.br",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["content-disposition"],
    )

    router = APIRouter()
    app_router = get_app_router()

    @router.get("/health", status_code=status.HTTP_200_OK)
    def sanity_check():
        return "FastAPI running!"

    app.include_router(app_router)
    app.include_router(router)
    add_pagination(app)

    return app


app = create_app()
