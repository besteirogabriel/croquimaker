from __future__ import annotations

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.core.models_v2 import CroquiEntity, EvidenceRef, TechnicalPayloadV2


def adapt_v1_to_v2(payload: TechnicalPayload, case_id: str | None = None) -> TechnicalPayloadV2:
    entities: list[CroquiEntity] = []
    for node in payload.active_nodes():
        entities.append(
            CroquiEntity(
                id=f"node-{node.id}",
                type="NODE",
                code=node.id,
                label=node.id,
                bbox=node.bbox,
                geometry={"x": node.x, "y": node.y, "page_index": node.page_index},
                evidence=[EvidenceRef(source="PROJECT_PDF", case_id=case_id, text=node.raw_text, bbox=node.bbox, confidence=node.confidence)],
            )
        )
    for span in payload.active_spans():
        entities.append(
            CroquiEntity(
                id=f"span-{span.id}",
                type="SPAN",
                code=span.id,
                label=span.id,
                bbox=span.bbox,
                geometry={"from_node": span.from_node, "to_node": span.to_node, "length_m": span.length_m},
                style={"network_type": span.network_type, "status": span.status, "cable": span.cable},
                evidence=[EvidenceRef(source="PROJECT_PDF", case_id=case_id, text=span.raw_text, bbox=span.bbox, confidence=span.confidence)],
            )
        )
    for equipment in payload.active_equipment():
        entities.append(
            CroquiEntity(
                id=f"equipment-{equipment.type}-{equipment.code}",
                type="EQUIPMENT",
                code=equipment.code,
                label=f"{equipment.type} {equipment.code}",
                bbox=equipment.bbox,
                geometry={"node_id": equipment.node_id, "page_index": equipment.page_index},
                style={"status": equipment.status},
                evidence=[EvidenceRef(source="PROJECT_PDF", case_id=case_id, text=equipment.raw_text, bbox=equipment.bbox, confidence=equipment.confidence)],
            )
        )
    return TechnicalPayloadV2(
        job_id=payload.job_id,
        case_id=case_id,
        v1_payload=payload,
        project_entities=entities,
        graph_entities=entities,
    )

