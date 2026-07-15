from __future__ import annotations

import json
from pathlib import Path

from croqui_engine.ground_truth.models import TargetCroquiPayload


def save_target_payload(payload: TargetCroquiPayload, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_target_payload(path: Path) -> TargetCroquiPayload:
    return TargetCroquiPayload.model_validate_json(path.read_text(encoding="utf-8"))

