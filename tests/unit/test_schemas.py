import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.certificate.schemas import (
    CertificateEmitRequest,
    CertificateValidationResponse,
    CourseAdminResponse,
    CourseResponse,
    CourseUpdateRequest,
)
from tests.factories import CourseFactory


class TestCertificateEmitRequest:
    def test_valid_cpf_digits(self):
        req = CertificateEmitRequest(cpf="12345678901", course_id=uuid.uuid4())
        assert req.cpf == "12345678901"

    def test_valid_cpf_formatted(self):
        req = CertificateEmitRequest(cpf="123.456.789-01", course_id=uuid.uuid4())
        assert req.cpf == "12345678901"

    def test_invalid_cpf_short(self):
        with pytest.raises(ValidationError, match="CPF deve ter 11 digitos"):
            CertificateEmitRequest(cpf="1234567890", course_id=uuid.uuid4())

    def test_invalid_cpf_long(self):
        with pytest.raises(ValidationError, match="CPF deve ter 11 digitos"):
            CertificateEmitRequest(cpf="123456789012", course_id=uuid.uuid4())


class TestCourseResponse:
    def test_from_attributes(self):
        course = CourseFactory.build()
        resp = CourseResponse.model_validate(course, from_attributes=True)
        assert resp.id == course.id
        assert resp.name == course.name
        assert resp.display_name == course.display_name
        assert resp.carga_horaria == course.carga_horaria


class TestCourseAdminResponse:
    def test_from_attributes(self):
        course = CourseFactory.build(
            conteudo_programatico={"modules": []},
            registration_info="Info de registro",
        )
        resp = CourseAdminResponse.model_validate(course, from_attributes=True)
        assert resp.id == course.id
        assert resp.guru_product_id == course.guru_product_id
        assert resp.guru_internal_id == course.guru_internal_id
        assert resp.is_active == course.is_active
        assert resp.conteudo_programatico == {"modules": []}
        assert resp.registration_info == "Info de registro"
        assert resp.created_at == course.created_at
        assert resp.updated_at == course.updated_at


class TestCourseUpdateRequest:
    def test_partial_update(self):
        req = CourseUpdateRequest(carga_horaria=20)
        dumped = req.model_dump(exclude_unset=True)
        assert dumped == {"carga_horaria": 20}
        assert "display_name" not in dumped
        assert "conteudo_programatico" not in dumped

    def test_full_update(self):
        req = CourseUpdateRequest(
            display_name="Nome Exibição",
            carga_horaria=60,
            conteudo_programatico={"modules": []},
            registration_info="Registro",
        )
        dumped = req.model_dump(exclude_unset=True)
        assert len(dumped) == 4


class TestCertificateValidationResponse:
    def test_serialization(self):
        now = datetime.now(tz=UTC)
        resp = CertificateValidationResponse(
            token="abc123",
            contact_name="João Silva",
            course_name="Curso A",
            course_display_name="Curso Avançado A",
            issued_at=now,
            issued_location="Londrina - PR",
        )
        data = resp.model_dump()
        assert data["token"] == "abc123"
        assert data["contact_name"] == "João Silva"
        assert data["course_name"] == "Curso A"
        assert data["course_display_name"] == "Curso Avançado A"
        assert data["issued_at"] == now
        assert data["issued_location"] == "Londrina - PR"
