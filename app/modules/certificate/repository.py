from typing import Optional

from fastapi_filter.base.filter import BaseFilterModel
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select

from app.modules.certificate.models import CertificateEmission, Course
from app.repositories.sql_repository import SQLAlchemyRepository


class CourseRepository(SQLAlchemyRepository[Course]):
    model = Course

    def get_available_courses(
        self,
        entity_filter: BaseFilterModel | None = None,
        pagination_params: Params | None = None,
    ) -> Page[Course] | list[Course]:
        stmt = select(Course).where(Course.is_active.is_(True))

        if entity_filter:
            stmt = entity_filter.filter(stmt)
            stmt = entity_filter.sort(stmt)

        if pagination_params:
            return paginate(self.db_session, stmt, params=pagination_params)
        return list(self.db_session.scalars(stmt).all())

    def get_by_guru_product_id(self, guru_product_id: str) -> Optional[Course]:
        stmt = select(Course).where(Course.guru_product_id == guru_product_id)
        return self.db_session.scalars(stmt).first()


class CertificateEmissionRepository(SQLAlchemyRepository[CertificateEmission]):
    model = CertificateEmission

    def get_by_token(self, token: str) -> Optional[CertificateEmission]:
        stmt = select(CertificateEmission).where(CertificateEmission.token == token)
        return self.db_session.scalars(stmt).first()
