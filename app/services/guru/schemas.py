from pydantic import BaseModel, Field


class GuruGroup(BaseModel):
    id: str | None = None
    name: str | None = None


class GuruContact(BaseModel):
    id: str
    name: str | None = None
    doc: str | None = None
    email: str | None = None
    address_city: str | None = None
    address_state: str | None = None


class GuruProductRef(BaseModel):
    id: str | None = None
    internal_id: str | None = None
    name: str | None = None
    group: GuruGroup | None = None


class GuruProduct(BaseModel):
    id: str
    internal_id: str | None = None
    marketplace_id: str | None = None
    name: str | None = None
    group: GuruGroup | None = None
    is_active: bool = True


class GuruTransactionDates(BaseModel):
    ordered_at: str | int | None = None


class GuruTransaction(BaseModel):
    id: str
    status: str | None = None
    product: GuruProductRef | None = None
    dates: GuruTransactionDates | None = None
