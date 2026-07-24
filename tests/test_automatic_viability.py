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


def test_interface_nao_exige_avaliacao_de_viabilidade():
    client = app_module.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "viabilityFields" not in html
    assert "Avaliação de viabilidade" not in html


def test_api_ignora_questionario_legado_e_enfileira_somente_o_pdf(
    tmp_path,
    monkeypatch,
):
    queue = CapturingQueue()
    monkeypatch.setattr(app_module, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(app_module, "work_q", queue)
    app_module.jobs.clear()

    client = app_module.app.test_client()
    response = client.post(
        "/api/projetos",
        data={
            "arquivo": (io.BytesIO(_pdf_bytes()), "projeto.pdf"),
            "viabilidade": json.dumps(["Não"] * 10),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 202
    job_id = response.get_json()["job_id"]
    assert queue.items == [job_id]
    assert "viabilidade" not in app_module.jobs[job_id]
