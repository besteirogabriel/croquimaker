from __future__ import annotations

import re
from pathlib import Path

from croqui_engine.core.enums import PageKind
from croqui_engine.core.models import PageInfo
from croqui_engine.ingestion.pdf_loader import get_page_text


def classify_page(
    text: str,
    width: float,
    height: float,
    rotation: int = 0,
    drawings_count: int = 0,
    page_index: int = 0,
) -> PageInfo:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    upper = normalized.upper()
    signals: list[str] = []
    scores: dict[PageKind, float] = {kind: 0.0 for kind in PageKind}

    def hit(kind: PageKind, signal: str, value: float) -> None:
        scores[kind] = scores.get(kind, 0.0) + value
        signals.append(signal)

    if "TES" in upper and ("DADOS GERAIS" in upper or "DADOS DO SERV" in upper):
        hit(PageKind.TES_ADMINISTRATIVO, "TES/Dados Gerais", 0.75)
    if re.search(r"\bTES\s*\d{5,}", upper) or re.search(r"\bNUMERO:\s*\d{5,}", upper):
        hit(PageKind.TES_ADMINISTRATIVO, "Numero TES", 0.25)
    if "EQUIPES" in upper and "QUANTIDADE" in upper:
        hit(PageKind.EQUIPES_EXECUCAO, "Equipes/Quantidade", 0.85)
    if "PLANO DE MANOBRA" in upper or "PLANO DE MANOBRAS" in upper:
        hit(PageKind.PLANO_MANOBRA, "Plano de Manobras", 0.9)
    if "PASSOS DE MANOBRA" in upper or "PASSOS DE MANOBRAS" in upper:
        hit(PageKind.PASSOS_MANOBRA, "Passos de Manobras", 0.9)
    if "CROQUI" in upper and "AVALIACAO DE VIABILIDADE" in _strip_accents(upper):
        hit(PageKind.CROQUI_RESUMIDO, "Croqui/Viabilidade", 0.8)
    if "GERENCIA DE OBRAS" in _strip_accents(upper) or "MANUTENCAO" in _strip_accents(upper):
        hit(PageKind.PROJETO_REDE, "Gerencia de Obras/Manutencao", 0.55)

    pole_count = len(re.findall(r"\bP\d+\b", upper))
    span_count = len(re.findall(r"\bV\d+\s*[-–]\s*\d+\b", upper))
    if pole_count >= 2:
        hit(PageKind.PROJETO_REDE, f"{pole_count} postes", min(0.3, pole_count * 0.04))
    if span_count >= 1:
        hit(PageKind.PROJETO_REDE, f"{span_count} vaos", min(0.45, span_count * 0.09))
    if width > height and drawings_count > 80:
        hit(PageKind.PROJETO_REDE, "Paisagem com alta densidade grafica", 0.25)
    if "FIGURA" in upper and drawings_count > 10:
        hit(PageKind.DETALHE_TECNICO, "Figura/desenho tecnico", 0.45)

    kind = max(scores, key=scores.get)
    score = min(scores[kind], 0.98)
    if score <= 0.05:
        kind = PageKind.UNKNOWN
        score = 0.0

    orientation = "landscape" if width >= height else "portrait"
    return PageInfo(
        index=page_index,
        width=width,
        height=height,
        rotation=rotation,
        orientation=orientation,
        kind=kind.value,
        confidence=round(score, 3),
        signals=list(dict.fromkeys(signals)),
    )


def classify_pdf_pages(pdf_path: Path) -> list[PageInfo]:
    import fitz

    pages: list[PageInfo] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc):
            drawings_count = 0
            try:
                drawings_count = len(page.get_drawings())
            except Exception:
                drawings_count = 0
            info = classify_page(
                get_page_text(pdf_path, index),
                page.rect.width,
                page.rect.height,
                page.rotation,
                drawings_count,
                index,
            )
            pages.append(info)
    return pages


def _strip_accents(value: str) -> str:
    table = str.maketrans(
        "ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàâãéèêíìîóòôõúùûç",
        "AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuc",
    )
    return value.translate(table)
