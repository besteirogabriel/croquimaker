from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz


SYMBOL_SPECS = {
    "POSTE_EXISTENTE": {
        "symbol_page": 0,
        "clip": (114.0, 131.0, 132.0, 150.0),
        "anchor": "center",
        "render_scale": 0.55,
        "description": "Poste existente",
    },
    "POSTE_NOVO": {
        "symbol_page": 0,
        "clip": (84.0, 159.0, 103.0, 181.0),
        "anchor": "center",
        "render_scale": 0.55,
        "description": "Poste a ser instalado novo ou a ser substituído",
    },
    "CRUZAMENTO_COM_CONEXAO": {
        "symbol_page": 0,
        "clip": (50.0, 196.0, 132.0, 228.0),
        "description": "Cruzamento de condutor com conexão",
    },
    "CRUZAMENTO_SEM_CONEXAO": {
        "symbol_page": 0,
        "clip": (50.0, 234.0, 132.0, 266.0),
        "description": "Cruzamento de condutores sem conexão",
    },
    "PASSAGEM_PRIMARIO": {
        "symbol_page": 0,
        "clip": (48.0, 273.0, 138.0, 307.0),
        "description": "Passagem de condutor primário",
    },
    "PASSAGEM_SECUNDARIO": {
        "symbol_page": 0,
        "clip": (48.0, 311.0, 138.0, 344.0),
        "description": "Passagem de condutor secundário",
    },
    "PASSAGEM_PRIMARIO_SECUNDARIO": {
        "symbol_page": 0,
        "clip": (48.0, 349.0, 138.0, 382.0),
        "description": "Passagem de condutor primário e secundário",
    },
    "ENCABECAMENTO_PRIMARIO": {
        "symbol_page": 0,
        "clip": (48.0, 387.0, 138.0, 420.0),
        "description": "Encabeçamento ou mudança de bitola de condutor primário",
    },
    "ENCABECAMENTO_SECUNDARIO": {
        "symbol_page": 0,
        "clip": (48.0, 426.0, 138.0, 458.0),
        "description": "Encabeçamento ou mudança de bitola de condutor secundário",
    },
    "CHAVE_FUSIVEL_RELIGADORA": {
        "symbol_page": 0,
        "clip": (52.0, 464.0, 136.0, 496.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave fusível religadora (repetidora)",
    },
    "SECCIONAMENTO_PRIMARIO": {
        "symbol_page": 0,
        "clip": (300.0, 120.0, 400.0, 153.0),
        "description": "Seccionamento do primário",
    },
    "SECCIONAMENTO_SECUNDARIO": {
        "symbol_page": 0,
        "clip": (300.0, 158.0, 400.0, 190.0),
        "description": "Seccionamento do secundário",
    },
    "TRANSFORMADOR_RGE": {
        "symbol_page": 0,
        "clip": (334.0, 202.0, 360.0, 230.0),
        "anchor": "first",
        "render_scale": 0.62,
        "description": "Transformador da concessionária (RGE)",
    },
    "TRANSFORMADOR_PARTICULAR": {
        "symbol_page": 0,
        "clip": (318.0, 240.0, 360.0, 270.0),
        "anchor": "first",
        "render_scale": 0.62,
        "description": "Medidor primário (TOM) ou transformador particular",
    },
    "RELIGADOR": {
        "symbol_page": 0,
        "clip": (322.0, 278.0, 360.0, 305.0),
        "description": "Religador",
    },
    "SECCIONALIZADORA": {
        "symbol_page": 0,
        "clip": (322.0, 316.0, 360.0, 342.0),
        "description": "Seccionalizadora",
    },
    "BANCO_CAPACITOR": {
        "symbol_page": 0,
        "clip": (322.0, 354.0, 364.0, 383.0),
        "description": "Banco de capacitor",
    },
    "REGULADOR_TENSAO": {
        "symbol_page": 0,
        "clip": (318.0, 391.0, 368.0, 423.0),
        "description": "Regulador de tensão",
    },
    "CHAVE_OLEO_UNIPOLAR": {
        "symbol_page": 0,
        "clip": (318.0, 430.0, 368.0, 457.0),
        "description": "Chave a óleo unipolar",
    },
    "CHAVE_OLEO_TRIPOLAR": {
        "symbol_page": 0,
        "clip": (318.0, 468.0, 368.0, 495.0),
        "description": "Chave a óleo tripolar",
    },
    "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA": {
        "symbol_page": 0,
        "clip": (60.0, 498.0, 117.0, 519.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave fusível sem abertura em carga",
    },
    "CHAVE_FUSIVEL_COM_ABERTURA_CARGA": {
        "symbol_page": 0,
        "clip": (578.0, 132.0, 634.0, 152.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave fusível com abertura em carga",
    },
    "CHAVE_FACA_SEM_ABERTURA_CARGA": {
        "symbol_page": 0,
        "clip": (572.0, 166.0, 635.0, 190.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave faca sem abertura em carga",
    },
    "CHAVE_FACA_COM_ABERTURA_CARGA": {
        "symbol_page": 0,
        "clip": (572.0, 204.0, 635.0, 228.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave faca com abertura em carga",
    },
    "CHAVE_FACA_TRIPOLAR_SEM_ABERTURA_CARGA": {
        "symbol_page": 0,
        "clip": (572.0, 242.0, 635.0, 266.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave faca tripolar sem abertura em carga",
    },
    "CHAVE_FACA_TRIPOLAR_COM_ABERTURA_CARGA": {
        "symbol_page": 0,
        "clip": (572.0, 280.0, 635.0, 304.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave faca tripolar com abertura em carga",
    },
    "CHAVE_OMNI_RUPTER": {
        "symbol_page": 0,
        "clip": (572.0, 318.0, 640.0, 344.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave Omni-rupter (operação sob carga)",
    },
    "ATERRAMENTO_BT": {
        "symbol_page": 0,
        "clip": (572.0, 355.0, 640.0, 395.0),
        "description": "Aterramento temporário de baixa tensão",
    },
    "ATERRAMENTO_AT": {
        "symbol_page": 0,
        "clip": (572.0, 393.0, 640.0, 433.0),
        "description": "Aterramento temporário de alta tensão",
    },
    "REDE_SECUNDARIA_CONTINUA": {
        "symbol_page": 1,
        "clip": (48.0, 224.0, 138.0, 249.0),
        "description": "Rede secundária contínua",
    },
    "REDE_PRIMARIA_TRACEJADA": {
        "symbol_page": 1,
        "clip": (48.0, 258.0, 138.0, 286.0),
        "description": "Rede primária tracejada",
    },
    "REDE_PROJETADA_MARROM": {
        "symbol_page": 1,
        "clip": (48.0, 294.0, 138.0, 328.0),
        "description": "Rede projetada nova em marrom",
    },
    "REDE_RECONDUTORADA_AZUL": {
        "symbol_page": 1,
        "clip": (48.0, 335.0, 138.0, 368.0),
        "description": "Rede recondutorada em azul",
    },
    "REDE_COMPLEMENTADA_ROSA": {
        "symbol_page": 1,
        "clip": (48.0, 373.0, 138.0, 407.0),
        "description": "Rede complementada em rosa",
    },
    "FIM_REDE_PRIMARIA": {
        "symbol_page": 1,
        "clip": (48.0, 146.0, 138.0, 170.0),
        "description": "Fim de rede primária",
    },
    "FIM_REDE_SECUNDARIA": {
        "symbol_page": 1,
        "clip": (48.0, 187.0, 138.0, 209.0),
        "description": "Fim de rede secundária",
    },
    "ELEMENTO_DESLOCAR": {
        "symbol_page": 1,
        "clip": (308.0, 146.0, 392.0, 175.0),
        "description": "Elemento a deslocar",
    },
    "ELEMENTO_RETIRAR": {
        "symbol_page": 1,
        "clip": (310.0, 187.0, 390.0, 210.0),
        "description": "Elemento a retirar",
    },
    "ESTAI": {
        "symbol_page": 1,
        "clip": (300.0, 218.0, 400.0, 250.0),
        "description": "Estai",
    },
    "CORTE_FORA_ESCALA": {
        "symbol_page": 1,
        "clip": (298.0, 289.0, 400.0, 320.0),
        "description": "Corte para indicar desenho fora de escala",
    },
    "ABERTURA_PASSAGEM_11N4": {
        "symbol_page": 1,
        "clip": (558.0, 151.0, 638.0, 188.0),
        "description": "Abertura de passagem 11N4",
    },
    "ABERTURA_PASSAGEM_8_11": {
        "symbol_page": 1,
        "clip": (558.0, 205.0, 638.0, 244.0),
        "description": "Abertura de passagem 8 às 11",
    },
}


def _convert_to_pdf(workbook: Path, output_dir: Path) -> Path:
    soffice = shutil.which("soffice")
    if not soffice:
        raise RuntimeError("soffice não encontrado; não é possível ler o XLS de referência")
    profile = output_dir / "libreoffice-profile"
    profile.mkdir()
    subprocess.run(
        [
            soffice,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(workbook),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    converted = output_dir / f"{workbook.stem}.pdf"
    if not converted.exists():
        raise RuntimeError(f"LibreOffice não gerou {converted}")
    return converted


def _point(value) -> tuple[float, float]:
    if isinstance(value, fitz.Point):
        return float(value.x), float(value.y)
    raise TypeError(f"Coordenada vetorial não suportada: {type(value)!r}")


def _drawing_points(drawing: dict) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for item in drawing.get("items", []):
        if item[0] in {"l", "c"}:
            points.extend(_point(value) for value in item[1:])
        elif item[0] == "re":
            rect = fitz.Rect(item[1])
            points.extend(
                [
                    (rect.x0, rect.y0),
                    (rect.x1, rect.y0),
                    (rect.x1, rect.y1),
                    (rect.x0, rect.y1),
                ]
            )
        elif item[0] == "qu":
            quad = fitz.Quad(item[1])
            points.extend(
                [
                    _point(quad.ul),
                    _point(quad.ur),
                    _point(quad.lr),
                    _point(quad.ll),
                ]
            )
    return points


def _contains(outer: fitz.Rect, inner: fitz.Rect, tolerance: float = 0.05) -> bool:
    return (
        inner.x0 >= outer.x0 - tolerance
        and inner.y0 >= outer.y0 - tolerance
        and inner.x1 <= outer.x1 + tolerance
        and inner.y1 <= outer.y1 + tolerance
    )


def _select_drawings(page: fitz.Page, clip: fitz.Rect) -> list[dict]:
    selected = []
    for drawing in page.get_drawings():
        bounds = fitz.Rect(drawing["rect"])
        center = fitz.Point(
            (bounds.x0 + bounds.x1) / 2,
            (bounds.y0 + bounds.y1) / 2,
        )
        if not clip.contains(center):
            continue
        if not drawing.get("items") or not _drawing_points(drawing):
            continue
        fill = drawing.get("fill")
        is_plain_cell_fill = (
            drawing.get("color") is None
            and fill is not None
            and all(float(channel) >= 0.98 for channel in fill[:3])
            and (
                bounds.width >= clip.width * 0.75
                or bounds.height >= clip.height * 0.85
            )
        )
        if is_plain_cell_fill:
            continue
        selected.append(drawing)
    if not selected:
        raise RuntimeError(f"Nenhum vetor encontrado na região {tuple(clip)}")
    return selected


def _anchor(
    mode: str,
    drawings: list[dict],
    bounds: fitz.Rect,
) -> tuple[float, float]:
    points = [point for drawing in drawings for point in _drawing_points(drawing)]
    if mode == "center":
        return (bounds.x0 + bounds.x1) / 2, (bounds.y0 + bounds.y1) / 2
    if mode == "first":
        return points[0]
    if mode == "right":
        return max(points, key=lambda point: (point[0], -abs(point[1] - bounds.y0)))
    raise ValueError(f"Modo de âncora desconhecido: {mode}")


def _rgb(value) -> str | None:
    if value is None:
        return None
    channels = [round(float(channel) * 255) for channel in value[:3]]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _commands(
    drawing: dict,
    anchor_x: float,
    anchor_y: float,
) -> list[list[float | str]]:
    result: list[list[float | str]] = []
    current: tuple[float, float] | None = None

    def local(value) -> tuple[float, float]:
        x, y = _point(value)
        return x - anchor_x, anchor_y - y

    for item in drawing.get("items", []):
        op = item[0]
        if op == "l":
            start = local(item[1])
            end = local(item[2])
            if current is None or math.dist(current, start) > 1e-5:
                result.append(["M", *start])
            if math.dist(start, end) > 1e-5:
                result.append(["L", *end])
            current = end
        elif op == "c":
            start = local(item[1])
            control_1 = local(item[2])
            control_2 = local(item[3])
            end = local(item[4])
            if current is None or math.dist(current, start) > 1e-5:
                result.append(["M", *start])
            result.append(["C", *control_1, *control_2, *end])
            current = end
        elif op == "re":
            rect = fitz.Rect(item[1])
            corners = [
                local(fitz.Point(rect.x0, rect.y0)),
                local(fitz.Point(rect.x1, rect.y0)),
                local(fitz.Point(rect.x1, rect.y1)),
                local(fitz.Point(rect.x0, rect.y1)),
            ]
            result.append(["M", *corners[0]])
            result.extend(["L", *corner] for corner in corners[1:])
            result.append(["Z"])
            current = corners[0]
        elif op == "qu":
            quad = fitz.Quad(item[1])
            corners = [local(point) for point in (quad.ul, quad.ur, quad.lr, quad.ll)]
            result.append(["M", *corners[0]])
            result.extend(["L", *corner] for corner in corners[1:])
            result.append(["Z"])
            current = corners[0]
        else:
            raise RuntimeError(f"Operação vetorial não suportada: {op}")

    first = next((row[1:3] for row in result if row[0] == "M"), None)
    if first and current and math.dist(tuple(first), current) <= 1e-4:
        result.append(["Z"])
    return result


def extract_catalog(workbook: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="croquimaker-rge-symbols-") as tmp:
        pdf_path = _convert_to_pdf(workbook, Path(tmp))
        with fitz.open(pdf_path) as document:
            symbol_pages = [
                page_no
                for page_no, page in enumerate(document)
                if "simbologia" in page.get_text("text").lower()
            ]
            if len(symbol_pages) < 2:
                raise RuntimeError("A aba Simbologia não foi exportada para as páginas esperadas")
            symbols = {}
            for name, spec in SYMBOL_SPECS.items():
                page_no = symbol_pages[int(spec.get("symbol_page", 0))]
                page = document[page_no]
                clip = fitz.Rect(spec["clip"])
                drawings = _select_drawings(page, clip)
                bounds = fitz.Rect(drawings[0]["rect"])
                for drawing in drawings[1:]:
                    bounds |= fitz.Rect(drawing["rect"])
                anchor_x, anchor_y = _anchor(
                    str(spec.get("anchor", "center")),
                    drawings,
                    bounds,
                )
                center_x = (bounds.x0 + bounds.x1) / 2
                center_y = (bounds.y0 + bounds.y1) / 2
                heading_x = center_x - anchor_x
                heading_y = anchor_y - center_y
                if math.hypot(heading_x, heading_y) < 1e-6:
                    heading_x, heading_y = 1.0, 0.0
                symbols[name] = {
                    "description": spec["description"],
                    "sheet": "Simbologia",
                    "source_page": page_no + 1,
                    "source_clip": list(spec["clip"]),
                    "bounds": [
                        bounds.x0 - anchor_x,
                        anchor_y - bounds.y1,
                        bounds.x1 - anchor_x,
                        anchor_y - bounds.y0,
                    ],
                    "heading": [heading_x, heading_y],
                    "render_scale": float(spec.get("render_scale", 0.48)),
                    "paths": [
                        {
                            "stroke": _rgb(drawing.get("color")),
                            "fill": _rgb(drawing.get("fill")),
                            "width": float(drawing.get("width") or 0.0),
                            "commands": _commands(drawing, anchor_x, anchor_y),
                        }
                        for drawing in drawings
                    ],
                }

    source_bytes = workbook.read_bytes()
    return {
        "version": 2,
        "source": {
            "workbook": "data/templates/croqui_template.xls",
            "sheet": "Simbologia",
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "method": "vetores da aba Simbologia exportados pelo LibreOffice e lidos pelo PyMuPDF",
        },
        "symbols": symbols,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path("data/templates/croqui_template.xls"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/symbols/rge_symbol_catalog.json"),
    )
    args = parser.parse_args()
    catalog = extract_catalog(args.workbook.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
