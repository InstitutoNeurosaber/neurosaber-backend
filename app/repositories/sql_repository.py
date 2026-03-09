import logging
import uuid
from datetime import UTC, datetime
from functools import wraps
from typing import Dict, List, Type, TypeVar

import psycopg2
import sqlalchemy
from fastapi_filter.base.filter import BaseFilterModel
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from injector import Inject
from pydantic import BaseModel
from sqlalchemy import Selectable, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.database.sql.base import Base, DatabaseResource
from app.modules.db import select_from_pydantic
from app.repositories.base_repository import BaseRepository
from app.repositories.clauses import (
    OnConflictClause,
    do_default_on_conflict,
    bulk_operation_context,
)
from app.repositories.exceptions import DuplicateError, NotFoundError, ReferencedError

T = TypeVar("T", bound=Base)

logger = logging.getLogger(__name__)


class SQLAlchemyRepository(BaseRepository[T]):
    model: Type[T]

    def __init__(self, db: Inject[DatabaseResource]) -> None:
        self.db_session = db.session

    def _generate_select_from_pydantic(
        self, pydantic_model: BaseModel, query: Selectable | None = None
    ) -> select:
        options = select_from_pydantic(self.model, pydantic_model)

        return (
            query.options(*options)
            if query is not None
            else select(self.model).options(*options)
        )

    def _base_query(self, **kwargs):
        return select(self.model)

    def __add_updates_metadata(self, updated_values: Dict) -> BaseModel:
        # This method might be deprecated in favor of the _add_instance_updates_metadata method
        # But it's still worth keeping it for now because it works with SQL statements without ORM
        if update_expression := getattr(self.model, "updates_metadata", None):
            for key in updated_values.keys():
                # Use func.jsonb_set to create the JSONB update expression
                update_expression = func.jsonb_set(
                    update_expression,
                    f"{{{key}}}",
                    f'"{datetime.now(tz=UTC).isoformat()}"',
                )

            updated_values.update({"updates_metadata": update_expression})
            return updated_values

    def handle_commit_errors(func):
        @wraps(func)
        def exception_wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except sqlalchemy.exc.IntegrityError as e:
                self.db_session.rollback()
                match e.orig:
                    case psycopg2.errors.UniqueViolation():
                        raise DuplicateError.from_db_string(
                            e.orig.pgerror, self.model
                        ) from e
                    # Add more cases for other possible exceptions if needed
                    case psycopg2.errors.ForeignKeyViolation():
                        if "is still referenced from table" in e.orig.pgerror:
                            raise ReferencedError(
                                detail=f"{self.model._display_name()} is being referenced by another table"
                            ) from e

                        if "violates foreign key constraint" in e.orig.pgerror:
                            raise ReferencedError(
                                detail=e.orig.pgerror.split(":")[-1].strip()
                            ) from e
                        raise e
                    case _:
                        raise e
            except (sqlalchemy.exc.SQLAlchemyError, psycopg2.Error) as e:
                # This prevents "current transaction is aborted" errors
                logger.warning(f"SQL error in {func.__name__}: {str(e)}, rolling back transaction")
                self.db_session.rollback()
                raise e
            except Exception as e:
                logger.warning(f"Unexpected error in {func.__name__}: {str(e)}, rolling back transaction as safety measure")
                self.db_session.rollback()
                raise e

        return exception_wrapper

    def get(
        self,
        entity_id: uuid.UUID | str,
        raise_error: bool | None = True,
        filter_field: str = "id",
        response_model: BaseModel = None,
    ) -> T | None:
        if not (filter_model_field := getattr(self.model, filter_field, None)):
            raise AttributeError(
                f"Field '{filter_field}' not found in {self.model._display_name()}"
            )
        query = select(self.model)
        if response_model:
            query = self._generate_select_from_pydantic(response_model)

        item = self.db_session.execute(
            query.where(filter_model_field == entity_id)
        ).scalar()

        if item is None and raise_error:
            raise NotFoundError(
                detail=f"{self.model._display_name()} {entity_id} not found"
            )
        return item

    def get_all(
        self,
        entity_filter: BaseFilterModel | None = None,
        pagination_params: Params | None = None,
        base_query: Selectable | None = None,
        return_scalars: bool = True,
        response_model: BaseModel | None = None,
        pagination_kwargs: Dict | None = None,
        **kwargs,
    ) -> Page[T] | List[T]:
        query = base_query if base_query is not None else self._base_query(**kwargs)
        if response_model:
            query = self._generate_select_from_pydantic(response_model, query)
        if entity_filter:
            query = entity_filter.filter(query)
            try:
                query = entity_filter.sort(query)
            except AttributeError:
                pass

        if pagination_params:
            return paginate(
                self.db_session,
                query,
                params=pagination_params,
                **(pagination_kwargs or {}),
            )

        if return_scalars:
            return self.db_session.scalars(query).unique().all()
        return self.db_session.execute(query).all()

    def _convert_m2m_relationships(self, entity):
        for rel in self.model.__mapper__.relationships:
            attr_val = getattr(entity, rel.key, None)
            if isinstance(attr_val, list) and any(
                isinstance(val, uuid.UUID) for val in attr_val
            ):
                values = self._uuid_to_entity(attr_val, rel)
                setattr(entity, rel.key, values)

    def _uuid_to_entity(self, attr_val, relationship):
        values = []
        uuids = set()

        for val in attr_val:
            if isinstance(val, uuid.UUID):
                uuids.add(val)
            else:
                values.append(val)

        if uuids:
            related_model = relationship.mapper.class_
            converted = (
                self.db_session.query(related_model)
                .filter(related_model.id.in_(uuids))
                .all()
            )

            # Throw errors for the UUIDs that were not found
            if len(uuids) != len(converted):
                missing_uuids = set(uuids) - {val.id for val in converted}
                raise ReferencedError(
                    detail=f"Foreign key violation: {relationship.key} with UUIDs {missing_uuids} not found"
                )

            values.extend(converted)
        return values

    @handle_commit_errors
    def save(self, entity: BaseModel, **extra_fields) -> BaseModel:
        new_entity = self.model(**{**entity.model_dump(), **extra_fields})
        self._convert_m2m_relationships(new_entity)

        self.db_session.add(new_entity)
        self.db_session.commit()
        self.db_session.refresh(new_entity)
        return new_entity

    @handle_commit_errors
    def upsert(self, entity: BaseModel, **extra_fields) -> T:
        new_entity = (
            self.model(**{**entity.model_dump(), **extra_fields})
            if not isinstance(entity, self.model)
            else entity
        )

        persisted_entity = self.db_session.merge(new_entity)
        self.db_session.commit()
        self.db_session.refresh(persisted_entity)
        return persisted_entity

    @handle_commit_errors
    def update(self, entity_id: uuid.UUID, updated_entity: BaseModel) -> T:
        # Create a new instance of the model to update it
        instance = self.get(entity_id)
        self._convert_m2m_relationships(updated_entity)
        self._merge(instance, updated_entity)
        self.db_session.commit()
        return instance

    def bulk_update(
        self,
        values: BaseModel,
        *,
        where: BaseFilterModel | None = None,
    ) -> None:
        update_values = values.model_dump(exclude_unset=True)

        stmt = update(self.model).values(update_values)

        if where:
            stmt = where.filter(stmt)

        self.db_session.execute(stmt)
        self.db_session.commit()

    @handle_commit_errors
    def delete(self, entity_id: uuid.UUID) -> None:
        self.db_session.execute(delete(self.model).where(self.model.id == entity_id))
        self.db_session.commit()

    @handle_commit_errors
    def delete_by_filter(self, filter_query: BaseFilterModel) -> None:
        query = filter_query.filter(delete(self.model))
        self.db_session.execute(query)
        self.db_session.commit()

    @handle_commit_errors
    def save_many(self, entity_list: List[BaseModel]) -> List[T]:
        new_entities = [self.model(**entity.model_dump()) for entity in entity_list]
        self.db_session.add_all(new_entities)
        self.db_session.commit()

        return new_entities

    @handle_commit_errors
    def delete_many(self, delete_filter_query: Selectable) -> None:
        self.db_session.execute(delete_filter_query)
        self.db_session.commit()

    @handle_commit_errors
    def bulk_create(
        self,
        entities: list[T],
        on_conflict: OnConflictClause = do_default_on_conflict,
    ) -> None:
        entities_dict = [
            entity.model_dump() if isinstance(entity, BaseModel) else entity
            for entity in entities
        ]
        if not entities_dict:
            logger.warning("No entities to bulk create")
            return

        with bulk_operation_context(self.db_session):
            stmt = insert(self.model).values(entities_dict)
            stmt = on_conflict(stmt)
            try:
                res = self.db_session.execute(stmt.returning(self.model))
            except NotImplementedError:
                ## Sometimes we get this error when using the returning clause self.model produced by some column_properties
                res = self.db_session.execute(stmt.returning("*"))

            self.db_session.commit()
            return res.unique().scalars().all()

    def count(self, entity_filter: BaseFilterModel | None = None) -> int:
        query = self._base_query()
        if entity_filter:
            query = entity_filter.filter(query)
        return self.db_session.execute(select(func.count()).select_from(query)).scalar()

    def _add_instance_updates_metadata(self, instance: T, update: dict | None) -> T:
        if update is None:
            return instance

        if hasattr(instance, "updates_metadata"):
            updated_keys = {
                key: datetime.now(tz=UTC).isoformat() for key in update.keys()
            }
            instance.updates_metadata = {
                **instance.updates_metadata,
                **updated_keys,
            }

        return instance

    def _merge(self, instance: T, update: BaseModel | dict | None) -> T:
        if update is None:
            return instance

        if not isinstance(update, dict):
            update = update.model_dump(exclude_unset=True)

        instance = self._add_instance_updates_metadata(instance, update)

        for key, value in update.items():
            try:
                # If the key is a relationship, merge the relationship
                # If it's an M2M relationship, convert the UUIDs to entities
                if key in instance.__mapper__.relationships:
                    if isinstance(value, list):
                        value = self._uuid_to_entity(
                            update[key], instance.__mapper__.relationships.get(key)
                        )
                    else:
                        return self._merge(getattr(instance, key), value)

                setattr(instance, key, value)
            except AttributeError as e:
                raise AttributeError(
                    f"Attribute {key} not found in {self.model._display_name()}"
                ) from e
        return instance
