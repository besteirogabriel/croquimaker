from __future__ import annotations

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.core.models_v2 import TechnicalPayloadV2


def adapt_v2_to_v1(payload: TechnicalPayloadV2) -> TechnicalPayload:
    if payload.v1_payload is not None:
        return payload.v1_payload
    return TechnicalPayload(job_id=payload.job_id)

