import json
import time

import structlog
from injector import Inject
from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker
from sqlalchemy.pool import NullPool

from app.context import get_request_context, req_or_thread_id
from app.core.config import settings

logger = structlog.get_logger(__name__)

meta = MetaData(
    naming_convention={
        "ix": "%(column_0_label)s_idx",
        "uq": "%(table_name)s_%(column_0_name)s_key",
        "ck": "%(table_name)s_%(constraint_name)s_check",
        "fk": "%(table_name)s_%(column_0_name)s_%(referred_table_name)s_fkey",
        "pk": "%(table_name)s_pkey",
    }
)


class Base(DeclarativeBase):
    metadata = meta

    @classmethod
    def _display_name(self):
        return self.__tablename__.capitalize()


def _dump_sqlalchemy_query(statement):
    return str(statement).replace("\n", "\\n")


def create_sqlalchemy_engine(*, db_url: str) -> Engine:
    connect_args = {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "connect_timeout": 10,
    }

    if settings.DB_USE_NULLPOOL:
        engine = create_engine(
            db_url,
            poolclass=NullPool,
            echo=settings.DEBUG_MODE,
            connect_args=connect_args,
        )
    else:
        engine = create_engine(
            db_url,
            pool_pre_ping=settings.DB_POOL_PRE_PING,
            pool_recycle=settings.POOL_RECYCLE_MINUTES * 60,
            echo=settings.DEBUG_MODE,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=30,
            connect_args=connect_args,
        )

    @event.listens_for(engine, "before_cursor_execute")
    def _before_execute(conn, cursor, statement, parameters, context, executemany):
        context._query_start_time = time.time()

    @event.listens_for(engine, "after_cursor_execute")
    def _after_execute(conn, cursor, statement, parameters, context, executemany):
        elapsed_ms = (time.time() - context._query_start_time) * 1000
        if elapsed_ms > 500:
            logger.warning(
                "slow_query",
                elapsed_ms=elapsed_ms,
                query=_dump_sqlalchemy_query(statement),
                parameters=parameters,
            )

    return engine


# class DBSession(Session):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # self.admin_db_role = admin_db_role

#     def _set_admin_role(self):
#         """
#         Enables the admin role for the session. This disables access control and RLS.

#         Intended for use in the admin API and other privileged operations.
#         """
#         # self.execute(text("SET LOCAL ROLE :role;").bindparams(role=self.admin_db_role))

#     def _configure_mass_update_session(self) -> None:
#         """
#         Configure the session for mass update operations.
#         This method is called before executing a mass update query.
#         """

#         self.expire_on_commit = False

#         sql = text(
#             """
#         SET LOCAL work_mem = '300MB';
#         SET LOCAL statement_timeout = '1h';
#         SET LOCAL lock_timeout = '10s';
#             """
#         )

#         self._set_admin_role()
#         self.execute(sql)


class DatabaseResource:
    """Class to handle database connections and sessions"""

    def __init__(
        self,
        engine: Inject[Engine],
        # admin_db_role: str = settings.DB_ADMIN_ROLE,
        # auth_db_role: str = settings.DB_AUTH_ROLE,
    ):
        self.engine = engine
        # self.admin_db_role = admin_db_role
        # self.auth_db_role = auth_db_role

        factory = sessionmaker(
            bind=self.engine,
            # class_=EchoDBSession,
            autocommit=False,
            autoflush=False,
            # admin_db_role=self.admin_db_role,
        )

        self.session_factory = scoped_session(
            factory,
            scopefunc=req_or_thread_id,
        )
        self.session = self.session_factory

        # self._add_session_event_listener()

    # def _add_session_event_listener(self):
    #     """Attach a listener to run SQL when a session starts"""

    #     @event.listens_for(self.session_factory, "after_begin")
    #     def set_custom_config(session, transaction, connection):
    #         req_ctx = get_request_context()

    #         # db_role = self.admin_db_role
    #         # if settings.ENABLE_ACCESS_CONTROL and req_ctx.authenticated:
    #         #     db_role = self.auth_db_role

    #         custom_sql = text(
    #             """
    #             SELECT set_config(
    #                 'request.jwt.claims',
    #                 :jwt,
    #                 true
    #             );

    #             SET LOCAL statement_timeout=:timeout;

    #             SET LOCAL ROLE :role;
    #         """
    #         ).bindparams(
    #             jwt=json.dumps(req_ctx.jwt),
    #             # role=db_role,
    #             timeout=settings.DB_STATEMENT_TIMEOUT_MS,
    #         )

    #         connection.execute(custom_sql)

    #         if req_ctx.user_id:
    #             connection.execute(
    #                 text("SET LOCAL request.user_id = :user_id;").bindparams(
    #                     user_id=req_ctx.user_id
    #                 )
    #             )

    def create_database(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_database(self):
        Base.metadata.drop_all(self.engine)

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_value, traceback):
        if traceback:
            self.session.rollback()
        self.session.remove()
