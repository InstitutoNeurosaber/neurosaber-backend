import uuid

import pytest
from sqlalchemy.orm import Session

from app.database.sql.base import DatabaseResource
from app.modules.certificate.models import CertificateEmission, Course
from app.modules.certificate.repository import (
    CertificateEmissionRepository,
    CourseRepository,
)
from app.repositories.exceptions import DuplicateError, NotFoundError
from tests.factories import CertificateEmissionFactory, CourseFactory


class FakeDatabaseResource:
    """Lightweight wrapper to satisfy SQLAlchemyRepository's db parameter."""

    def __init__(self, session: Session):
        self.session = session


@pytest.fixture
def course_repo(db_session):
    return CourseRepository(db=FakeDatabaseResource(db_session))


@pytest.fixture
def emission_repo(db_session):
    return CertificateEmissionRepository(db=FakeDatabaseResource(db_session))


class TestCourseRepository:
    def test_get_available_courses_active_only(self, db_session, course_repo):
        active = CourseFactory.build(is_active=True, guru_product_id="active-1")
        inactive = CourseFactory.build(is_active=False, guru_product_id="inactive-1")
        db_session.add_all([active, inactive])
        db_session.commit()

        courses = course_repo.get_available_courses()

        assert len(courses) == 1
        assert courses[0].guru_product_id == "active-1"

    def test_get_available_courses_empty(self, db_session, course_repo):
        inactive = CourseFactory.build(is_active=False, guru_product_id="inactive-2")
        db_session.add(inactive)
        db_session.commit()

        courses = course_repo.get_available_courses()

        assert courses == []

    def test_get_by_guru_product_id_found(self, db_session, course_repo):
        course = CourseFactory.build(guru_product_id="find-me")
        db_session.add(course)
        db_session.commit()

        result = course_repo.get_by_guru_product_id("find-me")

        assert result is not None
        assert result.guru_product_id == "find-me"

    def test_get_by_guru_product_id_not_found(self, course_repo):
        result = course_repo.get_by_guru_product_id("nonexistent")
        assert result is None

    def test_get_raises_not_found(self, course_repo):
        with pytest.raises(NotFoundError):
            course_repo.get(uuid.uuid4(), raise_error=True)

    def test_get_returns_none_without_raise(self, course_repo):
        result = course_repo.get(uuid.uuid4(), raise_error=False)
        assert result is None

    def test_save_duplicate_guru_product_id(self, db_session, course_repo):
        course1 = CourseFactory.build(guru_product_id="dup-prod")
        db_session.add(course1)
        db_session.commit()

        from pydantic import BaseModel

        class CourseCreate(BaseModel):
            guru_product_id: str = "dup-prod"
            name: str = "Duplicate"
            carga_horaria: int = 10

            model_config = {"from_attributes": True}

        with pytest.raises(DuplicateError):
            course_repo.save(CourseCreate())


class TestCertificateEmissionRepository:
    def test_get_by_token_found(self, db_session, emission_repo):
        course = CourseFactory.build(guru_product_id="emission-course")
        db_session.add(course)
        db_session.flush()

        emission = CertificateEmissionFactory.build(
            course_id=course.id, token="find-this-token"
        )
        db_session.add(emission)
        db_session.commit()

        result = emission_repo.get_by_token("find-this-token")

        assert result is not None
        assert result.token == "find-this-token"

    def test_get_by_token_not_found(self, emission_repo):
        result = emission_repo.get_by_token("nonexistent-token")
        assert result is None
