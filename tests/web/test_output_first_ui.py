from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

from croqui_engine.core.config import settings
from croqui_engine.core.models import TechnicalPayload
from croqui_engine.generators.json_exporter import export_payload_json
from croqui_engine.output.contract import CroquiOutputContract, attach_output_contract


def _login(client):
    return client.post(
        "/login",
        data={"email": settings.admin_email, "password": settings.admin_password},
        follow_redirects=True,
    )


def test_output_first_upload_status_artifacts_and_downloads(tmp_path, monkeypatch):
    from croqui_engine.app import project_processing
    from croqui_engine.app.web import app
    from croqui_engine.storage import file_store

    monkeypatch.setattr(
        file_store,
        "settings",
        SimpleNamespace(upload_dir=tmp_path / "uploads", output_dir=tmp_path / "outputs", root_dir=tmp_path),
    )

    calls = {"process": 0, "generate": 0}

    def fake_process_pdf(pdf_path: Path, job_id: str) -> TechnicalPayload:
        calls["process"] += 1
        assert pdf_path.name == "original.pdf"
        return TechnicalPayload(
            job_id=job_id,
            meta={"municipality": "Caxias do Sul"},
            confidence_global=0.76,
        )

    def fake_generate_outputs(payload: TechnicalPayload, pdf_path: Path | None = None) -> dict[str, Path]:
        calls["generate"] += 1
        assert pdf_path is not None
        out_dir = file_store.job_output_dir(payload.job_id or "manual")
        pdf = out_dir / "croqui_final.pdf"
        png = out_dir / "croqui_final.png"
        xls = out_dir / "croqui_final.xls"
        report = out_dir / "output_validation_report.json"
        reviewed = out_dir / "technical_payload_reviewed.json"
        pdf.write_bytes(b"%PDF-1.4\n% fake output-first pdf\n")
        png.write_bytes(b"fake png")
        xls.write_bytes(b"fake xls")
        contract = CroquiOutputContract(
            project_id=payload.job_id,
            source_pdf=str(pdf_path),
            header={"municipality": "CAXIAS DO SUL", "equipment": "TR 634087"},
            expected_or_selected_main_equipment="TR 634087",
            selected_equipment_type="TR",
            selected_equipment_code="634087",
            selected_equipment_source="execution_plan",
            selected_equipment_confidence=0.82,
            primary_focus_code="634087",
            primary_focus_bbox={"x0": 10, "y0": 20, "x1": 40, "y1": 60},
            focus_region={"x0": 0, "y0": 0, "x1": 120, "y1": 120},
            focus_confidence=0.80,
            focus_validated=True,
            included_codes=["634087"],
            output_status="final_candidate",
            validation_status="PASSED",
            final_output_allowed=True,
        )
        attach_output_contract(payload, contract)
        export_payload_json(payload, reviewed)
        report.write_text(
            json.dumps(
                {
                    "contract": {
                        "expected_or_selected_main_equipment": "TR 634087",
                        "selected_equipment_code": "634087",
                        "selected_equipment_confidence": 0.82,
                        "primary_focus_code": "634087",
                        "focus_confidence": 0.80,
                    },
                    "generated": {
                        "pdf_header_equipment": "TR 634087",
                        "xls_header_equipment": "TR 634087",
                        "visible_codes": ["634087"],
                    },
                    "validation": {
                        "status": "PASSED",
                        "output_status": "final_candidate",
                        "final_output_allowed": True,
                        "blocking_errors": [],
                        "warnings": [],
                    },
                }
            ),
            encoding="utf-8",
        )
        return {"pdf": pdf, "png": png, "xls": xls, "json": reviewed, "validation_report": report}

    monkeypatch.setattr(project_processing, "process_pdf", fake_process_pdf)
    monkeypatch.setattr(project_processing, "generate_outputs", fake_generate_outputs)

    app.config.update(TESTING=True)
    client = app.test_client()
    login_response = _login(client)
    assert login_response.status_code == 200

    upload_response = client.post(
        "/api/projects/upload",
        data={"pdf": (io.BytesIO(b"%PDF-1.4 fake"), "projeto_novo.pdf")},
        content_type="multipart/form-data",
    )

    assert upload_response.status_code == 200
    body = upload_response.get_json()
    assert body["ok"] is True
    assert calls == {"process": 1, "generate": 1}
    assert body["summary"]["selected_main_equipment"] == "TR 634087"
    assert body["summary"]["validation_status"] == "PASSED"
    assert body["summary"]["output_status"] == "final_candidate"
    assert body["summary"]["final_output_allowed"] is True

    job_id = body["job_id"]
    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    status_body = status_response.get_json()
    assert status_body["summary"]["selected_main_equipment"] == "TR 634087"
    assert status_body["summary"]["validation_status"] == "PASSED"

    artifacts_response = client.get(f"/api/jobs/{job_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifact_kinds = {item["kind"] for item in artifacts_response.get_json()["artifacts"]}
    assert {"pdf", "xls", "report"} <= artifact_kinds

    assert client.get(f"/api/jobs/{job_id}/download/pdf").status_code == 200
    assert client.get(f"/api/jobs/{job_id}/download/xls").status_code == 200
    report_response = client.get(f"/api/jobs/{job_id}/download/report")
    assert report_response.status_code == 200
    assert b"TR 634087" in report_response.data

    page = client.get(f"/jobs/{job_id}")
    assert page.status_code == 200
    assert b"TR 634087" in page.data
    assert b"Candidato final gerado" in page.data
    assert b"Relat" in page.data
    assert settings.use_corpus_reference_outputs is True
