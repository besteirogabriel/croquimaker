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
        "clip": (114.0, 131.0, 132.0, 150.0),
        "anchor": "center",
        "render_scale": 0.55,
        "description": "Poste existente",
    },
    "POSTE_NOVO": {
        "clip": (84.0, 159.0, 103.0, 181.0),
        "anchor": "center",
        "render_scale": 0.55,
        "description": "Poste a ser instalado novo ou a ser substituído",
    },
    "TRANSFORMADOR_RGE": {
        "clip": (334.0, 202.0, 360.0, 230.0),
        "anchor": "first",
        "render_scale": 0.62,
        "description": "Transformador da concessionária (RGE)",
    },
    "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA": {
        "clip": (60.0, 498.0, 117.0, 519.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave fusível sem abertura em carga",
    },
    "CHAVE_FUSIVEL_COM_ABERTURA_CARGA": {
        "clip": (578.0, 132.0, 634.0, 152.0),
        "anchor": "right",
        "render_scale": 0.40,
        "description": "Chave fusível com abertura em carga",
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
    return points


def _contains(outer: fitz.Rect, inner: fitz.Rect, tolerance: float = 0.05) -> bool:
    return (
        inner.x0 >= outer.x0 - tolerance
        and inner.y0 >= outer.y0 - tolerance
        and inner.x1 <= outer.x1 + tolerance
        and inner.y1 <= outer.y1 + tolerance
    )


def _select_drawings(page: fitz.Page, clip: fitz.Rect) -> list[dict]:
    selected = [
        drawing
        for drawing in page.get_drawings()
        if _contains(clip, fitz.Rect(drawing["rect"]))
        and drawing.get("items")
        and _drawing_points(drawing)
    ]
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
            if document.page_count < 3:
                raise RuntimeError("A aba Simbologia não foi exportada para as páginas esperadas")
            page = document[1]
            symbols = {}
            for name, spec in SYMBOL_SPECS.items():
                clip = fitz.Rect(spec["clip"])
                drawings = _select_drawings(page, clip)
                bounds = fitz.Rect(drawings[0]["rect"])
                for drawing in drawings[1:]:
                    bounds |= fitz.Rect(drawing["rect"])
                anchor_x, anchor_y = _anchor(spec["anchor"], drawings, bounds)
                center_x = (bounds.x0 + bounds.x1) / 2
                center_y = (bounds.y0 + bounds.y1) / 2
                heading_x = center_x - anchor_x
                heading_y = anchor_y - center_y
                if math.hypot(heading_x, heading_y) < 1e-6:
                    heading_x, heading_y = 1.0, 0.0
                symbols[name] = {
                    "description": spec["description"],
                    "sheet": "Simbologia",
                    "source_page": 2,
                    "source_clip": list(spec["clip"]),
                    "bounds": [
                        bounds.x0 - anchor_x,
                        anchor_y - bounds.y1,
                        bounds.x1 - anchor_x,
                        anchor_y - bounds.y0,
                    ],
                    "heading": [heading_x, heading_y],
                    "render_scale": spec["render_scale"],
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
        "version": 1,
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
