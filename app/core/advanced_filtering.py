from typing import Any, Union
from warnings import warn

from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import ValidationInfo, field_validator
from sqlalchemy import Select, cast, or_, not_
from sqlalchemy.dialects.postgresql import operators
from sqlalchemy.orm import Query


def _backward_compatible_value_for_like_and_ilike(value: str):
    """Add % if not in value to be backward compatible.

    Args:
        value (str): The value to filter.

    Returns:
        Either the unmodified value if a percent sign is present, the value wrapped in % otherwise to preserve
        current behavior.
    """
    if "%" not in value:
        # warn(
        #     "You must pass the % character explicitly to use the like and ilike operators.",
        #     DeprecationWarning,
        #     stacklevel=2,
        # )
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
    "like": lambda value: (
        "like",
        _backward_compatible_value_for_like_and_ilike(value),
    ),
    "ilike": lambda value: (
        "ilike",
        _backward_compatible_value_for_like_and_ilike(value),
    ),
    # XXX(arthurio): Mysql excludes None values when using `in` or `not in` filters.
    "not": lambda value: ("is_not", value),
    "not_in": lambda value: ("not_in", value),
    "array_contains": lambda value: (operators.CONTAINS, value),
    "array_not_contains": lambda value: (
        lambda column, casted_value: not_(operators.CONTAINS(column, casted_value)),
        value,
    ),
    "array_overlap": lambda value: (operators.OVERLAP, value),
}


class JoinFilter(Filter):
    def _apply_global_search(self, query: Query | Select, value: Any):
        search_fields = getattr(self.Constants, "search_model_fields", [])
        if not search_fields:
            warn(
                "No search fields defined in the filter. Global search will not be applied.",
                UserWarning,
                stacklevel=2,
            )
            return query

        return self.global_search_query(query, search_fields, value)

    def global_search_query(
        self, query: Query | Select, search_fields: list[str], value: Any
    ):
        search_query = or_(
            *[
                getattr(self.Constants.model, field).ilike(f"%{value}%")
                for field in search_fields
            ]
        )
        return query.filter(search_query)

    @field_validator("*", mode="before")
    def split_str(cls, value, field: ValidationInfo):
        if (
            field.field_name is not None
            and (
                field.field_name == cls.Constants.ordering_field_name
                or field.field_name.endswith("__in")
                or field.field_name.endswith("__not_in")
                or field.field_name.endswith("__array_contains")
                or field.field_name.endswith("__array_not_contains")
                or field.field_name.endswith("__array_overlap")
            )
            and isinstance(value, str)
        ):
            if not value:
                # Empty string should return [] not ['']
                return []
            return list(value.split(","))
        return value

    def filter(self, query: Query | Select):
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)

            if isinstance(field_value, Filter):
                field_value_dump = field_value.model_dump(
                    exclude_unset=True, exclude_none=True
                )
                if (
                    field_value_dump
                    and field_value_dump
                    and any(field_value_dump.values())
                ):
                    joins = getattr(self.Constants, "joins", {})
                    if joins and field_name in joins:
                        join = joins[field_name]
                        join["target"] = join.pop("target", field_value.Constants.model)
                        if hasattr(field_value.Constants, "cte_query_filter"):
                            join["target"] = field_value.Constants.cte_query_filter
                        query = query.join(**join)

                    query = field_value.filter(query)
            else:
                if "__" in field_name:
                    field_name, operator = field_name.split("__")
                    operator, value = _orm_operator_transformer[operator](value)
                else:
                    operator = "__eq__"

                if field_name == self.Constants.search_field_name:
                    query = self._apply_global_search(query, field_value)
                else:
                    model_field = getattr(self.Constants.model, field_name)
                    if isinstance(operator, str):
                        query = query.filter(getattr(model_field, operator)(value))
                    else:
                        query = query.filter(
                            operator(model_field, cast(value, model_field.type))
                        )

        return query


class AdvancedFilter(JoinFilter):
    def sort(self, query: Union[Query, Select]):
        if not self.ordering_values:
            return query
        nulls_last_fields = getattr(self.Constants, "nulls_last_fields", [])
        custom_sort_fields = getattr(self.Constants, "custom_sort_fields", {})

        for field_name in self.ordering_values:
            direction = Filter.Direction.asc
            if field_name.startswith("-"):
                direction = Filter.Direction.desc
            field_name = field_name.replace("-", "").replace("+", "")

            if field_name in custom_sort_fields:
                query = custom_sort_fields[field_name](
                    query=query,
                    direction=direction,
                    field_name=field_name,
                    filter_obj=self,
                )
                continue

            order_by_field = getattr(self.Constants.model, field_name)
            ordering_config = getattr(order_by_field, direction)()
            if field_name in nulls_last_fields:
                ordering_config = ordering_config.nulls_last()

            query = query.order_by(ordering_config)

        return query
