from typing import Optional

from app.core.advanced_filtering import AdvancedFilter
from app.modules.certificate.models import Course


class CourseFilter(AdvancedFilter):
    search: Optional[str] = None
    name__ilike: Optional[str] = None
    order_by: Optional[list[str]] = None

    class Constants(AdvancedFilter.Constants):
        model = Course
        search_field_name = "search"
        search_model_fields = ["name", "display_name"]
        ordering_field_name = "order_by"


class CourseAdminFilter(AdvancedFilter):
    search: Optional[str] = None
    name__ilike: Optional[str] = None
    is_active: Optional[bool] = None
    group_name__ilike: Optional[str] = None
    group_id: Optional[str] = None
    carga_horaria__gte: Optional[int] = None
    carga_horaria__lte: Optional[int] = None
    order_by: Optional[list[str]] = None

    class Constants(AdvancedFilter.Constants):
        model = Course
        search_field_name = "search"
        search_model_fields = ["name", "display_name", "group_name"]
        ordering_field_name = "order_by"
