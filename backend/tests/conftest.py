import sys
import asyncio
from unittest.mock import patch, MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture
async def client():
    # Reset the global engine so each test gets a fresh connection in the current loop
    import app.database as db_mod
    db_mod._engine = None
    db_mod._async_session = None

    # Mock Celery dispatch to avoid Redis dependency in tests
    with patch("app.routers.sources._dispatch_analysis") as mock_dispatch, \
         patch("app.routers.admin.collect_single_source_task", create=True) as mock_task, \
         patch("app.routers.admin.collect_public_api_task", create=True) as mock_task2:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    # Clean up engine after test
    engine = db_mod._engine
    if engine:
        await engine.dispose()
    db_mod._engine = None
    db_mod._async_session = None
