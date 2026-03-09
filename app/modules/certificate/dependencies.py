from fastapi_injector import request_scope

from app.dependency_registry import registry
from app.modules.certificate.repository import (
    CertificateEmissionRepository,
    CourseRepository,
)
from app.modules.certificate.service import CertificateService

registry.register(CourseRepository, scope=request_scope)
registry.register(CertificateEmissionRepository, scope=request_scope)
registry.register(CertificateService, scope=request_scope)
