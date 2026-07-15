from __future__ import annotations

import re

from croqui_engine.core.models import BBox, Equipment, ExtractedWord
from croqui_engine.symbols.catalog import load_symbol_catalog, match_equipment


def parse_equipment_from_text(text: str) -> list[Equipment]:
    catalog = load_symbol_catalog()
    equipment: list[Equipment] = []
    seen: set[tuple[str, str]] = set()

    for match in match_equipment(text, catalog):
        code = _code_from_match(match.text)
        if not code:
            continue
        eq_type = _map_type(match.type, match.text)
        status = infer_status(text, match.text)
        key = (code, eq_type)
        if key in seen:
            continue
        seen.add(key)
        equipment.append(
            Equipment(
                code=code,
                type=eq_type,
                confidence=match.confidence,
                raw_text=match.text,
                status=status,
            )
        )
    return equipment


def parse_equipment_from_words(words: list[ExtractedWord]) -> list[Equipment]:
    lines = _word_lines(words)
    output: list[Equipment] = []
    seen: set[tuple[str, str]] = set()
    for line_words in lines:
        line_text = " ".join(word.text for word in line_words)
        parsed = parse_equipment_from_text(line_text)
        for item in parsed:
            key = (item.code, item.type)
            if key in seen:
                continue
            seen.add(key)
            item.page_index = line_words[0].page_index
            item.bbox = _merge_bbox([w.bbox for w in line_words])
            item.raw_text = line_text
            output.append(item)
    return output


def infer_status(context_text: str, matched_text: str) -> str:
    idx = context_text.lower().find(matched_text.lower())
    window = context_text[max(0, idx - 80) : idx + len(matched_text) + 80] if idx >= 0 else context_text
    window_l = window.lower()
    status_map = {
        "instalar": ["instalar", "novo", "novos", "nova"],
        "retirar": ["retirar", "remover", "retirada", "sera retirada", "será retirada"],
        "abrir": ["abrir"],
        "fechar": ["fechar"],
        "deslocar": ["deslocar", "deslocamento"],
        "existente": ["existente", "referencia", "referência"],
    }
    for status, tokens in status_map.items():
        if any(token in window_l for token in tokens):
            return status
    return "indeterminado"


def _code_from_match(text: str) -> str:
    found = re.findall(r"\b\d{5,8}\b", text)
    return found[0] if found else ""


def _map_type(match_type: str, text: str) -> str:
    upper = text.upper()
    if match_type == "transformer" or "KVA" in upper or upper.startswith("TRT"):
        return "TRANSFORMADOR"
    if match_type == "fuse_switch" or "FU" in upper:
        return "CHAVE_FUSIVEL"
    if match_type == "command_switch" or "FC" in upper or "FACA" in upper:
        return "CHAVE_COMANDO"
    return match_type.upper()


def _word_lines(words: list[ExtractedWord]) -> list[list[ExtractedWord]]:
    grouped: dict[tuple[int, int | None, int | None], list[ExtractedWord]] = {}
    for word in words:
        grouped.setdefault((word.page_index, word.block_no, word.line_no), []).append(word)
    return [sorted(grouped[key], key=lambda w: w.bbox.x0) for key in sorted(grouped)]


def _merge_bbox(boxes: list[BBox]) -> BBox | None:
    if not boxes:
        return None
    return BBox(
        x0=min(box.x0 for box in boxes),
        y0=min(box.y0 for box in boxes),
        x1=max(box.x1 for box in boxes),
        y1=max(box.y1 for box in boxes),
    )
