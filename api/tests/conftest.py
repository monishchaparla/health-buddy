import os

import pytest

# Tests never call Gemini: an empty key wins over api/.env (load_dotenv doesn't override), so parsing uses rules.
os.environ["GEMINI_API_KEY"] = ""
os.environ["TEJU_COOKIE_INSECURE"] = "1"  # TestClient talks plain http


@pytest.fixture(autouse=True, scope="session")
def foods_db():
    from teju import foods, foods_build
    if not foods.FOODS_JSON.exists():
        foods_build.build()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TEJU_DB", str(tmp_path / "test.db"))
    from fastapi.testclient import TestClient

    from teju import auth
    from teju.api import app
    auth._failures.clear()
    with TestClient(app) as c:
        yield c


def signup(client, email="asha@example.com", password="correct-horse-1", **kw):
    body = {"email": email, "password": password, "name": "Asha", "consent": True, **kw}
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 201, r.text
    return r
