from __future__ import annotations

from croqui_engine.adapters.v1_to_v2 import adapt_v1_to_v2
from croqui_engine.core.models import TechnicalPayload
from croqui_engine.core.models_v2 import TechnicalPayloadV2


def build_graph_v2(payload: TechnicalPayload, case_id: str | None = None) -> TechnicalPayloadV2:
    return adapt_v1_to_v2(payload, case_id=case_id)

