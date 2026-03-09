import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.guru.schemas import (
    GuruContact,
    GuruProduct,
    GuruGroup,
    GuruProductRef,
    GuruTransaction,
)
from tests.factories import CourseFactory, CertificateEmissionFactory


class TestHealthCheck:
    def test_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200


class TestListCourses:
    def test_empty(self, client):
        response = client.get("/api/courses")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_returns_active_courses(self, client, seed_courses):
        response = client.get("/api/courses")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_excludes_inactive_courses(self, client, seed_courses):
        response = client.get("/api/courses")
        data = response.json()
        assert data["total"] == 3
        returned_ids = {item["id"] for item in data["items"]}
        inactive_ids = {str(c.id) for c in seed_courses["inactive"]}
        assert returned_ids.isdisjoint(inactive_ids)


class TestEmitCertificate:
    @patch("app.modules.certificate.service.generate_certificate_pdf")
    @patch("app.modules.certificate.service.GuruClient")
    def test_success(self, mock_guru_cls, mock_pdf, client, seed_courses):
        mock_pdf.return_value = b"%PDF-fake-certificate"
        mock_guru = MagicMock()
        mock_guru_cls.return_value = mock_guru

        course = seed_courses["active"][0]
        mock_guru.find_contact_by_cpf.return_value = GuruContact(
            id="c1",
            name="Aluno Teste",
            doc="12345678901",
            email="aluno@test.com",
            address_city="SP",
            address_state="SP",
        )
        mock_guru.get_transactions_for_contact.return_value = [
            GuruTransaction(
                id="tx-1",
                status="approved",
                product=GuruProductRef(id=course.guru_product_id),
            )
        ]

        response = client.post(
            "/api/certificates/emit",
            json={"cpf": "12345678901", "course_id": str(course.id)},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert b"%PDF-fake-certificate" in response.content

    def test_invalid_cpf(self, client):
        response = client.post(
            "/api/certificates/emit",
            json={"cpf": "123", "course_id": str(uuid.uuid4())},
        )
        assert response.status_code == 422

    @patch("app.modules.certificate.service.GuruClient")
    def test_course_not_found(self, mock_guru_cls, client):
        response = client.post(
            "/api/certificates/emit",
            json={"cpf": "12345678901", "course_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404


class TestValidateCertificate:
    def test_success(self, client, seed_emissions):
        emission = seed_emissions[0]
        response = client.get(f"/api/certificates/validate/{emission.token}")
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == emission.token
        assert data["contact_name"] == emission.contact_name

    def test_not_found(self, client):
        response = client.get("/api/certificates/validate/nonexistent-token")
        assert response.status_code == 404


class TestAdminEndpoints:
    def test_list_courses_unauthorized(self, client):
        response = client.get("/api/admin/courses")
        assert response.status_code == 401

    def test_list_courses_success(self, client, admin_headers, seed_courses):
        response = client.get("/api/admin/courses", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4  # 3 active + 1 inactive

    def test_update_course(self, client, admin_headers, seed_courses):
        course = seed_courses["active"][0]
        response = client.patch(
            f"/api/admin/courses/{course.id}",
            headers=admin_headers,
            json={"carga_horaria": 100, "display_name": "Nome Atualizado"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["carga_horaria"] == 100
        assert data["display_name"] == "Nome Atualizado"

    def test_update_course_not_found(self, client, admin_headers):
        response = client.patch(
            f"/api/admin/courses/{uuid.uuid4()}",
            headers=admin_headers,
            json={"carga_horaria": 50},
        )
        assert response.status_code == 404

    @patch("app.modules.certificate.service.GuruClient")
    def test_sync_courses(self, mock_guru_cls, client, admin_headers):
        mock_guru = MagicMock()
        mock_guru_cls.return_value = mock_guru
        mock_guru.get_ingresso_products.return_value = [
            GuruProduct(
                id="sync-prod-1",
                internal_id="sync-int-1",
                name="Synced Course",
                group=GuruGroup(id="g1", name="Ingressos"),
            )
        ]

        response = client.post("/api/admin/sync-courses", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["synced"] == 1
