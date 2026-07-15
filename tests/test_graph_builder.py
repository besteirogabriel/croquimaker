from croqui_engine.core.models import Equipment, Span, TechnicalPayload
from croqui_engine.topology.graph_builder import build_graph
from croqui_engine.topology.graph_validator import validate_graph


def test_graph_builder_creates_nodes_from_spans():
    payload = build_graph(
        nodes=[],
        spans=[Span(id="V1-2", from_node="P1", to_node="P2", length_m=36.41, cable="3E70-1A")],
        equipment=[Equipment(code="1297088", type="TRANSFORMADOR", confidence=0.8)],
        payload=TechnicalPayload(meta={"tes_number": "31283669"}),
    )

    node_ids = {node.id for node in payload.nodes}
    assert {"P1", "P2"} <= node_ids
    assert payload.spans[0].from_node == "P1"


def test_graph_validator_adds_warnings_for_partial_payload():
    payload = TechnicalPayload(
        meta={"tes_number": "31283669"},
        spans=[Span(id="V1-2", from_node="P1", to_node="P2")],
        equipment=[Equipment(code="1297088", type="TRANSFORMADOR", confidence=0.8)],
    )
    payload = build_graph([], payload.spans, payload.equipment, payload)
    payload = validate_graph(payload)

    codes = {validation.code for validation in payload.validations}
    assert "SPAN_WITHOUT_LENGTH" in codes
    assert payload.confidence_global < 1
