from __future__ import annotations

from croqui_engine.core.models import BBox, ExtractedWord, Node
from croqui_engine.extraction.geometry import distance_points


def find_nearest_words(
    target_bbox: BBox, words: list[ExtractedWord], radius: float = 120
) -> list[ExtractedWord]:
    center = target_bbox.center
    return sorted(
        [word for word in words if distance_points(center, word.bbox.center) <= radius],
        key=lambda word: distance_points(center, word.bbox.center),
    )


def find_nearest_node(equipment_bbox: BBox, nodes: list[Node], radius: float = 180) -> Node | None:
    candidates = []
    for node in nodes:
        if node.bbox is None:
            continue
        dist = distance_points(equipment_bbox.center, node.bbox.center)
        if dist <= radius:
            candidates.append((dist, node))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1]


def merge_text_lines(words: list[ExtractedWord]) -> list[str]:
    grouped: dict[tuple[int, int | None, int | None], list[ExtractedWord]] = {}
    for word in words:
        grouped.setdefault((word.page_index, word.block_no, word.line_no), []).append(word)
    lines = []
    for key in sorted(grouped):
        row = " ".join(w.text for w in sorted(grouped[key], key=lambda w: w.bbox.x0))
        if row.strip():
            lines.append(row.strip())
    return lines
