from __future__ import annotations

import base64
import json
import re
import shutil
from pathlib import Path

from croqui_engine.excel.native_graph_exporter import export_native_graph_xlsx
from croqui_engine.excel.official_template_assets import official_rge_logo_svg
from croqui_engine.graph.croqui_graph import (
    CroquiGraph,
    validate_excel_placement_plan_for_export,
)
from croqui_engine.office.libreoffice import convert_first_sheet_to_pdf, convert_to_xls
from croqui_engine.symbols.official_symbol_assets import default_symbol_assets_dir


def export_from_excel_placement_plan(
    graph: CroquiGraph,
    svg_preview: str,
    output_dir: Path,
) -> dict[str, Path]:
    """Create every final artifact from the official editable workbook.

    The SVG is stored only as an editor preview. It is never used to render the
    PDF or either spreadsheet artifact.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    graph.validation = validate_excel_placement_plan_for_export(graph)
    graph_path = output_dir / "edited_croqui_graph.json"
    svg_path = output_dir / "croqui_editor_preview.svg"
    pdf_path = output_dir / "croqui_final.pdf"
    png_path = output_dir / "croqui_final.png"
    xls_path = output_dir / "croqui_final.xls"
    xlsx_path = output_dir / "croqui_final.xlsx"
    report_path = output_dir / "output_validation_report.json"

    graph_path.write_text(
        json.dumps(graph.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    svg_path.write_text(_embed_official_assets(svg_preview), encoding="utf-8")

    # Canonical route: official XLSX workbook -> first-sheet PDF. The legacy
    # XLS is a second downloadable representation of that same workbook.
    # There is intentionally no raster/SVG spreadsheet fallback.
    export_native_graph_xlsx(graph, xlsx_path)
    converted_xls = convert_to_xls(xlsx_path, output_dir)
    if converted_xls != xls_path:
        shutil.copy2(converted_xls, xls_path)
    convert_first_sheet_to_pdf(xlsx_path, pdf_path)
    _pdf_to_png(pdf_path, png_path)
    _write_validation_report(graph, report_path)
    return {
        "graph": graph_path,
        "svg": svg_path,
        "pdf": pdf_path,
        "png": png_path,
        "xls": xls_path,
        "xlsx": xlsx_path,
        "validation_report": report_path,
    }


def export_from_croqui_graph_svg(
    graph: CroquiGraph,
    svg: str,
    output_dir: Path,
) -> dict[str, Path]:
    """Compatibility wrapper for older API callers.

    Despite the historical name, the final PDF is produced only from the
    official Excel workbook.
    """
    return export_from_excel_placement_plan(graph, svg, output_dir)


def _embed_official_assets(svg: str) -> str:
    if not svg:
        return ""
    assets_dir = default_symbol_assets_dir().resolve()

    def replace(match: re.Match[str]) -> str:
        quote = match.group("quote")
        filename = Path(match.group("path")).name
        asset = (assets_dir / filename).resolve()
        if asset.parent != assets_dir or not asset.is_file():
            return match.group(0)
        encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
        return f'{match.group("attr")}={quote}data:image/png;base64,{encoded}{quote}'

    embedded = re.sub(
        r'(?P<attr>(?:xlink:)?href)=(?P<quote>["\'])(?P<path>/static/img/symbols/official/[^"\']+)(?P=quote)',
        replace,
        svg,
    )
    if "/api/assets/rge-logo.svg" in embedded:
        try:
            logo = base64.b64encode(official_rge_logo_svg().read_bytes()).decode("ascii")
            embedded = embedded.replace(
                "/api/assets/rge-logo.svg",
                f"data:image/svg+xml;base64,{logo}",
            )
        except (FileNotFoundError, RuntimeError, OSError):
            pass
    return embedded


def _pdf_to_png(pdf_path: Path, output_path: Path) -> Path:
    import fitz

    with fitz.open(pdf_path) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(output_path)
    return output_path


def _write_validation_report(graph: CroquiGraph, output_path: Path) -> Path:
    final_allowed = (
        graph.validation.status == "final_candidate" and not graph.validation.blockingErrors
    )
    report = {
        "contract": {
            "project_id": graph.id,
            "expected_or_selected_main_equipment": graph.header.equipamento,
            "selected_equipment_type": graph.mainEquipment.type,
            "selected_equipment_code": graph.mainEquipment.code,
            "selected_equipment_confidence": graph.mainEquipment.confidence,
            "primary_focus_code": graph.mainEquipment.code,
            "focus_validated": final_allowed,
        },
        "generated": {
            "source": "official_excel_workbook",
            "pdf_source": "croqui_final.xlsx:first_sheet",
            "pdf_header_equipment": graph.header.equipamento,
            "xls_header_equipment": graph.header.equipamento,
            "primary_focus_code": graph.mainEquipment.code,
            "visible_codes": [node.code for node in graph.nodes if node.code],
            "excluded_codes": [],
        },
        "validation": {
            "status": "PASSED" if final_allowed else "BLOCKED",
            "output_status": graph.validation.status,
            "final_output_allowed": final_allowed,
            "blocking_errors": graph.validation.blockingErrors,
            "warnings": graph.validation.warnings,
        },
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
