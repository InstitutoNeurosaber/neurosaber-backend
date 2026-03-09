import abc
import uuid
from typing import Generic, List, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class BaseRepository(abc.ABC, Generic[T]):
    @abc.abstractmethod
    def get(
        self,
        entity_id: uuid.UUID,
        raise_error: bool | None = True,
        response_model: BaseModel = None,
    ) -> T | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_all(
        self, entity_filter: BaseModel | None = None,
    ) -> List[T]:
        raise NotImplementedError

    @abc.abstractmethod
    def save(self, entity: BaseModel) -> T:
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, entity_id: uuid.UUID, entity: BaseModel) -> T:
        raise NotImplementedError

    @abc.abstractmethod
    def upsert(self, entity: BaseModel, **extra_fields) -> BaseModel:
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, entity_id: uuid.UUID) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def save_many(self, entity_list: List[BaseModel]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def count(self, entity_filter: BaseModel | None = None) -> int:
        raise NotImplementedError