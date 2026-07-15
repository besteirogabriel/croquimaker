from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models_v2 import TechnicalPayloadV2
from croqui_engine.rendering.croqui_renderer_v2 import render_croqui_v2


def export_pdf_v2(payload: TechnicalPayloadV2, output_path: Path) -> Path:
    return render_croqui_v2(payload, output_path)

