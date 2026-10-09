import os
import tempfile
from pathlib import Path

# Configure before the app is imported: throwaway SQLite DB and no Gemini key
# (env vars win over any developer .env file).
_tmp = Path(tempfile.mkdtemp(prefix="kasa-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["GOOGLE_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import init_db, session_for  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    init_db()
    with session_for("test-user") as session:
        yield session
