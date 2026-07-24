from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from reportlab.lib.colors import Color, HexColor
from reportlab.pdfgen.canvas import Canvas


CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "symbols"
    / "rge_symbol_catalog.json"
)


@lru_cache(maxsize=1)
def load_rge_symbol_catalog() -> dict:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if catalog.get("source", {}).get("sheet") != "Simbologia":
        raise ValueError("Catálogo RGE não foi extraído da aba Simbologia")
    if not catalog.get("symbols"):
        raise ValueError("Catálogo RGE está vazio")
    return catalog


def symbol_for_equipment(kind: str) -> str | None:
    normalized = str(kind).strip().upper()
    aliases = {
        "TRANSFORMADOR_RGE": "TRANSFORMADOR_RGE",
        "TRANSFORMADOR_PARTICULAR": "TRANSFORMADOR_PARTICULAR",
        "MEDIDOR_PRIMARIO": "TRANSFORMADOR_PARTICULAR",
        "CHAVE_FUSIVEL_RELIGADORA": "CHAVE_FUSIVEL_RELIGADORA",
        "CHAVE_FUSIVEL_COM_CARGA": "CHAVE_FUSIVEL_COM_ABERTURA_CARGA",
        "CHAVE_FUSIVEL_COM_ABERTURA": "CHAVE_FUSIVEL_COM_ABERTURA_CARGA",
        "CHAVE_FUSIVEL_SEM_CARGA": "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA",
        "CHAVE_FUSIVEL_SEM_ABERTURA": "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA",
        "CHAVE_FACA_COM_CARGA": "CHAVE_FACA_COM_ABERTURA_CARGA",
        "CHAVE_FACA_COM_ABERTURA": "CHAVE_FACA_COM_ABERTURA_CARGA",
        "CHAVE_FACA_SEM_CARGA": "CHAVE_FACA_SEM_ABERTURA_CARGA",
        "CHAVE_FACA_SEM_ABERTURA": "CHAVE_FACA_SEM_ABERTURA_CARGA",
        "CHAVE_FACA_TRIPOLAR_COM_CARGA": "CHAVE_FACA_TRIPOLAR_COM_ABERTURA_CARGA",
        "CHAVE_FACA_TRIPOLAR_COM_ABERTURA": "CHAVE_FACA_TRIPOLAR_COM_ABERTURA_CARGA",
        "CHAVE_FACA_TRIPOLAR_SEM_CARGA": "CHAVE_FACA_TRIPOLAR_SEM_ABERTURA_CARGA",
        "CHAVE_FACA_TRIPOLAR_SEM_ABERTURA": "CHAVE_FACA_TRIPOLAR_SEM_ABERTURA_CARGA",
        "CHAVE_OMNI_RUPTER": "CHAVE_OMNI_RUPTER",
        "RELIGADOR": "RELIGADOR",
        "SECCIONALIZADORA": "SECCIONALIZADORA",
        "BANCO_CAPACITOR": "BANCO_CAPACITOR",
        "REGULADOR_TENSAO": "REGULADOR_TENSAO",
        "CHAVE_OLEO_UNIPOLAR": "CHAVE_OLEO_UNIPOLAR",
        "CHAVE_OLEO_TRIPOLAR": "CHAVE_OLEO_TRIPOLAR",
        "ATERRAMENTO_BT": "ATERRAMENTO_BT",
        "ATERRAMENTO_AT": "ATERRAMENTO_AT",
        "SECCIONAMENTO_PRIMARIO": "SECCIONAMENTO_PRIMARIO",
        "SECCIONAMENTO_SECUNDARIO": "SECCIONAMENTO_SECUNDARIO",
        "PASSAGEM_PRIMARIO": "PASSAGEM_PRIMARIO",
        "PASSAGEM_SECUNDARIO": "PASSAGEM_SECUNDARIO",
        "PASSAGEM_PRIMARIO_SECUNDARIO": "PASSAGEM_PRIMARIO_SECUNDARIO",
        "FIM_REDE_PRIMARIA": "FIM_REDE_PRIMARIA",
        "FIM_REDE_SECUNDARIA": "FIM_REDE_SECUNDARIA",
        "CRUZAMENTO_COM_CONEXAO": "CRUZAMENTO_COM_CONEXAO",
        "CRUZAMENTO_SEM_CONEXAO": "CRUZAMENTO_SEM_CONEXAO",
        "ENCABECAMENTO_PRIMARIO": "ENCABECAMENTO_PRIMARIO",
        "ENCABECAMENTO_SECUNDARIO": "ENCABECAMENTO_SECUNDARIO",
        "ELEMENTO_RETIRAR": "ELEMENTO_RETIRAR",
        "ELEMENTO_DESLOCAR": "ELEMENTO_DESLOCAR",
        "ESTAI": "ESTAI",
    }
    if normalized in aliases:
        return aliases[normalized]
    if "TRANSFORMADOR" in normalized:
        return "TRANSFORMADOR_RGE"
    if "FUS" in normalized:
        return "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA"
    return None


def _source_color(value: str | None) -> Color | None:
    return HexColor(value) if value else None


def _draw_path(
    canvas: Canvas,
    path_spec: dict,
    *,
    scale: float,
) -> None:
    path = canvas.beginPath()
    for command in path_spec["commands"]:
        op = command[0]
        if op == "M":
            path.moveTo(float(command[1]), float(command[2]))
        elif op == "L":
            path.lineTo(float(command[1]), float(command[2]))
        elif op == "C":
            path.curveTo(*[float(value) for value in command[1:]])
        elif op == "Z":
            path.close()
        else:
            raise ValueError(f"Comando vetorial RGE desconhecido: {op}")

    # Stroke and fill are copied literally from the Simbologia sheet. Runtime
    # state such as INSTALAR must never manufacture a color variant that is not
    # present in the reference workbook.
    stroke = _source_color(path_spec.get("stroke"))
    fill = _source_color(path_spec.get("fill"))
    if stroke is not None:
        canvas.setStrokeColor(stroke)
        canvas.setLineWidth(max(0.35 / scale, float(path_spec.get("width") or 0.0)))
    if fill is not None:
        canvas.setFillColor(fill)
    canvas.drawPath(path, stroke=int(stroke is not None), fill=int(fill is not None))


def draw_rge_symbol(
    canvas: Canvas,
    symbol_name: str,
    x: float,
    y: float,
    *,
    direction: tuple[float, float] = (1.0, 0.0),
    scale: float | None = None,
) -> float:
    """Draw a vector copied from the RGE workbook and return its outward extent."""

    symbol = load_rge_symbol_catalog()["symbols"][symbol_name]
    dx, dy = direction
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        dx, dy = 1.0, 0.0
    else:
        dx, dy = dx / length, dy / length
    heading_x, heading_y = symbol["heading"]
    rotation = math.degrees(math.atan2(dy, dx) - math.atan2(heading_y, heading_x))
    render_scale = float(scale if scale is not None else symbol["render_scale"])

    canvas.saveState()
    canvas.translate(x, y)
    canvas.rotate(rotation)
    canvas.scale(render_scale, render_scale)
    for path_spec in symbol["paths"]:
        _draw_path(
            canvas,
            path_spec,
            scale=render_scale,
        )
    canvas.restoreState()

    bounds = symbol["bounds"]
    return max(
        math.hypot(float(bounds[0]), float(bounds[1])),
        math.hypot(float(bounds[0]), float(bounds[3])),
        math.hypot(float(bounds[2]), float(bounds[1])),
        math.hypot(float(bounds[2]), float(bounds[3])),
    ) * render_scale
