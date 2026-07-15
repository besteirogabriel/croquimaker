from __future__ import annotations

import re
from pathlib import Path

from croqui_engine.excel.xls_reader import find_sheet_name, open_workbook


def import_symbol_sheet(case_id: str, xls_path: Path) -> dict:
    book = open_workbook(xls_path)
    sheet_name = find_sheet_name(xls_path, "Simbologia")
    if not sheet_name:
        return {
            "case_id": case_id,
            "file_path": str(xls_path),
            "sheet_name": None,
            "symbols": [],
            "materials": [],
            "line_styles": [],
            "warnings": ["SIMBOLOGIA_SHEET_MISSING"],
        }
    sheet = book.sheet_by_name(sheet_name)
    symbols = []
    materials = []
    line_styles = []
    seen: set[str] = set()
    for row in range(sheet.nrows):
        values = [
            str(sheet.cell_value(row, col)).strip()
            for col in range(sheet.ncols)
            if str(sheet.cell_value(row, col)).strip()
        ]
        if not values:
            continue
        text = " | ".join(values)
        symbol_id = _symbol_id(text)
        if symbol_id and symbol_id not in seen:
            seen.add(symbol_id)
            symbols.append(
                {
                    "id": symbol_id,
                    "names": sorted(set([symbol_id, *values[:3]])),
                    "description": text[:500],
                    "source_case": case_id,
                    "source_file": str(xls_path),
                    "source_sheet": sheet_name,
                    "source_row": row + 1,
                    "text_patterns": _patterns_for_symbol(symbol_id, text),
                    "style": {},
                    "visual_templates": [],
                }
            )
        for material in re.findall(r"\b\d+[A-Z]\d+(?:[-/]\d+[A-Z])?\b", text.upper()):
            materials.append({"code": material, "source_case": case_id, "source_row": row + 1})
        if any(token in text.lower() for token in ("tracejad", "linha", "existente", "nova", "retir")):
            line_styles.append({"description": text[:500], "source_case": case_id, "source_row": row + 1})
    return {
        "case_id": case_id,
        "file_path": str(xls_path),
        "sheet_name": sheet_name,
        "symbols": symbols,
        "materials": materials,
        "line_styles": line_styles,
        "warnings": [],
    }


def _symbol_id(text: str) -> str | None:
    upper = text.upper()
    mapping = {
        "TRANSFORMADOR": ("TRANSFORMADOR", "TR ", " TR", "TRAFO"),
        "CHAVE_FUSIVEL": ("FUSIVEL", "FUSÍVEL", "FU ", " FU"),
        "CHAVE_COMANDO": ("CHAVE", "FACA", "FC ", " FC", "CF ", " CF"),
        "RELIGADOR": ("RELIGADOR", "RL ", " RL"),
        "POSTE": ("POSTE",),
        "ESTAI": ("ESTAI",),
        "ATERRAMENTO": ("ATERR",),
        "AREA_TRABALHO": ("AREA DE TRABALHO", "ÁREA DE TRABALHO", "LINHA VIVA", "LINHA MORTA"),
    }
    for symbol_id, tokens in mapping.items():
        if any(token in upper for token in tokens):
            return symbol_id
    code = re.search(r"\b(TR|FU|FC|RL|CF)\b", upper)
    if code:
        return code.group(1)
    return None


def _patterns_for_symbol(symbol_id: str, text: str) -> list[str]:
    patterns = {
        "TRANSFORMADOR": [r"\bTR\s*\d{3,8}\b", r"\bTRT?\s*\d{3,8}\b"],
        "CHAVE_FUSIVEL": [r"\bFU\s*\d{3,8}\b"],
        "CHAVE_COMANDO": [r"\bFC\s*\d{3,8}\b", r"\bCF\s*\d{3,8}\b"],
        "RELIGADOR": [r"\bRL\s*\d{3,8}\b"],
        "POSTE": [r"\bP\s*\d{1,4}\b"],
    }
    return patterns.get(symbol_id, [re.escape(text[:30])]) if text else patterns.get(symbol_id, [])

