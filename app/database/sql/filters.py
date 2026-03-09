from typing import Type, TypeVar, Union, List
from pydantic import BaseModel, ValidationInfo, field_validator
from sqlalchemy import Select, cast, or_
from sqlalchemy.dialects.postgresql import operators
from sqlalchemy.orm import Query, DeclarativeBase

T = TypeVar('T', bound=BaseModel)


def _backward_compatible_value_for_like_and_ilike(value: str):
    """Add % if not in value to be backward compatible."""
    if "%" not in value:
        value = f"%{value}%"
    return value


_orm_operator_transformer = {
    "neq": lambda value: ("__ne__", value),
    "gt": lambda value: ("__gt__", value),
    "gte": lambda value: ("__ge__", value),
    "in": lambda value: ("in_", value),
    "isnull": lambda value: ("is_", None) if value is True else ("is_not", None),
    "lt": lambda value: ("__lt__", value),
    "lte": lambda value: ("__le__", value),
    "like": lambda value: ("like", _backward_compatible_value_for_like_and_ilike(value)),
    "ilike": lambda value: ("ilike", _backward_compatible_value_for_like_and_ilike(value)),
    "not": lambda value: ("is_not", value),
    "not_in": lambda value: ("not_in", value),
    "array_contains": lambda value: (operators.CONTAINS, value),
    "array_overlap": lambda value: (operators.OVERLAP, value),
}


class FilterConstants:
    """Clase base para las constantes de los filtros"""
    model: Type[DeclarativeBase]
    search_model_fields: List[str] = []
    ordering_field_name: str = "order_by"
    search_field_name: str = "search"
    nulls_last_fields: List[str] = []
    joins: dict = {}


class BaseFilter(BaseModel):
    """Clase base para todos los filtros de repositorio"""

    class Constants(FilterConstants):
        pass

    @field_validator("*", mode="before")
    def split_str(cls, value, field: ValidationInfo):
        if (
            field.field_name is not None

            and (
                field.field_name == cls.Constants.ordering_field_name
                or field.field_name.endswith("__in")
                or field.field_name.endswith("__not_in")
                or field.field_name.endswith("__array_contains")
                or field.field_name.endswith("__array_overlap")
            )
            and isinstance(value, str)
        ):
            if not value:
                return []
            return list(value.split(","))
        return value

    @property
    def filtering_fields(self):
        """Obtiene los campos de filtrado con sus valores"""
        return [
            (field_name, value)
            for field_name, value in self.model_dump(exclude_none=True).items()
            if value is not None and field_name != self.Constants.ordering_field_name
        ]

    def filter(self, query: Union[Query, Select]) -> Union[Query, Select]:
        """Aplica los filtros al query"""
        for field_name, value in self.filtering_fields:
            if isinstance(value, BaseFilter):
                field_value_dump = value.model_dump(
                    exclude_unset=True, exclude_none=True)
                if field_value_dump and any(field_value_dump.values()):
                    joins = getattr(self.Constants, "joins", {})
                    if joins and field_name in joins:
                        join = joins[field_name]
                        join["target"] = join.pop(
                            "target", value.Constants.model)
                        if hasattr(value.Constants, "cte_query_filter"):
                            join["target"] = value.Constants.cte_query_filter
                        query = query.join(**join)
                    query = value.filter(query)
            else:
                if "__" in field_name:
                    field_name, operator = field_name.split("__")
                    operator, value = _orm_operator_transformer[operator](
                        value)
                else:
                    operator = "__eq__"

                if field_name == self.Constants.search_field_name and hasattr(
                    self.Constants, "search_model_fields"
                ):
                    search_filters = [
                        getattr(self.Constants.model,
                                field).ilike(f"%{value}%")
                        for field in self.Constants.search_model_fields
                    ]
                    query = query.filter(or_(*search_filters))
                else:
                    model_field = getattr(self.Constants.model, field_name)
                    if isinstance(operator, str):
                        query = query.filter(
                            getattr(model_field, operator)(value))
                    else:
                        query = query.filter(
                            operator(model_field, cast(value, model_field.type)))

        return query

    def sort(self, query: Union[Query, Select]) -> Union[Query, Select]:
        """Aplica ordenamiento al query"""
        if not hasattr(self, self.Constants.ordering_field_name):
            return query

        ordering_values = getattr(self, self.Constants.ordering_field_name)
        if not ordering_values:
            return query

        nulls_last_fields = getattr(self.Constants, "nulls_last_fields", [])

        for field_name in ordering_values:
            direction = "asc"
            if field_name.startswith("-"):
                direction = "desc"
            field_name = field_name.replace("-", "").replace("+", "")

            order_by_field = getattr(self.Constants.model, field_name)
            ordering_config = getattr(order_by_field, direction)()
            if field_name in nulls_last_fields:
                ordering_config = ordering_config.nulls_last()
            query = query.order_by(ordering_config)

        return query
