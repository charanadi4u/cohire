import os, tempfile
from pathlib import Path
from cryptography.fernet import Fernet
TEST_ROOT=Path(tempfile.mkdtemp(prefix='cohire-test-'))
os.environ.update(DATABASE_URL='sqlite+aiosqlite:///'+str(TEST_ROOT/'domain.db'),IDENTITY_DATABASE_URL='sqlite+aiosqlite:///'+str(TEST_ROOT/'vault.db'),
 DEV_AUTH='true',DEV_TOKEN='synthetic-test-token-123456789012345',IDENTITY_KEY=Fernet.generate_key().decode(),AGENT_MODE='demo',AGENT_TRANSPORT='local',A2A_TOKEN='synthetic-a2a-secret-123456789012345')
import pytest_asyncio
from app.repositories.db import Base,VaultBase,engine,vault_engine
from app.api.main import app
from httpx import AsyncClient,ASGITransport
@pytest_asyncio.fixture(autouse=True)
async def database():
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all);await c.run_sync(Base.metadata.create_all)
    async with vault_engine.begin() as c:
        await c.run_sync(VaultBase.metadata.drop_all);await c.run_sync(VaultBase.metadata.create_all)
    yield
@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test',headers={'Authorization':'Bearer '+os.environ['DEV_TOKEN']}) as c:yield c
