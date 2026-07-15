from __future__ import annotations


def line_style(status: str | None = None) -> dict:
    if status in {"retirar", "referencia"}:
        return {"stroke": "#777777", "dash": [5, 3]}
    if status == "instalar":
        return {"stroke": "#0ca2f8", "dash": []}
    return {"stroke": "#222222", "dash": []}

