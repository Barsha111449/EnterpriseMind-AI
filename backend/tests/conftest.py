from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

import backend.app.models  # noqa: F401
from backend.app.core.config import settings
from backend.app.database.base import Base
from backend.app.database.session import get_db
from backend.app.main import app


test_database_url = URL.create(
    drivername="postgresql+pg8000",
    username=settings.postgres_user,
    password=settings.postgres_password,
    host=settings.postgres_host,
    port=settings.postgres_port,
    database="enterprisemind_test",
)

test_engine = create_engine(
    test_database_url,
    pool_pre_ping=True,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database() -> Generator[None, None, None]:
    """Create the test tables before testing and remove them afterward."""

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def clean_test_database() -> Generator[None, None, None]:
    """Delete all records before every test."""

    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    yield


@pytest.fixture
def database_session() -> Generator[Session, None, None]:
    """Provide a session for checking database records."""

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Make FastAPI use the testing database."""

    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()

        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()