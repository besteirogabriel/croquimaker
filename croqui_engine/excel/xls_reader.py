from __future__ import annotations

from pathlib import Path


def open_workbook(path: Path):
    import xlrd

    return xlrd.open_workbook(str(path), formatting_info=True)


def sheet_names(path: Path) -> list[str]:
    return open_workbook(path).sheet_names()


def find_sheet_name(path: Path, desired: str) -> str | None:
    desired_norm = _norm(desired)
    for name in sheet_names(path):
        if _norm(name) == desired_norm:
            return name
    for name in sheet_names(path):
        if desired_norm in _norm(name):
            return name
    return None


def _norm(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())

