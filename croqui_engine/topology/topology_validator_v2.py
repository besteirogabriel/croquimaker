from __future__ import annotations

from croqui_engine.core.models_v2 import TechnicalPayloadV2


def validate_topology_v2(payload: TechnicalPayloadV2) -> list[dict]:
    warnings = []
    if not payload.graph_entities:
        warnings.append({"severity": "warning", "code": "V2_GRAPH_EMPTY"})
    return warnings

