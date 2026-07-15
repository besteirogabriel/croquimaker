from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from croqui_engine.core.config import ROOT_DIR


@dataclass(frozen=True)
class SymbolMatch:
    category: str
    type: str
    text: str
    confidence: float


@dataclass
class SymbolCatalog:
    version: str
    description: str
    data: dict

    @property
    def is_heuristic(self) -> bool:
        return "heuristic" in self.version.lower()


def default_catalog_path() -> Path:
    return ROOT_DIR / "croqui_engine" / "symbols" / "default_rge_heuristic.yaml"


def load_symbol_catalog(path: Path | None = None) -> SymbolCatalog:
    path = path or default_catalog_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SymbolCatalog(
        version=str(data.get("version", "unknown")),
        description=str(data.get("description", "")),
        data=data,
    )


def match_equipment(text: str, catalog: SymbolCatalog | None = None) -> list[SymbolMatch]:
    catalog = catalog or load_symbol_catalog()
    matches: list[SymbolMatch] = []
    source = text or ""
    for eq_type, config in (catalog.data.get("equipment_patterns") or {}).items():
        confidence = float(config.get("confidence", 0.6))
        for pattern in config.get("regex", []) or []:
            for found in re.finditer(pattern, source, flags=re.IGNORECASE):
                matches.append(
                    SymbolMatch(
                        category="equipment",
                        type=eq_type,
                        text=found.group(0),
                        confidence=confidence,
                    )
                )
    return matches


def match_materials(text: str, catalog: SymbolCatalog | None = None) -> list[str]:
    catalog = catalog or load_symbol_catalog()
    found: list[str] = []
    source = text or ""
    for pattern in (catalog.data.get("materials") or {}).get("common_regex", []) or []:
        for item in re.findall(pattern, source, flags=re.IGNORECASE):
            value = item if isinstance(item, str) else item[0]
            found.append(value.upper())
    return list(dict.fromkeys(found))


def match_network_type(text: str, catalog: SymbolCatalog | None = None) -> str | None:
    catalog = catalog or load_symbol_catalog()
    source = text or ""
    for key, config in (catalog.data.get("network_labels") or {}).items():
        for pattern in config.get("regex", []) or []:
            if re.search(pattern, source, flags=re.IGNORECASE):
                return key.upper()
    return None


def import_symbol_catalog_from_excel(path: Path) -> SymbolCatalog:
    raise NotImplementedError(
        "Importacao de simbologia oficial via Excel depende do arquivo homologado da JOBEL."
    )
