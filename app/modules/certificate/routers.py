import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from fastapi_filter import FilterDepends
from fastapi_injector import Injected
from fastapi_pagination import Page, Params

from app.modules.certificate.filters import CourseFilter
from app.modules.certificate.schemas import (
    CertificateEmitRequest,
    CertificateValidationResponse,
    CourseResponse,
)
from app.modules.certificate.service import CertificateService

router = APIRouter()


@router.get(
    "/courses",
    response_model=Page[CourseResponse],
    summary="Listar cursos disponíveis para certificação",
)
def list_courses(
    pagination_params: Params = Depends(),
    course_filter: CourseFilter = FilterDepends(CourseFilter),
    service: CertificateService = Injected(CertificateService),
) -> Page[CourseResponse]:
    return service.list_courses(
        entity_filter=course_filter,
        pagination_params=pagination_params,
    )


@router.post(
    "/certificates/emit",
    summary="Emitir certificado em PDF",
    response_class=StreamingResponse,
)
def emit_certificate(
    body: CertificateEmitRequest,
    service: CertificateService = Injected(CertificateService),
):
    pdf_bytes, token = service.emit_certificate(body.cpf, body.course_id)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="certificado_{token}.pdf"',
        },
    )


@router.get(
    "/certificates/validate/{token}",
    response_model=CertificateValidationResponse,
    summary="Validar certificado por token",
)
def validate_certificate(
    token: str,
    service: CertificateService = Injected(CertificateService),
) -> CertificateValidationResponse:
    return service.validate_certificate(token)
