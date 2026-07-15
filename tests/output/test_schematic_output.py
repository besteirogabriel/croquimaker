from __future__ import annotations

from croqui_engine.core.models import BBox, Equipment, Node, Span, TechnicalPayload
from croqui_engine.core.pipeline import ensure_output_contract
from croqui_engine.output.contract import CroquiOutputContract, output_contract_from_payload
from croqui_engine.output.visual_quality import validate_schematic_visual_quality
from croqui_engine.rendering.svg_croqui_renderer import generate_svg_croqui


def test_output_contract_builds_schematic_layout_from_electrical_graph():
    payload = _schematic_payload()

    payload = ensure_output_contract(payload, None, force_rebuild=True)
    contract = output_contract_from_payload(payload)
    layout = payload.meta["schematic_layout"]

    assert contract is not None
    assert contract.selected_equipment_code == "754881"
    assert layout["source"] == "SchematicLayoutEngine"
    assert payload.meta["electrical_graph"]["nodes"]
    assert payload.meta["focus_subgraph"]["included_codes"] == ["754881"]
    focus_nodes = [node for node in layout["nodes"] if node.get("is_focus")]
    assert focus_nodes
    assert abs(float(focus_nodes[0]["x"]) - 500.0) <= 1.0
    assert abs(float(focus_nodes[0]["y"]) - 210.0) <= 1.0
    assert all(0 <= float(node["x"]) <= 1000 for node in layout["nodes"])
    assert all(0 <= float(node["y"]) <= 420 for node in layout["nodes"])


def test_svg_renderer_uses_schematic_layout_not_raw_trace_coordinates(tmp_path):
    payload = ensure_output_contract(_schematic_payload(), None, force_rebuild=True)

    svg_path = generate_svg_croqui(payload, tmp_path / "croqui.svg")
    svg = svg_path.read_text(encoding="utf-8")

    assert "754881" in svg
    assert "<polyline" in svg
    assert "2409" not in svg
    assert "3201" not in svg


def test_visual_quality_blocks_missing_schematic_layout():
    contract = CroquiOutputContract(
        project_id="missing-layout",
        header={"equipment": "FU 754881"},
        expected_or_selected_main_equipment="FU 754881",
        selected_equipment_type="FU",
        selected_equipment_code="754881",
        selected_equipment_source="execution_plan",
        selected_equipment_confidence=0.88,
        primary_focus_code="754881",
        focus_confidence=0.9,
        focus_validated=True,
        included_codes=["754881"],
        output_status="final_candidate",
        validation_status="PASSED",
        final_output_allowed=True,
    )

    validated = validate_schematic_visual_quality(contract, None)

    assert validated.output_status == "low_quality_draft"
    assert validated.final_output_allowed is False
    assert {warning["code"] for warning in validated.warnings} >= {"SCHEMATIC_LAYOUT_MISSING"}


def _schematic_payload() -> TechnicalPayload:
    return TechnicalPayload(
        job_id="schematic-output",
        meta={
            "department": "JOBEL",
            "municipality": "Caxias do Sul",
            "survey_date": "01/07/2026",
            "surveyor": "Equipe A",
            "tes_actions": [
                {
                    "label": "FU",
                    "code": "754881",
                    "type": "CHAVE_FUSIVEL",
                    "status": "abrir",
                    "raw_text": "Abrir FU 754881",
                }
            ],
            "project_numeric_labels": ["754881", "634087"],
            "project_numeric_label_positions": [
                {"text": "754881", "x": 2409, "y": 3201},
                {"text": "634087", "x": 3900, "y": 3300},
            ],
            "project_vector_trace": {
                "mode": "clean_project_trace",
                "page_width": 4200,
                "page_height": 3600,
                "labels": [
                    {"text": "754881", "x": 2409, "y": 3201},
                    {"text": "634087", "x": 3900, "y": 3300},
                ],
                "segments": [
                    {"kind": "blue", "x1": 2409, "y1": 3201, "x2": 3900, "y2": 3300},
                    {"kind": "red", "x1": 2360, "y1": 3160, "x2": 2440, "y2": 3240},
                ],
                "symbols": [{"x": 2409, "y": 3201, "kind": "dark"}],
            },
        },
        nodes=[
            Node(id="P1", x=100.0, y=210.0, confidence=0.9),
            Node(id="P2", x=220.0, y=210.0, confidence=0.9),
            Node(id="P3", x=340.0, y=210.0, confidence=0.9),
        ],
        spans=[
            Span(id="S1", from_node="P1", to_node="P2", network_type="AT", confidence=0.9),
            Span(id="S2", from_node="P2", to_node="P3", network_type="AT", confidence=0.9),
        ],
        equipment=[
            Equipment(
                code="754881",
                type="CHAVE_FUSIVEL",
                bbox=BBox(x0=210.0, y0=190.0, x1=230.0, y1=214.0),
                confidence=0.92,
                node_id="P2",
                raw_text="FU 754881",
            )
        ],
    )
