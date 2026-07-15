from __future__ import annotations

from pathlib import Path

from croqui_engine.excel.sheet_profiler import profile_workbook


def profile_template(path: Path) -> dict:
    profile = profile_workbook(path)
    profile["template_family_hint"] = _family_from_name(path.name)
    return profile


def _family_from_name(name: str) -> str:
    upper = name.upper()
    for token in ("TR", "FU", "FC", "RL", "CF"):
        if f" {token} " in f" {upper} " or upper.startswith(token):
            return token
    return "UNKNOWN"

