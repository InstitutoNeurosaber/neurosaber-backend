import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import BadRequestError
from app.modules.certificate.schemas import CourseUpdateRequest
from app.modules.certificate.service import CertificateService
from app.repositories.exceptions import NotFoundError
from app.services.guru.schemas import (
    GuruContact,
    GuruGroup,
    GuruProduct,
    GuruProductRef,
    GuruTransaction,
)
from tests.factories import CertificateEmissionFactory, CourseFactory


@pytest.fixture
def mock_course_repo():
    return MagicMock()


@pytest.fixture
def mock_emission_repo():
    return MagicMock()


@pytest.fixture
def service(mock_course_repo, mock_emission_repo):
    with patch("app.modules.certificate.service.GuruClient"):
        svc = CertificateService(
            course_repo=mock_course_repo,
            emission_repo=mock_emission_repo,
        )
        svc.guru_client = MagicMock()
        yield svc


class TestListCourses:
    def test_delegates_to_repo(self, service, mock_course_repo):
        mock_course_repo.get_available_courses.return_value = []
        result = service.list_courses()
        mock_course_repo.get_available_courses.assert_called_once()
        assert result == []

    def test_list_all_delegates_to_repo(self, service, mock_course_repo):
        mock_course_repo.get_all.return_value = []
        result = service.list_all_courses()
        mock_course_repo.get_all.assert_called_once()
        assert result == []


class TestEmitCertificate:
    def _setup_happy_path(self, service, mock_course_repo, mock_emission_repo):
        course = CourseFactory.build()
        mock_course_repo.get.return_value = course

        contact = GuruContact(
            id="contact-1",
            name="João Silva",
            doc="12345678901",
            email="joao@test.com",
            address_city="São Paulo",
            address_state="SP",
        )
        service.guru_client.find_contact_by_cpf.return_value = contact

        transaction = GuruTransaction(
            id="tx-1",
            status="approved",
            product=GuruProductRef(
                id=course.guru_product_id, internal_id=None, name="Curso"
            ),
        )
        service.guru_client.get_transactions_for_contact.return_value = [transaction]

        return course, contact, transaction

    @patch("app.modules.certificate.service.generate_certificate_pdf")
    def test_success(
        self, mock_pdf, service, mock_course_repo, mock_emission_repo
    ):
        mock_pdf.return_value = b"%PDF-fake-content"
        self._setup_happy_path(service, mock_course_repo, mock_emission_repo)

        pdf_bytes, token = service.emit_certificate("12345678901", uuid.uuid4())

        assert pdf_bytes == b"%PDF-fake-content"
        assert token is not None
        mock_emission_repo.db_session.add.assert_called_once()
        mock_emission_repo.db_session.commit.assert_called_once()
        mock_pdf.assert_called_once()

    def test_course_not_found(self, service, mock_course_repo):
        mock_course_repo.get.return_value = None

        with pytest.raises(NotFoundError, match="Curso não encontrado"):
            service.emit_certificate("12345678901", uuid.uuid4())

    def test_cpf_not_found_in_guru(self, service, mock_course_repo):
        mock_course_repo.get.return_value = CourseFactory.build()
        service.guru_client.find_contact_by_cpf.return_value = None

        with pytest.raises(BadRequestError, match="CPF não encontrado"):
            service.emit_certificate("12345678901", uuid.uuid4())

    def test_no_approved_transaction(self, service, mock_course_repo):
        course = CourseFactory.build()
        mock_course_repo.get.return_value = course
        service.guru_client.find_contact_by_cpf.return_value = GuruContact(
            id="c1", name="Test"
        )
        service.guru_client.get_transactions_for_contact.return_value = [
            GuruTransaction(
                id="tx-1",
                status="pending",
                product=GuruProductRef(id=course.guru_product_id),
            )
        ]

        with pytest.raises(BadRequestError, match="compra aprovada"):
            service.emit_certificate("12345678901", uuid.uuid4())

    def test_skips_non_approved_transactions(self, service, mock_course_repo):
        course = CourseFactory.build()
        mock_course_repo.get.return_value = course
        service.guru_client.find_contact_by_cpf.return_value = GuruContact(
            id="c1", name="Test"
        )
        service.guru_client.get_transactions_for_contact.return_value = [
            GuruTransaction(
                id="tx-refused",
                status="refused",
                product=GuruProductRef(id=course.guru_product_id),
            ),
            GuruTransaction(
                id="tx-cancelled",
                status="cancelled",
                product=GuruProductRef(id=course.guru_product_id),
            ),
        ]

        with pytest.raises(BadRequestError, match="compra aprovada"):
            service.emit_certificate("12345678901", uuid.uuid4())

    @patch("app.modules.certificate.service.generate_certificate_pdf")
    def test_matches_guru_internal_id(
        self, mock_pdf, service, mock_course_repo, mock_emission_repo
    ):
        mock_pdf.return_value = b"%PDF-fake"
        course = CourseFactory.build(guru_internal_id="internal-123")
        mock_course_repo.get.return_value = course
        service.guru_client.find_contact_by_cpf.return_value = GuruContact(
            id="c1", name="Test"
        )
        service.guru_client.get_transactions_for_contact.return_value = [
            GuruTransaction(
                id="tx-1",
                status="approved",
                product=GuruProductRef(
                    id="different-id", internal_id="internal-123"
                ),
            )
        ]

        pdf_bytes, token = service.emit_certificate("12345678901", course.id)
        assert pdf_bytes == b"%PDF-fake"


