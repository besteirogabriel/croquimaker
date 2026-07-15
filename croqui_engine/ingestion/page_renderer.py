from __future__ import annotations

from pathlib import Path


def render_page_png(pdf_path: Path, page_index: int, output_path: Path, dpi: int = 120) -> Path:
    import fitz

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as doc:
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        pix.save(output_path)
    return output_path


def render_all_thumbnails(pdf_path: Path, output_dir: Path) -> list[Path]:
    import fitz

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        for index in range(doc.page_count):
            target = output_dir / f"page_{index + 1:03d}.png"
            page = doc[index]
            pix = page.get_pixmap(dpi=120, alpha=False)
            pix.save(target)
            paths.append(target)
    return paths
