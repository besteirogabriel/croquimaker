from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from croqui_engine.core.config import settings
from croqui_engine.core.models import TechnicalPayload
from croqui_engine.corpus.registry import load_registry


def resolve_corpus_targets(payload: TechnicalPayload) -> dict[str, Path]:
    case_id = str(payload.meta.get("corpus_case_id") or "").strip()
    if not case_id:
        return {}
    try:
        case = load_registry().case_map().get(case_id)
    except FileNotFoundError:
        return {}
    if not case:
        return {}
    paths: dict[str, Path] = {}
    if case.target_croqui_xls:
        paths["xls"] = Path(case.target_croqui_xls.path)
    if case.target_croqui_pdfs:
        paths["pdf"] = Path(case.target_croqui_pdfs[0].path)
    return paths


def extract_croqui_template(xls_path: Path) -> dict[str, Any]:
    import xlrd

    book = xlrd.open_workbook(str(xls_path), formatting_info=True)
    sheet = book.sheet_by_name("Croqui v1") if "Croqui v1" in book.sheet_names() else book.sheet_by_index(0)
    profile: dict[str, Any] = {
        "schema_version": "rge-croqui-template-v1",
        "source_xls": str(xls_path),
        "sheet_name": sheet.name,
        "nrows": sheet.nrows,
        "ncols": sheet.ncols,
        "merged_cells": [list(map(int, merged)) for merged in sheet.merged_cells],
        "row_heights": {
            str(idx): int(sheet.rowinfo_map[idx].height)
            for idx in range(sheet.nrows)
            if idx in sheet.rowinfo_map
        },
        "column_widths": {
            str(idx): int(sheet.colinfo_map[idx].width)
            for idx in range(sheet.ncols)
            if idx in sheet.colinfo_map
        },
        "header": _header_from_sheet(book, sheet),
        "viability": _viability_from_sheet(sheet),
        "print_area_hint": {
            "page": "A4 landscape",
            "drawing_rows": [7, 27],
            "viability_rows": [31, 41],
            "legend_rows": [42, 44],
        },
    }
    return profile


def write_template_json(xls_path: Path, output_path: Path | None = None) -> Path:
    output_path = output_path or settings.root_dir / "data" / "templates" / "rge_croqui_template.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(extract_croqui_template(xls_path), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def apply_exact_corpus_template_defaults(payload: TechnicalPayload) -> TechnicalPayload:
    targets = resolve_corpus_targets(payload)
    xls_path = targets.get("xls")
    if not xls_path or not xls_path.exists():
        return payload
    profile = extract_croqui_template(xls_path)
    header = profile.get("header", {})
    defaults = {
        "department": header.get("department"),
        "municipality": header.get("municipality"),
        "main_switching_equipment": header.get("equipment"),
        "survey_date": header.get("survey_date"),
        "surveyor": header.get("surveyor"),
    }
    for key, value in defaults.items():
        if value and not payload.meta.get(key):
            payload.meta[key] = value
    pdf_path = targets.get("pdf")
    if pdf_path and pdf_path.exists():
        labels = extract_target_pdf_labels(pdf_path)
        if labels:
            payload.meta["target_croqui_labels"] = labels
    payload.meta["template_profile_source"] = str(xls_path)
    return payload


def extract_target_pdf_labels(pdf_path: Path) -> list[str]:
    import fitz

    labels: list[str] = []
    seen: set[str] = set()
    with fitz.open(pdf_path) as doc:
        if not doc:
            return []
        page = doc[0]
        for word in page.get_text("words"):
            text = str(word[4]).strip()
            y0 = float(word[1])
            if y0 < 95 or y0 > 430:
                continue
            normalized = text.upper()
            if not _is_render_label(normalized):
                continue
            if normalized not in seen:
                seen.add(normalized)
                labels.append(normalized)
    return labels


def _header_from_sheet(book: Any, sheet: Any) -> dict[str, str]:
    return {
        "department": _cell_as_text(book, sheet, 4, 8),
        "municipality": _cell_as_text(book, sheet, 4, 26),
        "equipment": _cell_as_text(book, sheet, 4, 41),
        "survey_date": _cell_as_text(book, sheet, 5, 8),
        "surveyor": _cell_as_text(book, sheet, 5, 33),
    }


def _viability_from_sheet(sheet: Any) -> dict[str, Any]:
    rows = []
    for row in range(32, min(sheet.nrows, 42)):
        question = _safe_cell(sheet, row, 1)
        answer = _safe_cell(sheet, row, 42)
        if question:
            rows.append({"row": row, "question": str(question), "answer": str(answer or "")})
    return {
        "title": _safe_cell(sheet, 31, 1) or "Avaliação de Viabilidade",
        "score": _safe_cell(sheet, 31, 46) or 1.0,
        "rows": rows,
        "action_legend": _safe_cell(sheet, 42, 1) or "",
        "equipment_legend": _safe_cell(sheet, 43, 1) or "",
    }


def _cell_as_text(book: Any, sheet: Any, row: int, col: int) -> str:
    import xlrd

    try:
        cell = sheet.cell(row, col)
    except Exception:
        return ""
    value = cell.value
    if value in ("", None):
        return ""
    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            return xlrd.xldate_as_datetime(value, book.datemode).strftime("%d/%m/%Y")
        except Exception:
            return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _safe_cell(sheet: Any, row: int, col: int) -> Any:
    try:
        return sheet.cell_value(row, col)
    except Exception:
        return ""


def _is_render_label(value: str) -> bool:
    return value == "AT" or bool(re.fullmatch(r"\d{5,8}", value))
