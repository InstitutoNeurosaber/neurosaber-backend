import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.sql.base import Base
from tests.factories import CertificateEmissionFactory, CourseFactory


@pytest.fixture(autouse=True)
def _cleanup_db(db_engine):
    yield
    with Session(bind=db_engine) as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
        session.commit()


@pytest.fixture
def seed_courses(db_session):
    courses = [
        CourseFactory.build(is_active=True, guru_product_id=f"active-prod-{i}")
        for i in range(3)
    ]
    inactive = CourseFactory.build(
        is_active=False, guru_product_id="inactive-prod-0"
    )
    all_courses = courses + [inactive]
    for c in all_courses:
        db_session.add(c)
    db_session.commit()
    for c in all_courses:
        db_session.refresh(c)
    return {"active": courses, "inactive": [inactive]}


@pytest.fixture
def seed_emissions(db_session, seed_courses):
    course = seed_courses["active"][0]
    emissions = [
        CertificateEmissionFactory.build(
            course_id=course.id,
            token=f"valid-token-{i}",
        )
        for i in range(2)
    ]
    for e in emissions:
        db_session.add(e)
    db_session.commit()
    for e in emissions:
        db_session.refresh(e)
    return emissions
