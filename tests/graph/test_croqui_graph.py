from __future__ import annotations

import json

from croqui_engine.core.models import Equipment, Node, Span, TechnicalPayload
from croqui_engine.core.pipeline import ensure_output_contract
from croqui_engine.generators.svg_graph_exporter import export_from_croqui_graph_svg
from croqui_engine.graph.croqui_graph import (
    croqui_graph_from_payload,
    validate_croqui_graph_for_export,
)


def test_payload_is_converted_to_croqui_graph_contract():
    payload = ensure_output_contract(_payload(), None, force_rebuild=True)

    graph = croqui_graph_from_payload(payload)

    assert graph.header.equipamento == "FU 754881"
    assert graph.mainEquipment.code == "754881"
    assert graph.nodes
    assert graph.edges
    assert any(node.isMain for node in graph.nodes)
    assert graph.workZones[0].attachedTo == graph.mainEquipment.id


def test_export_validation_blocks_svg_without_main_equipment():
    payload = ensure_output_contract(_payload(), None, force_rebuild=True)
    graph = croqui_graph_from_payload(payload)

    validation = validate_croqui_graph_for_export(graph, "<svg></svg>")

    assert validation.status == "blocked"
    assert {item["code"] for item in validation.blockingErrors} >= {"SVG_MAIN_EQUIPMENT_NOT_FOUND"}


def test_export_uses_submitted_svg_for_pdf_and_xls(tmp_path):
    payload = ensure_output_contract(_payload(), None, force_rebuild=True)
    graph = croqui_graph_from_payload(payload)
    svg = """
    <svg xmlns="http://www.w3.org/2000/svg" width="840" height="595" viewBox="0 0 840 595">
      <rect x="0" y="0" width="840" height="595" fill="white"/>
      <text x="120" y="120">FU 754881</text>
      <circle cx="220" cy="220" r="20" stroke="black" fill="none"/>
    </svg>
    """

    outputs = export_from_croqui_graph_svg(graph, svg, tmp_path)
    report = json.loads(outputs["validation_report"].read_text(encoding="utf-8"))

    assert outputs["svg"].read_text(encoding="utf-8") == svg
    assert outputs["pdf"].exists()
    assert outputs["xls"].exists()
    assert outputs["xlsx"].exists()
    assert report["generated"]["pdf_header_equipment"] == report["generated"]["xls_header_equipment"]


def _payload() -> TechnicalPayload:
    return TechnicalPayload(
        job_id="graph-test",
        meta={
            "department": "JOBEL",
            "municipality": "Caxias do Sul",
            "survey_date": "01/07/2026",
            "surveyor": "Equipe A",
            "tes_actions": [
                {"label": "FU", "code": "754881", "type": "CHAVE_FUSIVEL", "status": "abrir"}
            ],
            "project_numeric_label_positions": [{"text": "754881", "x": 220, "y": 220}],
            "project_vector_trace": {
                "mode": "clean_project_trace",
                "labels": [{"text": "754881", "x": 220, "y": 220}],
                "segments": [{"kind": "red", "x1": 190, "y1": 190, "x2": 240, "y2": 240}],
            },
        },
        nodes=[
            Node(id="P1", x=100, y=200, confidence=0.9),
            Node(id="P2", x=220, y=200, confidence=0.9),
            Node(id="P3", x=340, y=200, confidence=0.9),
        ],
        spans=[
            Span(id="S1", from_node="P1", to_node="P2", network_type="AT", confidence=0.9),
            Span(id="S2", from_node="P2", to_node="P3", network_type="AT", confidence=0.9),
        ],
        equipment=[
            Equipment(code="754881", type="CHAVE_FUSIVEL", node_id="P2", confidence=0.9),
        ],
    )
