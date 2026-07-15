from __future__ import annotations

from croqui_engine.core.models import TechnicalPayload


def payload_to_graph_json(payload: TechnicalPayload) -> dict:
    return {
        "nodes": [node.as_dict() for node in payload.active_nodes()],
        "edges": [
            {
                "id": span.id,
                "source": span.from_node,
                "target": span.to_node,
                "length_m": span.length_m,
                "cable": span.cable,
                "network_type": span.network_type,
                "confidence": span.confidence,
            }
            for span in payload.active_spans()
        ],
        "equipment": [item.as_dict() for item in payload.active_equipment()],
    }
