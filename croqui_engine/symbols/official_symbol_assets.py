from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from croqui_engine.core.config import settings
from croqui_engine.office.libreoffice import convert_to_pdf


@dataclass(frozen=True)
class SymbolAssetSpec:
    id: str
    symbol_page: int
    rect: tuple[float, float, float, float]


ASSET_SPECS: tuple[SymbolAssetSpec, ...] = (
    SymbolAssetSpec("POSTE_EXISTENTE", 0, (76, 134, 112, 154)),
    SymbolAssetSpec("POSTE_NOVO_SUBSTITUIR", 0, (80, 174, 104, 191)),
    SymbolAssetSpec("CRUZAMENTO_COM_CONEXAO", 0, (70, 213, 115, 237)),
    SymbolAssetSpec("CRUZAMENTO_SEM_CONEXAO", 0, (70, 251, 115, 276)),
    SymbolAssetSpec("PASSAGEM_PRIMARIO", 0, (48, 292, 138, 310)),
    SymbolAssetSpec("PASSAGEM_SECUNDARIO", 0, (48, 330, 138, 350)),
    SymbolAssetSpec("PASSAGEM_PRIMARIO_SECUNDARIO", 0, (48, 368, 138, 388)),
    SymbolAssetSpec("ENCABECAMENTO_PRIMARIO", 0, (52, 402, 132, 428)),
    SymbolAssetSpec("ENCABECAMENTO_SECUNDARIO", 0, (52, 440, 132, 466)),
    SymbolAssetSpec("CHAVE_FUSIVEL_RELIGADORA", 0, (58, 475, 136, 488)),
    SymbolAssetSpec("CHAVE_FUSIVEL_SEM_ABERTURA", 0, (58, 513, 132, 524)),
    SymbolAssetSpec("SECCIONAMENTO_PRIMARIO", 0, (300, 139, 392, 158)),
    SymbolAssetSpec("SECCIONAMENTO_SECUNDARIO", 0, (300, 177, 392, 196)),
    SymbolAssetSpec("TRANSFORMADOR_RGE", 0, (318, 211, 342, 231)),
    SymbolAssetSpec("TRANSFORMADOR_PARTICULAR", 0, (318, 249, 342, 269)),
    SymbolAssetSpec("RELIGADOR", 0, (322, 286, 360, 302)),
    SymbolAssetSpec("SECCIONALIZADORA", 0, (322, 324, 360, 340)),
    SymbolAssetSpec("BANCO_CAPACITOR", 0, (322, 362, 364, 383)),
    SymbolAssetSpec("REGULADOR_TENSAO", 0, (318, 400, 368, 423)),
    SymbolAssetSpec("CHAVE_OLEO_UNIPOLAR", 0, (328, 438, 356, 456)),
    SymbolAssetSpec("CHAVE_OLEO_TRIPOLAR", 0, (328, 476, 356, 494)),
    SymbolAssetSpec("CHAVE_FUSIVEL_COM_ABERTURA", 0, (572, 135, 632, 154)),
    SymbolAssetSpec("CHAVE_FACA_SEM_ABERTURA", 0, (572, 173, 632, 190)),
    SymbolAssetSpec("CHAVE_FACA_COM_ABERTURA", 0, (572, 211, 632, 228)),
    SymbolAssetSpec("CHAVE_FACA_TRIPOLAR_SEM_ABERTURA", 0, (572, 249, 632, 266)),
    SymbolAssetSpec("CHAVE_FACA_TRIPOLAR_COM_ABERTURA", 0, (572, 287, 632, 304)),
    SymbolAssetSpec("CHAVE_OMNI_RUPTER", 0, (572, 325, 640, 344)),
    SymbolAssetSpec("ATERRAMENTO_BT", 0, (582, 363, 626, 395)),
    SymbolAssetSpec("ATERRAMENTO_AT", 0, (582, 401, 626, 433)),
    SymbolAssetSpec("AREA_TRABALHO", 0, (574, 439, 634, 461)),
    SymbolAssetSpec("FIM_REDE_PRIMARIA", 1, (48, 146, 138, 170)),
    SymbolAssetSpec("FIM_REDE_SECUNDARIA", 1, (48, 187, 138, 209)),
    SymbolAssetSpec("REDE_SECUNDARIA_CONTINUA", 1, (48, 232, 138, 246)),
    SymbolAssetSpec("REDE_PRIMARIA_TRACEJADA", 1, (48, 268, 138, 283)),
    SymbolAssetSpec("REDE_PROJETADA_MARROM", 1, (48, 305, 138, 328)),
    SymbolAssetSpec("REDE_RECONDUTORADA_AZUL", 1, (48, 346, 138, 368)),
    SymbolAssetSpec("REDE_COMPLEMENTADA_ROSA", 1, (48, 384, 138, 407)),
    SymbolAssetSpec("ELEMENTO_DESLOCAR", 1, (308, 146, 392, 175)),
    SymbolAssetSpec("ELEMENTO_RETIRAR", 1, (310, 187, 390, 210)),
    SymbolAssetSpec("ESTAI", 1, (314, 226, 382, 248)),
    SymbolAssetSpec("EQUIPAMENTO_INSTALAR", 1, (298, 260, 400, 281)),
    SymbolAssetSpec("CORTE_FORA_ESCALA", 1, (298, 296, 400, 320)),
    SymbolAssetSpec("ABERTURA_PASSAGEM_11N4", 1, (558, 151, 638, 188)),
    SymbolAssetSpec("ABERTURA_PASSAGEM_8_11", 1, (558, 205, 638, 244)),
)


