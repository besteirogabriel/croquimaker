from __future__ import annotations

import json

import pytest

from croqui_engine.excel.native_graph_exporter import (
    NativeExcelTemplateUnavailable,
    _symbol_name,
)
from croqui_engine.generators import svg_graph_exporter as exporter
from croqui_engine.graph.croqui_graph import (
    CroquiEdge,
    CroquiGraph,
    CroquiGraphHeader,
    CroquiMainEquipment,
    CroquiNode,
)


def _graph() -> CroquiGraph:
    return CroquiGraph(
        id="synthetic-canonical-export",
        header=CroquiGraphHeader(equipamento="FU 000000"),
        mainEquipment=CroquiMainEquipment(
            id="main-device",
            type="FU",
            code="000000",
            confidence=0.9,
        ),
        nodes=[
            CroquiNode(id="source", kind="pole", x=100, y=200),
            CroquiNode(
                id="main-device",
                kind="switch",
                equipmentType="FU",
                code="000000",
                isMain=True,
                x=240,
                y=200,
            ),
        ],
        edges=[CroquiEdge(id="network", source="source", target="main-device")],
    )


def test_pdf_is_derived_from_official_excel_not_svg(monkeypatch, tmp_path):
    calls: list[str] = []

    def fake_native(graph, output_path):
        calls.append("official_excel")
        output_path.write_bytes(b"OFFICIAL-EXCEL-OBJECTS")
        return output_path

    def fake_xls(input_path, output_dir):
        calls.append("xls")
        assert input_path.read_bytes() == b"OFFICIAL-EXCEL-OBJECTS"
        output_path = output_dir / "croqui_final.xls"
        output_path.write_bytes(b"OFFICIAL-XLS")
        return output_path

    def fake_pdf(input_path, output_path):
        calls.append("pdf-from-xlsx")
        assert input_path.read_bytes() == b"OFFICIAL-EXCEL-OBJECTS"
        output_path.write_bytes(b"PDF-FROM-OFFICIAL-XLSX")
        return output_path

    def fake_png(input_path, output_path):
        calls.append("png-from-pdf")
        assert input_path.read_bytes() == b"PDF-FROM-OFFICIAL-XLSX"
        output_path.write_bytes(b"PNG-FROM-PDF")
        return output_path

    monkeypatch.setattr(exporter, "export_native_graph_xlsx", fake_native)
    monkeypatch.setattr(exporter, "convert_to_xls", fake_xls)
    monkeypatch.setattr(exporter, "convert_first_sheet_to_pdf", fake_pdf)
    monkeypatch.setattr(exporter, "_pdf_to_png", fake_png)

    outputs = exporter.export_from_excel_placement_plan(
        _graph(),
        "<svg>PREVIEW-ONLY-MARKER</svg>",
        tmp_path,
    )
    report = json.loads(outputs["validation_report"].read_text(encoding="utf-8"))

    assert calls == ["official_excel", "xls", "pdf-from-xlsx", "png-from-pdf"]
    assert b"PREVIEW-ONLY-MARKER" not in outputs["pdf"].read_bytes()
    assert b"PREVIEW-ONLY-MARKER" not in outputs["xlsx"].read_bytes()
    assert report["generated"]["source"] == "official_excel_workbook"
    assert report["generated"]["pdf_source"] == "croqui_final.xlsx:first_sheet"


@pytest.mark.parametrize(
    ("equipment_type", "official_object"),
    [
        ("TR", "AutoShape 238"),
        ("FU", "Group 729"),
        ("FC", "Group 302"),
        ("RL", "Text Box 245"),
        ("RG", "Group 260"),
        ("OL", "Text Box 261"),
        ("SC", "Text Box 247"),
    ],
)
def test_each_equipment_uses_its_exact_official_symbol(equipment_type, official_object):
    node = CroquiNode(
        id="synthetic-device",
        kind="transformer" if equipment_type == "TR" else "switch",
        equipmentType=equipment_type,
    )

    assert _symbol_name(node) == official_object


def test_unknown_equipment_never_falls_back_to_the_wrong_icon():
    node = CroquiNode(id="unknown-device", kind="equipment", equipmentType="UNKNOWN")

    with pytest.raises(NativeExcelTemplateUnavailable):
        _symbol_name(node)
