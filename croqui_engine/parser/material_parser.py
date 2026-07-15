from __future__ import annotations

from croqui_engine.core.models import MaterialItem
from croqui_engine.symbols.catalog import match_materials


def parse_materials(text: str) -> list[MaterialItem]:
    return [
        MaterialItem(code=code, source="text", confidence=0.65)
        for code in match_materials(text)
    ]
