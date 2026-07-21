from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sistema.parsing.entities import ProjectExtraction


class Extractor(Protocol):
    kind: str

    def supports(self, path: Path) -> bool: ...

    def extract(self, folder_id: str, path: Path) -> ProjectExtraction: ...


_REGISTRY: dict[str, Extractor] = {}


def register(extractor: Extractor) -> None:
    _REGISTRY[extractor.kind] = extractor


def get_extractor(kind: str) -> Extractor:
    return _REGISTRY[kind]


def get_extractor_for_path(path: Path) -> Extractor | None:
    for extractor in _REGISTRY.values():
        if extractor.supports(path):
            return extractor
    return None


def registered_kinds() -> list[str]:
    return list(_REGISTRY.keys())
