import io
import json
import re
import sqlite3

import fitz

from croquimaker.project_store import ProjectStore


class CapturingQueue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


def _pdf_bytes(label="Projeto teste") -> bytes:
    document = fitz.open()
    document.new_page().insert_text((72, 72), label)
    content = document.tobytes()
    document.close()
    return content


def _csrf(client) -> str:
    with client.session_transaction() as browser_session:
        return browser_session["_csrf_token"]


def _upload(client, filename="projeto.pdf"):
    return client.post(
        "/api/projetos",
        data={"arquivo": (io.BytesIO(_pdf_bytes(filename)), filename)},
        headers={"X-CSRF-Token": _csrf(client)},
        content_type="multipart/form-data",
    )


def test_upload_persiste_projeto_com_nomes_unicos_e_manifesto_seguro(
    app_module_with_auth,
    login_client,
    monkeypatch,
):
    queue = CapturingQueue()
    monkeypatch.setattr(app_module_with_auth, "work_q", queue)
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")

    first = _upload(client, "OS 300001.pdf")
    second = _upload(client, "OS 300001.pdf")

    assert first.status_code == 202
    assert second.status_code == 202
    first_id = first.get_json()["job_id"]
    second_id = second.get_json()["job_id"]
    assert first_id != second_id

    first_job = app_module_with_auth.project_store.get_job(first_id, "caxias")
    second_job = app_module_with_auth.project_store.get_job(second_id, "caxias")
    assert first_job is not None
    assert second_job is not None
    assert first_job["output_pdf_filename"] != second_job["output_pdf_filename"]
    assert re.fullmatch(
        r"CROQUI-CAXIAS-\d{8}T\d{6}Z-[0-9A-F]{10}\.pdf",
        first_job["output_pdf_filename"],
    )
    assert first_job["input_sha256"]

    status_path = (
        app_module_with_auth.PROJECTS_DIR
        / "caxias"
        / "jobs"
        / first_id
        / "status.json"
    )
    manifest = json.loads(status_path.read_text(encoding="utf-8"))
    assert "dir" not in manifest
    assert "input" not in manifest
    assert manifest["original_filename"] == "OS 300001.pdf"
    assert manifest["input_filename"].startswith("PROJETO-CAXIAS-")
    assert queue.items == [f"caxias:{first_id}", f"caxias:{second_id}"]


def test_dashboard_regional_isola_unidade_e_admin_consolida_as_duas(
    app_module_with_auth,
    login_client,
    monkeypatch,
):
    queue = CapturingQueue()
    monkeypatch.setattr(app_module_with_auth, "work_q", queue)

    caxias = app_module_with_auth.app.test_client()
    login_client(caxias, "caxias1")
    assert _upload(caxias, "PROJETO-CAXIAS-TESTE.pdf").status_code == 202

    vacaria = app_module_with_auth.app.test_client()
    login_client(vacaria, "vacaria1")
    assert _upload(vacaria, "PROJETO-VACARIA-TESTE.pdf").status_code == 202

    caxias_page = caxias.get("/").get_data(as_text=True)
    assert "PROJETO-CAXIAS-TESTE.pdf" in caxias_page
    assert "PROJETO-VACARIA-TESTE.pdf" not in caxias_page

    admin = app_module_with_auth.app.test_client()
    login_client(admin, "admin1")
    admin_page = admin.get("/").get_data(as_text=True)
    assert "PROJETO-CAXIAS-TESTE.pdf" in admin_page
    assert "PROJETO-VACARIA-TESTE.pdf" in admin_page
    assert "Visão consolidada dos projetos de Caxias e Vacaria." in admin_page


def test_saida_generica_e_renomeada_e_download_preserva_nome_unico(
    app_module_with_auth,
    login_client,
    monkeypatch,
):
    queue = CapturingQueue()
    monkeypatch.setattr(app_module_with_auth, "work_q", queue)
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")
    created = _upload(client, "entrada.pdf")
    job_id = created.get_json()["job_id"]
    job = app_module_with_auth.jobs[f"caxias:{job_id}"]
    job_dir = app_module_with_auth.PROJECTS_DIR / "caxias" / "jobs" / job_id
    generic_output = job_dir / "croqui.pdf"
    generic_output.write_bytes(_pdf_bytes("Croqui final"))

    app_module_with_auth._finalize_artifacts(job)
    job["state"] = "done"
    job["message"] = app_module_with_auth.PUBLIC_MESSAGES["done"]
    app_module_with_auth._save_job(job)

    unique_output = job_dir / job["output_pdf_filename"]
    assert unique_output.exists()
    assert not generic_output.exists()

    response = client.get(f"/api/projetos/{job_id}/croqui.pdf")
    assert response.status_code == 200
    assert job["output_pdf_filename"] in response.headers["Content-Disposition"]

    events = app_module_with_auth.project_store.list_events(("caxias",), limit=20)
    assert any(
        event["action"] == "artifact.downloaded" and event["job_id"] == job_id
        for event in events
    )


def test_trilha_de_auditoria_detecta_alteracao(tmp_path):
    store = ProjectStore(tmp_path / "operations.db")
    store.initialize()
    store.record_event(actor_username="admin1", action="auth.login")
    store.record_event(
        actor_username="admin1",
        action="project.created",
        project_slug="caxias",
        job_id="a" * 32,
    )
    assert store.verify_audit_chain()

    with sqlite3.connect(store.database) as connection:
        connection.execute(
            "UPDATE audit_events SET action = 'project.changed' WHERE id = 1"
        )

    assert not store.verify_audit_chain()


def test_auditoria_regional_nao_expoe_eventos_de_outra_unidade(
    app_module_with_auth,
    login_client,
):
    app_module_with_auth.project_store.record_event(
        actor_username="caxias1",
        action="project.created",
        project_slug="caxias",
        job_id="a" * 32,
    )
    app_module_with_auth.project_store.record_event(
        actor_username="vacaria1",
        action="project.created",
        project_slug="vacaria",
        job_id="b" * 32,
    )
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")

    page = client.get("/auditoria").get_data(as_text=True)

    assert "#AAAAAAAA" in page
    assert "#BBBBBBBB" not in page
    assert "Trilha de auditoria" in page
