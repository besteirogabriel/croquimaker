from __future__ import annotations

import json
from pathlib import Path

import pytest

from croqui_engine.core.pipeline import generate_outputs, process_pdf


def test_known_project_uses_corpus_reference_output_when_available():
    project_pdf = Path("CROQUI IA/300001061186/300001061186 PROJETO A3.pdf")
    if not project_pdf.exists():
        pytest.skip("Corpus real FU 754881 nao disponivel neste ambiente.")

    job_id = "test_fu754881_regression"
    payload = process_pdf(project_pdf, job_id)
    outputs = generate_outputs(payload, project_pdf)

    diff = json.loads((outputs["pdf"].parent / "diff_report.json").read_text(encoding="utf-8"))
    reviewed = json.loads(outputs["json"].read_text(encoding="utf-8"))
    report = json.loads(outputs["validation_report"].read_text(encoding="utf-8"))

    assert outputs["pdf"].exists()
    assert outputs["xls"].exists()
    assert reviewed["meta"]["output_mode"] == "CORPUS_REFERENCE_APPROVED"
    assert reviewed["meta"]["output_source_case_id"] == "300001061186"
    assert "output_contract" in reviewed["meta"]
    contract = reviewed["meta"]["output_contract"]
    assert contract["expected_or_selected_main_equipment"] == "FU 754881"
    assert contract["selected_equipment_code"] == "754881"
    assert contract["selected_equipment_source"] == "corpus_reference"
    assert contract["primary_focus_code"] == "754881"
    assert diff["missing_fields"] == []
    assert diff["missing_equipment"] == []
    assert diff["layout_differences"] == []
    assert diff["visual_score"] == 1.0
    assert diff["technical_score"] == 1.0
    assert report["generated"]["pdf_header_equipment"] == report["generated"]["xls_header_equipment"]
    assert report["generated"]["pdf_header_equipment"] == "FU 754881"
