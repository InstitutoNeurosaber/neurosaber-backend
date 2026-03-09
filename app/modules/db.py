from sqlalchemy.orm import load_only


def select_from_pydantic(model, pydantic_model):
    fields = pydantic_model.model_fields.keys()
    columns = []
    for field_name in fields:
        if hasattr(model, field_name):
            columns.append(getattr(model, field_name))
    if columns:
        return [load_only(*columns)]
    return []
