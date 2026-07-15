from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from croqui_engine.core.config import settings
from croqui_engine.corpus.discovery import sha256_file


def soffice_path() -> Path | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return Path(found)
    mac_path = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    return mac_path if mac_path.exists() else None


def libreoffice_available() -> bool:
    return soffice_path() is not None


def convert_to_pdf(input_path: Path, output_dir: Path, timeout: int = 120) -> Path:
    soffice = soffice_path()
    if not soffice:
        raise RuntimeError("LibreOffice/soffice nao encontrado.")
    input_path = input_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(soffice),
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    expected = output_dir / f"{input_path.stem}.pdf"
    if result.returncode != 0 or not expected.exists():
        raise RuntimeError(
            "Falha ao converter com LibreOffice: "
            f"{result.stdout.strip()} {result.stderr.strip()}".strip()
        )
    return expected


def render_pdf_pages(
    pdf_path: Path,
    output_dir: Path,
    prefix: str,
    page_indices: list[int] | None = None,
    zoom: float = 2.0,
) -> list[Path]:
    import fitz

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        indices = page_indices if page_indices is not None else list(range(len(doc)))
        for index in indices:
            if index < 0 or index >= len(doc):
                continue
            pix = doc[index].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            out = output_dir / f"{prefix}_p{index + 1}.png"
            pix.save(out)
            paths.append(out)
    return paths


def render_simbologia_pages(case_id: str, xls_path: Path) -> list[Path]:
    digest = sha256_file(xls_path)[:16]
    out_dir = settings.root_dir / "data" / "rendered_xls" / case_id / digest
    cached = sorted(out_dir.glob("simbologia_p*.png"))
    if cached:
        return cached

    pdf_path = convert_to_pdf(xls_path, out_dir)
    page_indices = _simbologia_page_indices(pdf_path)
    return render_pdf_pages(pdf_path, out_dir, "simbologia", page_indices=page_indices, zoom=2.0)


def convert_first_sheet_to_pdf(xls_path: Path, output_pdf: Path) -> Path:
    import fitz

    tmp_dir = output_pdf.parent / ".lo_tmp"
    converted = convert_to_pdf(xls_path, tmp_dir)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(converted) as src:
        out = fitz.open()
        out.insert_pdf(src, from_page=0, to_page=0)
        out.save(output_pdf)
        out.close()
    return output_pdf


def _simbologia_page_indices(pdf_path: Path) -> list[int]:
    import fitz

    indices = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc):
            text = page.get_text("text").lower()
            if "simbologia" in text or "símbolo" in text or "simbolo" in text:
                indices.append(index)
    return indices or [0]
