import importlib
import io
import json

import fitz


app_module = importlib.import_module("croquimaker.app")


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


def test_interface_nao_exige_avaliacao_de_viabilidade(
    app_module_with_auth,
    login_client,
):
    client = app_module_with_auth.app.test_client()
    login_client(client)
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "viabilityFields" not in html
    assert "Avaliação de viabilidade" not in html


def test_api_ignora_questionario_legado_e_enfileira_somente_o_pdf(
    tmp_path,
    monkeypatch,
    app_module_with_auth,
    login_client,
):
    queue = CapturingQueue()
    monkeypatch.setattr(app_module_with_auth, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(app_module_with_auth, "work_q", queue)
    app_module_with_auth.jobs.clear()

    client = app_module_with_auth.app.test_client()
    login_client(client)
    with client.session_transaction() as browser_session:
        token = browser_session["_csrf_token"]
    response = client.post(
        "/api/projetos",
        data={
            "arquivo": (io.BytesIO(_pdf_bytes()), "projeto.pdf"),
            "viabilidade": json.dumps(["Não"] * 10),
        },
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )

    assert response.status_code == 202
    job_id = response.get_json()["job_id"]
    assert queue.items == [f"caxias:{job_id}"]
    assert "viabilidade" not in app_module_with_auth.jobs[f"caxias:{job_id}"]
