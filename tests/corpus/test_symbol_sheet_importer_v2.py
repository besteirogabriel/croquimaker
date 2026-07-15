from pathlib import Path

import xlwt

from croqui_engine.excel.symbol_sheet_importer import import_symbol_sheet


def _make_symbol_xls(path: Path) -> None:
    book = xlwt.Workbook()
    sheet = book.add_sheet("Simbologia")
    sheet.write(0, 0, "Transformador TR 123456")
    sheet.write(1, 0, "Poste")
    sheet.write(2, 0, "Linha existente tracejada")
    sheet.write(3, 0, "3E70-1A")
    book.save(str(path))


def test_import_symbol_sheet_extracts_symbols_materials_and_line_styles(tmp_path):
    xls_path = tmp_path / "Croqui TR 123456.xls"
    _make_symbol_xls(xls_path)

    imported = import_symbol_sheet("case-001", xls_path)

    symbol_ids = {symbol["id"] for symbol in imported["symbols"]}
    material_codes = {material["code"] for material in imported["materials"]}

    assert imported["sheet_name"] == "Simbologia"
    assert {"TRANSFORMADOR", "POSTE"} <= symbol_ids
    assert "3E70-1A" in material_codes
    assert imported["line_styles"]
    assert imported["warnings"] == []
