from __future__ import annotations

from pathlib import Path


def profile_pdf(path: Path) -> dict:
    import fitz

    with fitz.open(path) as doc:
        return {
            "path": str(path),
            "page_count": len(doc),
            "pages": [
                {"index": idx, "width": float(page.rect.width), "height": float(page.rect.height)}
                for idx, page in enumerate(doc)
            ],
        }

