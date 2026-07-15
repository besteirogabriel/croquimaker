from __future__ import annotations

import re

from croqui_engine.core.models import BBox, ExtractedWord, Node, Span
from croqui_engine.symbols.catalog import match_network_type

SPAN_RE = re.compile(r"\(?\s*V\s*(\d{1,4})\s*[-–]\s*(\d{1,4})\s*\)?", re.IGNORECASE)
LENGTH_RE = re.compile(r"(\d+(?:[\.,]\d+)?)\s*m\b", re.IGNORECASE)


def parse_spans(text: str) -> list[Span]:
    output: list[Span] = []
    seen: set[str] = set()
    lines = [line.strip() for line in re.split(r"[\n\r]+", text or "") if line.strip()]
    if len(lines) == 1:
        lines = re.split(r"(?=\(?\s*V\d+\s*[-–]\s*\d+)", lines[0])

    for line in lines:
        for match in SPAN_RE.finditer(line):
            a, b = match.group(1), match.group(2)
            span_id = f"V{int(a)}-{int(b)}"
            if span_id in seen:
                continue
            seen.add(span_id)
            length = _parse_length(line[match.end() :])
            cable = _parse_cable(line)
            output.append(
                Span(
                    id=span_id,
                    from_node=f"P{int(a)}",
                    to_node=f"P{int(b)}",
                    length_m=length,
                    cable=cable,
                    network_type=match_network_type(line),
                    raw_text=line,
                    confidence=0.9 if length else 0.72,
                )
            )
    return output


def parse_spans_from_words(words: list[ExtractedWord]) -> list[Span]:
    spans: list[Span] = []
    seen: set[str] = set()
    for line_words in _word_lines(words):
        line = " ".join(word.text for word in line_words)
        for span in parse_spans(line):
            if span.id in seen:
                continue
            seen.add(span.id)
            span.page_index = line_words[0].page_index
            span.bbox = _merge_bbox([w.bbox for w in line_words])
            spans.append(span)
    return spans


def parse_nodes(text: str) -> list[Node]:
    nodes: list[Node] = []
    seen: set[str] = set()
    for found in re.finditer(r"\(?\s*P\s*(\d{1,4})(?!\d)\s*\)?", text or "", flags=re.IGNORECASE):
        node_id = f"P{int(found.group(1))}"
        if node_id in seen:
            continue
        seen.add(node_id)
        nodes.append(Node(id=node_id, confidence=0.65, raw_text=found.group(0)))
    return nodes


def parse_nodes_from_words(words: list[ExtractedWord]) -> list[Node]:
    nodes: list[Node] = []
    seen: set[str] = set()
    for word in words:
        for found in re.finditer(r"\bP\s*(\d{1,4})(?!\d)\b", word.text, flags=re.IGNORECASE):
            node_id = f"P{int(found.group(1))}"
            if node_id in seen:
                continue
            seen.add(node_id)
            nodes.append(
                Node(
                    id=node_id,
                    page_index=word.page_index,
                    bbox=word.bbox,
                    x=word.bbox.center[0],
                    y=word.bbox.center[1],
                    confidence=0.75,
                    raw_text=word.text,
                )
            )
    return nodes


def _parse_length(text: str) -> float | None:
    match = LENGTH_RE.search(text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _parse_cable(text: str) -> str | None:
    candidates = [
        r"\b\d+[EA]\d+(?:-\d+[A-Z])?\b",
        r"\b\d+S\d+[A-Z]?\b",
        r"\b\d+P\d+(?:\([A-Z0-9]+\))?\b",
        r"\b\d+A\d+\b",
    ]
    for pattern in candidates:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
    return None


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