def default_symbol_assets_dir() -> Path:
    return settings.root_dir / "croqui_engine" / "app" / "static" / "img" / "symbols" / "official"


def generate_official_symbol_assets_from_xls(
    xls_path: Path,
    output_dir: Path | None = None,
) -> Path:
    import fitz

    output_dir = output_dir or default_symbol_assets_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = settings.tmp_dir / "official_symbol_assets"
    pdf_path = convert_to_pdf(xls_path, tmp_dir)
    assets: list[dict] = []
    with fitz.open(pdf_path) as doc:
        symbol_pages = _find_symbol_pages(doc)
        if not symbol_pages:
            raise RuntimeError("Nenhuma pagina de simbologia encontrada no XLS informado.")
        for spec in ASSET_SPECS:
            if spec.symbol_page >= len(symbol_pages):
                continue
            page = doc[symbol_pages[spec.symbol_page]]
            path = output_dir / f"{spec.id.lower()}.png"
            width_px, height_px = _render_asset(page, spec.rect, path)
            assets.append(
                {
                    "id": spec.id,
                    "filename": path.name,
                    "width_px": width_px,
                    "height_px": height_px,
                }
            )
    manifest = {
        "version": "local-official-simbologia-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "Aba Simbologia oficial convertida localmente. Caminho do arquivo de origem nao e persistido.",
        "assets": assets,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def load_official_symbol_assets(asset_dir: Path | None = None) -> dict[str, dict]:
    asset_dir = asset_dir or default_symbol_assets_dir()
    manifest_path = asset_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets: dict[str, dict] = {}
    for item in manifest.get("assets", []):
        path = asset_dir / str(item.get("filename", ""))
        if not path.exists():
            continue
        assets[str(item["id"])] = {**item, "path": path}
    return assets


def _find_symbol_pages(doc) -> list[int]:
    indices = []
    for index, page in enumerate(doc):
        text = page.get_text("text").lower()
        if "simbologia" in text or "simbolo" in text or "s\u00edmbolo" in text:
            indices.append(index)
    return indices


def _render_asset(page, rect: tuple[float, float, float, float], output_path: Path) -> tuple[int, int]:
    import fitz

    pix = page.get_pixmap(matrix=fitz.Matrix(5, 5), clip=fitz.Rect(*rect), alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    image = _make_white_transparent(image)
    image = _trim_transparent(image, padding=8)
    image.save(output_path)
    return image.size


def _make_white_transparent(image: Image.Image) -> Image.Image:
    pixels = []
    for red, green, blue, alpha in image.getdata():
        if red > 246 and green > 246 and blue > 246:
            pixels.append((0, 0, 0, 0))
        else:
            pixels.append((red, green, blue, alpha))
    image.putdata(pixels)
    return image


def _trim_transparent(image: Image.Image, padding: int) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        return image
    cropped = image.crop(bbox)
    padded = Image.new("RGBA", (cropped.width + padding * 2, cropped.height + padding * 2), (0, 0, 0, 0))
    padded.paste(cropped, (padding, padding), cropped)
    return padded
