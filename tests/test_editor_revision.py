from __future__ import annotations

import io
import json

import fitz


class CapturingQueue:
    def put(self, item):
        pass


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Projeto")
    content = document.tobytes()
    document.close()
    return content


def _csrf(client) -> str:
    with client.session_transaction() as browser_session:
        return browser_session["_csrf_token"]


def _completed_job(app_module, client, monkeypatch) -> tuple[str, dict]:
    monkeypatch.setattr(app_module, "work_q", CapturingQueue())
    response = client.post(
        "/api/projetos",
        data={"arquivo": (io.BytesIO(_pdf_bytes()), "projeto.pdf")},
        headers={"X-CSRF-Token": _csrf(client)},
        content_type="multipart/form-data",
    )
    job_id = response.get_json()["job_id"]
    job = app_module.jobs[f"caxias:{job_id}"]
    job["state"] = "done"
    job["message"] = app_module.PUBLIC_MESSAGES["done"]
    job_dir = app_module.PROJECTS_DIR / "caxias" / "jobs" / job_id
    (job_dir / job["output_pdf_filename"]).write_bytes(_pdf_bytes())
    scene = {
        "schema_version": 1,
        "page": {"width": 841.8898, "height": 595.2756},
        "metadata": {
            "departamento": "JOBEL",
            "municipio": "Caxias do Sul",
            "equipamento": "FU 735607",
            "data": "30/07/2026",
            "responsavel": "Teste",
        },
        "viability": ["Sim"] * 10,
        "elements": [
            {
                "id": "line-0",
                "kind": "line",
                "x1": 100,
                "y1": 200,
                "x2": 300,
                "y2": 200,
                "tension": "BT",
            },
            {
                "id": "pole-0",
                "kind": "symbol",
                "category": "pole",
                "symbol": "POSTE_CONCRETO",
                "x": 100,
                "y": 200,
                "code": "P1",
                "direction": [1, 0],
            },
        ],
    }
    (job_dir / "croqui_scene.json").write_text(
        json.dumps(scene),
        encoding="utf-8",
    )
    app_module._save_job(job)
    return job_id, scene


def test_editor_abre_cena_e_exporta_revisao_auditavel(
    app_module_with_auth,
    login_client,
    monkeypatch,
):
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")
    job_id, scene = _completed_job(app_module_with_auth, client, monkeypatch)

    page = client.get(f"/projetos/caxias/{job_id}/editor")
    assert page.status_code == 200
    assert "Revisão técnica do croqui" in page.get_data(as_text=True)

    loaded = client.get(
        f"/api/unidades/caxias/projetos/{job_id}/cena"
    ).get_json()
    assert loaded["elements"][1]["symbol"] == "POSTE_CONCRETO"

    scene["elements"][1]["symbol"] = "POSTE_MADEIRA"
    scene["elements"][1]["x"] = 140
    exported = client.post(
        f"/api/unidades/caxias/projetos/{job_id}/revisoes",
        json=scene,
        headers={"X-CSRF-Token": _csrf(client)},
    )
    assert exported.status_code == 201
    body = exported.get_json()
    assert body["revision"] == 1
    assert body["filename"].endswith("-REV001.pdf")

    downloaded = client.get(body["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.data.startswith(b"%PDF")

    job_dir = app_module_with_auth.PROJECTS_DIR / "caxias" / "jobs" / job_id
    saved = json.loads(
        (job_dir / "revisions" / "revision-001.json").read_text(encoding="utf-8")
    )
    assert saved["elements"][1]["symbol"] == "POSTE_MADEIRA"
    assert saved["elements"][1]["x"] == 140

    actions = {
        event["action"]
        for event in app_module_with_auth.project_store.list_events(
            ("caxias",),
            limit=30,
        )
    }
    assert {
        "editor.opened",
        "editor.revision_exported",
        "editor.revision_downloaded",
    } <= actions


def test_editor_rejeita_simbolo_ou_coordenada_manipulados(
    app_module_with_auth,
    login_client,
    monkeypatch,
):
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")
    job_id, scene = _completed_job(app_module_with_auth, client, monkeypatch)

    scene["elements"][1]["symbol"] = "../../arquivo"
    response = client.post(
        f"/api/unidades/caxias/projetos/{job_id}/revisoes",
        json=scene,
        headers={"X-CSRF-Token": _csrf(client)},
    )
    assert response.status_code == 400

    scene["elements"][1]["symbol"] = "POSTE_CONCRETO"
    scene["elements"][1]["x"] = 99999
    response = client.post(
        f"/api/unidades/caxias/projetos/{job_id}/revisoes",
        json=scene,
        headers={"X-CSRF-Token": _csrf(client)},
    )
    assert response.status_code == 400
