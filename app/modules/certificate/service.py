import logging
import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi_filter.base.filter import BaseFilterModel
from fastapi_pagination import Page, Params
from injector import Inject

from app.exceptions import BadRequestError
from app.modules.certificate.models import CertificateEmission, Course
from app.modules.certificate.repository import (
    CertificateEmissionRepository,
    CourseRepository,
)
from app.modules.certificate.schemas import (
    CertificateValidationResponse,
    CourseAdminResponse,
    CourseResponse,
    CourseUpdateRequest,
)
from app.repositories.exceptions import NotFoundError
from app.services.guru.client import GuruClient
from app.services.pdf.service import generate_certificate_pdf

logger = logging.getLogger(__name__)


class CertificateService:
    def __init__(
        self,
        course_repo: Inject[CourseRepository],
        emission_repo: Inject[CertificateEmissionRepository],
    ):
        self.course_repo = course_repo
        self.emission_repo = emission_repo
        self.guru_client = GuruClient()

    def list_courses(
        self,
        entity_filter: BaseFilterModel | None = None,
        pagination_params: Params | None = None,
    ) -> Page[CourseResponse] | list[CourseResponse]:
        return self.course_repo.get_available_courses(
            entity_filter=entity_filter,
            pagination_params=pagination_params,
        )

    def list_all_courses(
        self,
        entity_filter: BaseFilterModel | None = None,
        pagination_params: Params | None = None,
    ) -> Page[CourseAdminResponse] | list[CourseAdminResponse]:
        return self.course_repo.get_all(
            entity_filter=entity_filter,
            pagination_params=pagination_params,
        )

    def emit_certificate(self, cpf_digits: str, course_id: UUID) -> tuple[bytes, str]:
        course = self.course_repo.get(course_id)
        if not course:
            raise NotFoundError(detail="Curso não encontrado")
        contact = self.guru_client.find_contact_by_cpf(cpf_digits)
        if not contact:
            raise BadRequestError(detail="CPF não encontrado na base de dados")

        transactions = self.guru_client.get_transactions_for_contact(contact.id)

        approved_tx = None
        for tx in transactions:
            if tx.status and tx.status.lower() != "approved":
                continue
            if not tx.product:
                continue
            if (
                tx.product.id == course.guru_product_id
                or tx.product.internal_id == course.guru_product_id
                or tx.product.id == course.guru_internal_id
                or tx.product.internal_id == course.guru_internal_id
            ):
                approved_tx = tx
                break

        if not approved_tx:
            raise BadRequestError(
                detail="Não foi encontrada uma compra aprovada deste curso para o CPF informado"
            )

        token = secrets.token_urlsafe(12)

        issued_location = None
        if contact.address_city and contact.address_state:
            issued_location = f"{contact.address_city} - {contact.address_state}"

        now = datetime.now(tz=UTC)

        emission = CertificateEmission(
            token=token,
            contact_name=contact.name or "Aluno",
            contact_cpf=f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}",
            contact_email=contact.email,
            course_id=course.id,
            guru_transaction_id=approved_tx.id,
            issued_at=now,
            issued_location=issued_location,
        )
        self.emission_repo.db_session.add(emission)
        self.emission_repo.db_session.commit()
        self.emission_repo.db_session.refresh(emission)

        pdf_bytes = generate_certificate_pdf(
            contact_name=contact.name or "Aluno",
            contact_cpf=cpf_digits,
            course_name=course.name,
            course_display_name=course.display_name,
            carga_horaria=course.carga_horaria,
            conteudo_programatico=course.conteudo_programatico,
            registration_info=course.registration_info,
            issued_at=now,
            issued_location=issued_location,
            token=token,
        )

        return pdf_bytes, token

    def update_course_metadata(self, course_id: UUID, data: CourseUpdateRequest) -> CourseAdminResponse:
        course = self.course_repo.get(course_id)
        if not course:
            raise NotFoundError(detail="Curso não encontrado")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(course, key, value)

        self.course_repo.db_session.commit()
        self.course_repo.db_session.refresh(course)

        return CourseAdminResponse.model_validate(course)

    def validate_certificate(self, token: str) -> CertificateValidationResponse:
        emission = self.emission_repo.get_by_token(token)
        if not emission:
            raise NotFoundError(detail="Certificado não encontrado")

        return CertificateValidationResponse(
            token=emission.token,
            contact_name=emission.contact_name,
            course_name=emission.course.name,
            course_display_name=emission.course.display_name,
            issued_at=emission.issued_at,
            issued_location=emission.issued_location,
        )

    def sync_courses_from_guru(self) -> int:
        logger.info("Starting course sync from Guru...")
        try:
            products = self.guru_client.get_ingresso_products()
        except Exception as e:
            logger.error(f"Failed to fetch products from Guru: {e}")
            return 0

        synced = 0
        for product in products:
            existing = self.course_repo.get_by_guru_product_id(product.id)
            if existing:
                existing.name = product.name or existing.name
                existing.guru_internal_id = product.internal_id or product.marketplace_id
                existing.is_active = True
                if product.group:
                    existing.group_id = product.group.id
                    existing.group_name = product.group.name
            else:
                new_course = Course(
                    guru_product_id=product.id,
                    guru_internal_id=product.internal_id or product.marketplace_id,
                    name=product.name or "Curso sem nome",
                    group_id=product.group.id if product.group else None,
                    group_name=product.group.name if product.group else None,
                    is_active=True,
                )
                self.course_repo.db_session.add(new_course)
            synced += 1

        self.course_repo.db_session.commit()
        logger.info(f"Synced {synced} courses from Guru")
        return synced
