import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CourseResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    carga_horaria: int

    model_config = {"from_attributes": True}


class CourseAdminResponse(BaseModel):
    id: uuid.UUID
    guru_product_id: str
    guru_internal_id: str | None
    name: str
    display_name: str | None
    group_id: str | None
    group_name: str | None
    is_active: bool
    carga_horaria: int
    conteudo_programatico: dict | None
    registration_info: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CourseUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    carga_horaria: Optional[int] = None
    conteudo_programatico: Optional[dict] = Field(
        default=None,
        description=(
            "Conteúdo programático do curso em formato JSON. "
            'Deve conter uma lista de módulos, cada um com "name" e "lessons".'
        ),
        json_schema_extra={
            "example": {
                "modules": [
                    {
                        "name": "Módulo Único",
                        "lessons": [
                            "1.1 Aula 1 - Os 5 Passos para Identificar "
                            "Transtornos de Aprendizagem",
                            "1.2 Aula 2 - Entendendo os Transtornos de "
                            "Aprendizagem: Dislexia, Disortografia e "
                            "Discalculia",
                            "1.3 Aula 3 - Quais Estratégias diante das "
                            "Dificuldades e Transtornos Específicos de "
                            "Aprendizagem",
                            "1.4 Certificado",
                        ],
                    }
                ]
            }
        },
    )
    registration_info: Optional[str] = None


class CertificateEmitRequest(BaseModel):
    cpf: str
    course_id: uuid.UUID

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) != 11:
            raise ValueError("CPF deve ter 11 digitos")
        return digits


class CertificateValidationResponse(BaseModel):
    token: str
    contact_name: str
    course_name: str
    course_display_name: str | None
    issued_at: datetime
    issued_location: str | None

    model_config = {"from_attributes": True}
