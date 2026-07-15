from __future__ import annotations

from pathlib import Path

from croqui_engine.office.libreoffice import convert_to_pdf


def generate_simbologia_svg_from_xls(xls_path: Path, output_path: Path) -> Path:
    return generate_simbologia_svg_pages_from_xls(xls_path, output_path)[0]


def generate_simbologia_svg_pages_from_xls(xls_path: Path, output_path: Path) -> list[Path]:
    import fitz

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_path.parent / ".simbologia_tmp"
    pdf_path = convert_to_pdf(xls_path, tmp_dir)
    paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        for position, page_index in enumerate(_find_simbologia_pages(doc), start=1):
            page_output = output_path if position == 1 else output_path.with_name(
                f"{output_path.stem}_p{position}{output_path.suffix}"
            )
            svg = doc[page_index].get_svg_image(text_as_path=True)
            page_output.write_text(_sanitize_svg(svg), encoding="utf-8")
            paths.append(page_output)
    return paths


def _find_simbologia_pages(doc) -> list[int]:
    indices = []
    for index, page in enumerate(doc):
        text = page.get_text("text").lower()
        if "simbologia" in text or "símbolo" in text or "simbolo" in text:
            indices.append(index)
    return indices or [0]


def _sanitize_svg(svg: str) -> str:
    # The source workbook is used only to derive the local static visual catalog.
    return svg.replace("\r\n", "\n").replace("\r", "\n")
