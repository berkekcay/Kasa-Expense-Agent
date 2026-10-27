import os
import tempfile
from pathlib import Path

# Configure before the app is imported: throwaway SQLite DB, dev auth, and (unless live
# tests were asked for) no LLM provider. Env vars win over any developer .env file.
LIVE = os.environ.get("KASA_LIVE_TESTS") == "1"
_tmp = Path(tempfile.mkdtemp(prefix="kasa-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["FIREBASE_PROJECT_ID"] = ""
os.environ["AUTO_MIGRATE"] = "true"
os.environ["AUTH_MODE"] = "dev"
if not LIVE:
    os.environ["LLM_PROVIDER"] = "gemini"
    os.environ["GOOGLE_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.db.session import init_db, session_for
from app.main import app


def pytest_collection_modifyitems(config, items):
    if LIVE:
        return
    skip = pytest.mark.skip(reason="live LLM test; run with KASA_LIVE_TESTS=1 pytest -m live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    init_db()
    with session_for("test-user") as session:
        yield session
