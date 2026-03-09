import uuid

from fastapi import APIRouter, Depends
from fastapi_filter import FilterDepends
from fastapi_injector import Injected
from fastapi_pagination import Page, Params

from app.core.auth import verify_admin_api_key
from app.modules.certificate.filters import CourseAdminFilter
from app.modules.certificate.schemas import (
    CourseAdminResponse,
    CourseUpdateRequest,
)
from app.modules.certificate.service import CertificateService


admin_router = APIRouter(dependencies=[Depends(verify_admin_api_key)])


@admin_router.get(
    "/courses",
    response_model=Page[CourseAdminResponse],
    summary="Listar todos os cursos (incluindo não configurados)",
)
def list_all_courses(
    pagination_params: Params = Depends(),
    course_filter: CourseAdminFilter = FilterDepends(CourseAdminFilter),
    service: CertificateService = Injected(CertificateService),
) -> Page[CourseAdminResponse]:
    return service.list_all_courses(
        entity_filter=course_filter,
        pagination_params=pagination_params,
    )


@admin_router.patch(
    "/courses/{course_id}",
    response_model=CourseAdminResponse,
    summary="Atualizar metadados do curso",
)
def update_course(
    course_id: uuid.UUID,
    body: CourseUpdateRequest,
    service: CertificateService = Injected(CertificateService),
) -> CourseAdminResponse:
    return service.update_course_metadata(course_id, body)


@admin_router.post(
    "/sync-courses",
    summary="Sincronizar cursos com o Guru",
)
def sync_courses(
    service: CertificateService = Injected(CertificateService),
):
    count = service.sync_courses_from_guru()
    return {"synced": count}
