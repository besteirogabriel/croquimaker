import io
import json
import stat

import fitz

from croquimaker.auth import AuthStore


class CapturingQueue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Projeto teste")
    content = document.tobytes()
    document.close()
    return content


def _csrf(client) -> str:
    with client.session_transaction() as browser_session:
        return browser_session["_csrf_token"]


def _upload(client, token):
    return client.post(
        "/api/projetos",
        data={"arquivo": (io.BytesIO(_pdf_bytes()), "projeto.pdf")},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )


def test_bootstrap_cria_oito_usuarios_com_perfis_corretos(tmp_path):
    credentials = tmp_path / "auth" / "initial-credentials.txt"
    store = AuthStore(tmp_path / "auth" / "auth.db", credentials)

    assert store.initialize(bootstrap_password="SenhaInicial!2026")
    users = store.list_users()

    assert len(users) == 8
    assert sum(user["role"] == "admin" for user in users) == 4
    assert sum(user["project_slug"] == "caxias" for user in users) == 2
    assert sum(user["project_slug"] == "vacaria" for user in users) == 2
    assert stat.S_IMODE(credentials.stat().st_mode) == 0o600


def test_rotas_protegidas_exigem_login(app_module_with_auth):
    client = app_module_with_auth.app.test_client()

    page = client.get("/")
    api = client.get("/api/projetos/inexistente")

    assert page.status_code == 302
    assert page.headers["Location"].endswith("/login")
    assert api.status_code == 401


def test_usuario_caxias_grava_somente_no_projeto_caxias(
    app_module_with_auth,
    login_client,
    monkeypatch,
):
    queue = CapturingQueue()
    monkeypatch.setattr(app_module_with_auth, "work_q", queue)
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")

    response = _upload(client, _csrf(client))

    assert response.status_code == 202
    body = response.get_json()
    job_id = body["job_id"]
    assert body["project"] == "caxias"
    assert queue.items == [f"caxias:{job_id}"]
    status_path = (
        app_module_with_auth.PROJECTS_DIR
        / "caxias"
        / "jobs"
        / job_id
        / "status.json"
    )
    assert status_path.exists()
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["project_slug"] == "caxias"
    assert status["created_by"] == "caxias1"
    assert not (
        app_module_with_auth.PROJECTS_DIR / "vacaria" / "jobs" / job_id
    ).exists()


def test_usuario_vacaria_nao_acessa_job_de_caxias(
    app_module_with_auth,
    login_client,
    monkeypatch,
):
    queue = CapturingQueue()
    monkeypatch.setattr(app_module_with_auth, "work_q", queue)
    caxias_client = app_module_with_auth.app.test_client()
    login_client(caxias_client, "caxias1")
    created = _upload(caxias_client, _csrf(caxias_client))
    job_id = created.get_json()["job_id"]

    vacaria_client = app_module_with_auth.app.test_client()
    login_client(vacaria_client, "vacaria1")
    response = vacaria_client.get(f"/api/projetos/{job_id}")

    assert response.status_code == 404


def test_id_de_job_nao_permite_navegacao_de_diretorio(
    app_module_with_auth,
    login_client,
):
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")

    response = client.get("/api/projetos/..")

    assert response.status_code == 404


def test_admin_pode_trocar_para_vacaria_e_upload_respeita_selecao(
    app_module_with_auth,
    login_client,
    monkeypatch,
):
    queue = CapturingQueue()
    monkeypatch.setattr(app_module_with_auth, "work_q", queue)
    client = app_module_with_auth.app.test_client()
    login_client(client, "admin1")

    page = client.get("/")
    assert page.status_code == 200
    assert 'name="project_slug"' in page.get_data(as_text=True)

    selected = client.post(
        "/projeto-ativo",
        data={"_csrf_token": _csrf(client), "project_slug": "vacaria"},
    )
    assert selected.status_code == 302
    created = _upload(client, _csrf(client))

    assert created.status_code == 202
    body = created.get_json()
    assert body["project"] == "vacaria"
    assert (
        app_module_with_auth.PROJECTS_DIR
        / "vacaria"
        / "jobs"
        / body["job_id"]
        / "status.json"
    ).exists()


def test_usuario_regional_nao_pode_trocar_projeto(
    app_module_with_auth,
    login_client,
):
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")

    page = client.get("/")
    assert 'name="project_slug"' not in page.get_data(as_text=True)
    response = client.post(
        "/projeto-ativo",
        data={"_csrf_token": _csrf(client), "project_slug": "vacaria"},
    )

    assert response.status_code == 403
