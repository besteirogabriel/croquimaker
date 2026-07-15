from __future__ import annotations

import json
from pathlib import Path

import yaml

from croqui_engine.corpus.registry import load_registry
from croqui_engine.corpus.storage import catalogs_dir
from croqui_engine.excel.symbol_sheet_importer import import_symbol_sheet


def build_official_catalog(path: str | Path | None = None, limit: int | None = None) -> dict:
    registry = load_registry()
    symbols: dict[str, dict] = {}
    materials: dict[str, dict] = {}
    line_styles: list[dict] = []
    sources: list[dict] = []
    cases = registry.cases[:limit] if limit else registry.cases
    for case in cases:
        if not case.target_croqui_xls:
            continue
        source = import_symbol_sheet(case.case_id, Path(case.target_croqui_xls.path))
        sources.append(source)
        for symbol in source["symbols"]:
            current = symbols.setdefault(
                symbol["id"],
                {
                    "id": symbol["id"],
                    "names": [],
                    "source_sheets": [],
                    "visual_templates": [],
                    "text_patterns": [],
                    "style": {},
                },
            )
            current["names"] = sorted(set([*current["names"], *symbol.get("names", [])]))
            current["text_patterns"] = sorted(
                set([*current["text_patterns"], *symbol.get("text_patterns", [])])
            )
            current["source_sheets"].append(
                {
                    "case_id": case.case_id,
                    "file_path": symbol["source_file"],
                    "sheet_name": symbol["source_sheet"],
                    "row": symbol["source_row"],
                }
            )
        for material in source["materials"]:
            materials.setdefault(material["code"], {"code": material["code"], "sources": []})[
                "sources"
            ].append({"case_id": case.case_id, "row": material["source_row"]})
        line_styles.extend(source["line_styles"])

    catalog = {
        "catalog_version": "corpus-2026-06-25-v1",
        "source_cases": len(cases),
        "symbols": sorted(symbols.values(), key=lambda item: item["id"]),
        "materials": sorted(materials.values(), key=lambda item: item["code"]),
        "line_styles": line_styles[:500],
        "viability_questions": [],
        "source_registry": registry.source_path,
        "warnings": [],
    }
    save_catalog(catalog, path)
    save_symbol_sources(sources)
    return catalog


def load_official_catalog(path: str | Path | None = None) -> dict | None:
    raw = Path(path) if path else catalogs_dir() / "official_symbol_catalog.json"
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    if not raw.exists():
        return None
    return json.loads(raw.read_text(encoding="utf-8"))


def save_catalog(catalog: dict, path: str | Path | None = None) -> None:
    out_dir = catalogs_dir()
    json_path = Path(path) if path else out_dir / "official_symbol_catalog.json"
    if not json_path.is_absolute():
        json_path = Path.cwd() / json_path
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    yaml_path = out_dir / "official_symbol_catalog.yaml"
    yaml_path.write_text(yaml.safe_dump(catalog, sort_keys=False, allow_unicode=True), encoding="utf-8")


def save_symbol_sources(sources: list[dict]) -> None:
    source_dir = catalogs_dir() / "symbol_sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        path = source_dir / f"{source['case_id']}.json"
        path.write_text(json.dumps(source, indent=2, ensure_ascii=False), encoding="utf-8")

