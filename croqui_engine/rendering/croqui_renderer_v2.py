from __future__ import annotations

from pathlib import Path

from croqui_engine.adapters.v2_to_v1 import adapt_v2_to_v1
from croqui_engine.core.models_v2 import TechnicalPayloadV2
from croqui_engine.rendering.final_croqui_renderer import generate_final_croqui_pdf


def render_croqui_v2(payload: TechnicalPayloadV2, output_path: Path) -> Path:
    return generate_final_croqui_pdf(adapt_v2_to_v1(payload), output_path)
