import importlib

import pytest

from croquimaker.auth import AuthStore
from croquimaker.project_store import ProjectStore


TEST_PASSWORD = "TesteSeguro!2026"


@pytest.fixture
def app_module_with_auth(tmp_path, monkeypatch):
    app_module = importlib.import_module("croquimaker.app")
    store = AuthStore(
        tmp_path / "auth" / "auth.db",
        tmp_path / "auth" / "initial-credentials.txt",
    )
    store.initialize(bootstrap_password=TEST_PASSWORD)
    project_store = ProjectStore(tmp_path / "operations.db")
    project_store.initialize()
    monkeypatch.setattr(app_module, "auth_store", store)
    monkeypatch.setattr(app_module, "project_store", project_store)
    monkeypatch.setattr(app_module, "PROJECTS_DIR", tmp_path / "projects")
    app_module.jobs.clear()
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    yield app_module
    app_module.jobs.clear()


@pytest.fixture
def login_client():
    def login(client, username="caxias1", password=TEST_PASSWORD):
        response = client.get("/login")
        assert response.status_code == 200
        with client.session_transaction() as browser_session:
            token = browser_session["_csrf_token"]
        response = client.post(
            "/login",
            data={
                "_csrf_token": token,
                "username": username,
                "password": password,
            },
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")
        return token

    return login
