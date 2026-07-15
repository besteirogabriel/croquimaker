from __future__ import annotations

from pathlib import Path

from croqui_engine.core.models_v2 import EvidenceRef
from croqui_engine.ground_truth.models import XlsSheetProfile


def extract_target_xls(case_id: str, xls_path: Path, max_cells_per_sheet: int = 350) -> dict:
    import xlrd

    workbook = xlrd.open_workbook(str(xls_path), formatting_info=True)
    profiles: list[XlsSheetProfile] = []
    for sheet in workbook.sheets():
        cells = []
        for row_idx in range(sheet.nrows):
            for col_idx in range(sheet.ncols):
                value = sheet.cell_value(row_idx, col_idx)
                if value in ("", None):
                    continue
                if len(cells) < max_cells_per_sheet:
                    cells.append(
                        {
                            "row": row_idx,
                            "col": col_idx,
                            "cell_ref": _cell_ref(row_idx, col_idx),
                            "value": str(value),
                            "ctype": int(sheet.cell_type(row_idx, col_idx)),
                            "evidence": EvidenceRef(
                                source="TARGET_XLS",
                                case_id=case_id,
                                file_path=str(xls_path),
                                sheet_name=sheet.name,
                                cell_ref=_cell_ref(row_idx, col_idx),
                                text=str(value),
                            ).as_dict(),
                        }
                    )
        profiles.append(
            XlsSheetProfile(
                name=sheet.name,
                nrows=sheet.nrows,
                ncols=sheet.ncols,
                non_empty_cells=sum(
                    1
                    for row_idx in range(sheet.nrows)
                    for col_idx in range(sheet.ncols)
                    if sheet.cell_value(row_idx, col_idx) not in ("", None)
                ),
                merged_cells=[tuple(int(v) for v in merged) for merged in sheet.merged_cells],
                cells=cells,
            )
        )

    return {
        "file_path": str(xls_path),
        "sheet_names": workbook.sheet_names(),
        "sheets": [profile.as_dict() for profile in profiles],
    }


def _cell_ref(row: int, col: int) -> str:
    col_num = col + 1
    letters = ""
    while col_num:
        col_num, remainder = divmod(col_num - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row + 1}"

