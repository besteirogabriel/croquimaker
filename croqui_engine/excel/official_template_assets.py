from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from croqui_engine.core.config import settings
from croqui_engine.office.libreoffice import convert_to_svg, convert_to_xlsx


def official_rge_logo_svg() -> Path:
    """Return the RGE logo embedded in the official Excel template as SVG."""
    output_dir = settings.tmp_dir / "official_template_assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "rge_logo.svg"
    if output.exists():
        return output
    template = _template_path()
    xlsx = template if template.suffix.lower() == ".xlsx" else convert_to_xlsx(template, output_dir)
    with ZipFile(xlsx) as workbook:
        media = next((name for name in workbook.namelist() if name.lower().endswith(".emf")), "")
        if not media:
            raise FileNotFoundError("O template oficial não contém o logo RGE em EMF.")
        emf = output_dir / "rge_logo.emf"
        emf.write_bytes(workbook.read(media))
    converted = convert_to_svg(emf, output_dir)
    root = ET.fromstring(converted.read_bytes())
    bbox = next((item for item in root.iter() if item.get("class") == "BoundingBox"), None)
    if bbox is not None:
        x = bbox.get("x", "0")
        y = bbox.get("y", "0")
        width = bbox.get("width", "21000")
        height = bbox.get("height", "29700")
        root.set("viewBox", f"{x} {y} {width} {height}")
        root.set("width", width)
        root.set("height", height)
        root.set("preserveAspectRatio", "xMinYMid meet")
    output.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return output


def _template_path() -> Path:
    if settings.excel_template_path:
        configured = Path(settings.excel_template_path)
        if not configured.is_absolute():
            configured = settings.root_dir / configured
        if configured.is_file():
            return configured
    corpus = Path(settings.golden_corpus_path)
    if not corpus.is_absolute():
        corpus = settings.root_dir / corpus
    candidate = next(iter(sorted(corpus.rglob("*.xls"))), None) if corpus.is_dir() else None
    if candidate is None:
        raise FileNotFoundError(
            "Configure CROQUI_EXCEL_TEMPLATE_PATH para carregar o logo RGE oficial."
        )
    return candidate
