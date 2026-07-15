from __future__ import annotations

import json

from croqui_engine.core.equipment_candidate_resolver import resolve_main_equipment
from croqui_engine.core.models import Equipment, TechnicalPayload
from croqui_engine.core.pipeline import ensure_output_contract, generate_outputs
from croqui_engine.output.contract import CroquiOutputContract, output_contract_from_payload
from croqui_engine.output.validation import validate_output_contract


def test_main_candidate_is_not_selected_by_secondary_presence_only():
    payload = TechnicalPayload(
        job_id="candidate-test",
        meta={
            "tes_actions": [
                {
                    "label": "TR",
                    "code": "634087",
                    "type": "TRANSFORMADOR",
                    "status": "abrir",
                    "raw_text": "Abrir TR 634087",
                }
            ],
            "project_numeric_labels": ["1297573", "1297574", "634087", "633743"],
            "project_numeric_label_positions": [
                {"text": "1297574", "x": 1200, "y": 1200},
                {"text": "634087", "x": 120, "y": 115},
            ],
            "project_vector_trace": {
                "mode": "clean_project_trace",
                "page_width": 1400,
                "page_height": 1400,
                "labels": [
                    {"text": "1297574", "x": 1200, "y": 1200},
                    {"text": "634087", "x": 120, "y": 115},
                ],
                "segments": [
                    {"kind": "red", "x1": 95, "y1": 90, "x2": 155, "y2": 130},
                    {"kind": "red", "x1": 100, "y1": 145, "x2": 160, "y2": 100},
                ],
                "symbols": [{"x": 122, "y": 118, "kind": "dark"}],
            },
        },
        equipment=[
            Equipment(code="1297573", type="CHAVE_FUSIVEL", confidence=0.75),
            Equipment(code="1297574", type="TRANSFORMADOR", confidence=0.75),
            Equipment(code="634087", type="TRANSFORMADOR", confidence=0.75),
            Equipment(code="633743", type="TRANSFORMADOR", confidence=0.75),
        ],
    )

    candidate = resolve_main_equipment(payload)

    assert candidate is not None
    assert candidate.label == "TR 634087"
    assert {item.kind for item in candidate.evidence} >= {"execution_plan", "near_work_zone"}


def test_header_focus_divergence_blocks_final_output():
    contract = CroquiOutputContract(
        project_id="mismatch",
        header={"equipment": "TR 1297574"},
        expected_or_selected_main_equipment="TR 634087",
        selected_equipment_type="TR",
        selected_equipment_code="634087",
        selected_equipment_source="execution_plan",
        selected_equipment_confidence=0.82,
        primary_focus_code="634087",
        focus_confidence=0.81,
        focus_validated=True,
        included_codes=["634087"],
    )

    validated = validate_output_contract(contract)

    assert validated.final_output_allowed is False
    assert validated.validation_status == "BLOCKED"
    assert {item["code"] for item in validated.blocking_errors} >= {"HEADER_EQUIPMENT_MISMATCH"}


def test_new_project_without_corpus_creates_contract_and_consistent_outputs(tmp_path, monkeypatch):
    from croqui_engine.core import pipeline

    monkeypatch.setattr(pipeline, "job_output_dir", lambda job_id: tmp_path / job_id)
    payload = TechnicalPayload(
        job_id="new-project",
        meta={
            "municipality": "Caxias do Sul",
            "project_numeric_labels": ["634087"],
            "project_numeric_label_positions": [{"text": "634087", "x": 120, "y": 120}],
            "project_vector_trace": {
                "mode": "focused_trace",
                "page_width": 400,
                "page_height": 300,
                "labels": [{"text": "634087", "x": 120, "y": 120}],
                "segments": [{"kind": "red", "x1": 100, "y1": 100, "x2": 150, "y2": 135}],
                "symbols": [{"x": 122, "y": 118, "kind": "dark"}],
            },
        },
        equipment=[Equipment(code="634087", type="TRANSFORMADOR", confidence=0.8)],
    )

    payload = ensure_output_contract(payload, None, force_rebuild=True)
    contract = output_contract_from_payload(payload)
    outputs = generate_outputs(payload, None)
    report = json.loads(outputs["validation_report"].read_text(encoding="utf-8"))

    assert contract is not None
    assert contract.expected_or_selected_main_equipment == "TR 634087"
    assert contract.selected_equipment_confidence is not None
    assert contract.output_status in {"draft", "final_candidate", "low_quality_draft"}
    assert outputs["pdf"].exists()
    assert outputs["xls"].exists()
    assert report["generated"]["pdf_header_equipment"] == report["generated"]["xls_header_equipment"]


def test_clean_project_trace_without_validated_focus_is_not_final_candidate():
    contract = CroquiOutputContract(
        project_id="trace-only",
        header={"equipment": "TR 634087"},
        expected_or_selected_main_equipment="TR 634087",
        selected_equipment_type="TR",
        selected_equipment_code="634087",
        selected_equipment_source="spatial_fallback",
        selected_equipment_confidence=0.38,
        primary_focus_code="634087",
        focus_confidence=0.34,
        focus_validated=False,
        included_codes=["634087"],
    )

    validated = validate_output_contract(contract)

    assert validated.output_status != "final_candidate"
    assert validated.final_output_allowed is False
    assert {item["code"] for item in validated.warnings} >= {"FOCUS_NOT_VALIDATED"}
