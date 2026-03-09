import secrets
import uuid
from datetime import UTC, datetime

import factory

from app.modules.certificate.models import CertificateEmission, Course


class CourseFactory(factory.Factory):
    class Meta:
        model = Course

    id = factory.LazyFunction(uuid.uuid4)
    guru_product_id = factory.Sequence(lambda n: f"guru-prod-{n}")
    guru_internal_id = factory.Sequence(lambda n: f"guru-int-{n}")
    name = factory.Sequence(lambda n: f"Curso de Teste {n}")
    display_name = factory.LazyAttribute(lambda o: o.name)
    group_id = None
    group_name = None
    is_active = True
    carga_horaria = 40
    conteudo_programatico = factory.LazyFunction(
        lambda: {
            "modules": [
                {
                    "name": "Módulo 1",
                    "lessons": [
                        "1.1 Introdução ao tema",
                        "1.2 Desenvolvimento prático",
                    ],
                }
            ]
        }
    )
    registration_info = None
    created_at = factory.LazyFunction(lambda: datetime.now(tz=UTC))
    updated_at = factory.LazyFunction(lambda: datetime.now(tz=UTC))


class CertificateEmissionFactory(factory.Factory):
    class Meta:
        model = CertificateEmission

    id = factory.LazyFunction(uuid.uuid4)
    token = factory.LazyFunction(lambda: secrets.token_urlsafe(12))
    contact_name = factory.Sequence(lambda n: f"Aluno Teste {n}")
    contact_cpf = factory.Sequence(lambda n: f"123.456.{str(n).zfill(3)}-00")
    contact_email = factory.Sequence(lambda n: f"aluno{n}@teste.com")
    course_id = factory.LazyFunction(uuid.uuid4)
    guru_transaction_id = factory.Sequence(lambda n: f"tx-{n}")
    issued_at = factory.LazyFunction(lambda: datetime.now(tz=UTC))
    issued_location = "São Paulo - SP"
    created_at = factory.LazyFunction(lambda: datetime.now(tz=UTC))
    updated_at = factory.LazyFunction(lambda: datetime.now(tz=UTC))
