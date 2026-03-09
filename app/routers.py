from fastapi import APIRouter
from app.modules.certificate.routers import router as certificate_router
from app.modules.certificate.admin_routers import admin_router


def get_app_router():
    router = APIRouter()

    router.include_router(
        certificate_router,
        prefix="/api",
        tags=["certificates"],
    )

    router.include_router(
        admin_router,
        prefix="/api/admin",
        tags=["admin"],
    )

    return router