class TestValidateCertificate:
    def test_success(self, service, mock_emission_repo):
        course = CourseFactory.build()
        emission = CertificateEmissionFactory.build(course_id=course.id)
        emission.course = course
        mock_emission_repo.get_by_token.return_value = emission

        result = service.validate_certificate(emission.token)

        assert result.token == emission.token
        assert result.contact_name == emission.contact_name
        assert result.course_name == course.name

    def test_not_found(self, service, mock_emission_repo):
        mock_emission_repo.get_by_token.return_value = None

        with pytest.raises(NotFoundError, match="Certificado não encontrado"):
            service.validate_certificate("nonexistent-token")


class TestUpdateCourseMetadata:
    def test_success(self, service, mock_course_repo):
        course = CourseFactory.build()
        mock_course_repo.get.return_value = course

        data = CourseUpdateRequest(carga_horaria=80)
        result = service.update_course_metadata(course.id, data)

        assert result.carga_horaria == 80
        mock_course_repo.db_session.commit.assert_called_once()

    def test_not_found(self, service, mock_course_repo):
        mock_course_repo.get.return_value = None

        with pytest.raises(NotFoundError, match="Curso não encontrado"):
            service.update_course_metadata(
                uuid.uuid4(), CourseUpdateRequest(carga_horaria=80)
            )


class TestSyncCoursesFromGuru:
    def test_creates_new_courses(self, service, mock_course_repo):
        products = [
            GuruProduct(
                id="prod-new",
                internal_id="int-new",
                name="Novo Curso",
                group=GuruGroup(id="g1", name="Ingressos"),
            )
        ]
        service.guru_client.get_ingresso_products.return_value = products
        mock_course_repo.get_by_guru_product_id.return_value = None

        count = service.sync_courses_from_guru()

        assert count == 1
        mock_course_repo.db_session.add.assert_called_once()
        mock_course_repo.db_session.commit.assert_called_once()

    def test_updates_existing_courses(self, service, mock_course_repo):
        existing_course = CourseFactory.build(
            guru_product_id="prod-existing", name="Old Name"
        )
        products = [
            GuruProduct(
                id="prod-existing",
                internal_id="int-updated",
                name="Updated Name",
                group=GuruGroup(id="g1", name="Ingressos"),
            )
        ]
        service.guru_client.get_ingresso_products.return_value = products
        mock_course_repo.get_by_guru_product_id.return_value = existing_course

        count = service.sync_courses_from_guru()

        assert count == 1
        assert existing_course.name == "Updated Name"
        assert existing_course.guru_internal_id == "int-updated"
        mock_course_repo.db_session.commit.assert_called_once()

    def test_handles_guru_error(self, service):
        service.guru_client.get_ingresso_products.side_effect = Exception(
            "API down"
        )

        count = service.sync_courses_from_guru()

        assert count == 0
