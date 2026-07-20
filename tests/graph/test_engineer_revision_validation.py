from __future__ import annotations

from croqui_engine.graph.croqui_graph import (
    CroquiEdge,
    CroquiGraph,
    CroquiGraphHeader,
    CroquiGraphValidation,
    CroquiMainEquipment,
    CroquiNode,
    validate_croqui_graph_for_export,
)


def test_engineer_regeneration_keeps_non_blocking_warnings_visible():
    graph = CroquiGraph(
        id="synthetic-editor-revision",
        header=CroquiGraphHeader(equipamento="FU 000000"),
        mainEquipment=CroquiMainEquipment(
            id="main-device",
            type="FU",
            code="000000",
            confidence=0.5,
        ),
        nodes=[
            CroquiNode(id="source", kind="pole"),
            CroquiNode(
                id="main-device",
                kind="switch",
                equipmentType="FU",
                code="000000",
                isMain=True,
            ),
        ],
        edges=[CroquiEdge(id="network", source="source", target="main-device")],
        validation=CroquiGraphValidation(
            status="draft",
            warnings=[{"code": "SYNTHETIC_REVIEW_WARNING"}],
        ),
    )
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>FU 000000</text></svg>'

    validation = validate_croqui_graph_for_export(graph, svg)

    assert validation.status == "final_candidate"
    assert validation.blockingErrors == []
    assert validation.warnings == [{"code": "SYNTHETIC_REVIEW_WARNING"}]
