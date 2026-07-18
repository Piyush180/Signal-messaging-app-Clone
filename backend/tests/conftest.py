"""
Test fixtures.

We point the app at a throwaway SQLite file and create the schema ourselves, so
tests never touch the real `signal.db`. Each test module gets a clean database.
"""
import os
import tempfile

import pytest
import pytest_asyncio

# Configure the environment BEFORE importing the app so settings pick it up.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp.name}"
os.environ["AUTO_INIT_DB"] = "false"
os.environ["SECRET_KEY"] = "test-key"

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register(client: AsyncClient, phone: str, name: str) -> dict:
    """Full request-otp -> verify-otp flow. Returns {token, headers, user}."""
    r = await client.post("/api/v1/auth/request-otp", json={"phone_number": phone})
    code = r.json()["otp_demo"]
    r = await client.post(
        "/api/v1/auth/verify-otp",
        json={"phone_number": phone, "code": code, "full_name": name},
    )
    data = r.json()
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }
