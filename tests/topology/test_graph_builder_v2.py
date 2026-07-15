from croqui_engine.core.models import Equipment, Node, Span, TechnicalPayload
from croqui_engine.core.schema_version import V2_PROJECT_SCHEMA_VERSION
from croqui_engine.topology.graph_builder_v2 import build_graph_v2


def test_build_graph_v2_adapts_active_v1_objects_to_entities():
    payload = TechnicalPayload(
        job_id="job-001",
        nodes=[Node(id="P1", x=10, y=20, confidence=0.9)],
        spans=[Span(id="S1", from_node="P1", to_node="P2", length_m=30.5, confidence=0.8)],
        equipment=[Equipment(code="123456", type="TRANSFORMADOR", node_id="P1", confidence=0.95)],
    )

    v2 = build_graph_v2(payload, case_id="case-001")

    assert v2.schema_version == V2_PROJECT_SCHEMA_VERSION
    assert v2.case_id == "case-001"
    assert v2.v1_payload == payload
    assert {entity.type for entity in v2.graph_entities} == {"NODE", "SPAN", "EQUIPMENT"}
    assert all(entity.evidence for entity in v2.graph_entities)
