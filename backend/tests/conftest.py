import asyncio
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.base import Base
from backend.app.db.session import engine


@pytest.fixture(scope="session", autouse=True)
def initialize_database():
    """Ensure database schema is created for test sessions."""
    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())
    yield


@pytest.fixture
def client():
    """Provides a TestClient instance for testing FastAPI routes."""
    with TestClient(app) as test_client:
        yield test_client
