import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database.sql.base import Base


@pytest.fixture(scope="session")
def postgres_container():
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_url(postgres_container):
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def _test_settings():
    from app.core.config import settings

    original_admin_key = settings.ADMIN_API_KEY
    original_guru_key = settings.GURU_API_KEY
    settings.ADMIN_API_KEY = "test-admin-key"
    settings.GURU_API_KEY = ""
    yield
    settings.ADMIN_API_KEY = original_admin_key
    settings.GURU_API_KEY = original_guru_key


@pytest.fixture(scope="session")
def test_app(db_url, _test_settings):
    from app.dependencies import DependencyInjector
    from app.main import create_app

    injector = DependencyInjector(db_url=db_url)
    app = create_app(injector, add_middlewares=False)

    engine = injector.get(Engine)
    Base.metadata.create_all(engine)
    yield app
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def db_engine(test_app, db_url):
    engine = create_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    session = Session(bind=db_engine)
    yield session
    session.close()


@pytest.fixture
def client(test_app):
    from starlette.testclient import TestClient

    with TestClient(test_app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers():
    return {"x-admin-api-key": "test-admin-key"}
