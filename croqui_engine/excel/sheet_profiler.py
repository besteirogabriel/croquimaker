from __future__ import annotations

from pathlib import Path

from croqui_engine.excel.xls_reader import open_workbook


def profile_workbook(path: Path) -> dict:
    book = open_workbook(path)
    return {
        "path": str(path),
        "sheet_names": book.sheet_names(),
        "sheets": [
            {
                "name": sheet.name,
                "nrows": sheet.nrows,
                "ncols": sheet.ncols,
                "merged_cells": [tuple(int(v) for v in merged) for merged in sheet.merged_cells],
                "non_empty_cells": sum(
                    1
                    for row in range(sheet.nrows)
                    for col in range(sheet.ncols)
                    if sheet.cell_value(row, col) not in ("", None)
                ),
            }
            for sheet in book.sheets()
        ],
    }

