from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.storage.file_store import write_json


def export_payload_json(payload: TechnicalPayload, output_path: Path) -> Path:
    return write_json(output_path, payload.as_dict())


def load_payload_json(path: Path) -> TechnicalPayload:
    import json

    return TechnicalPayload.model_validate(json.loads(path.read_text(encoding="utf-8")))
