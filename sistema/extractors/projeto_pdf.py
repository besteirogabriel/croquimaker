from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import fitz

from sistema.extractors._pdf_geometry import (
    detect_poles,
    extract_conductor_segments,
    nearest_pole,
)
from sistema.parsing.entities import (
    ExistingEquipment,
    Position,
    ProjectExtraction,
    Transformer,
)


def _spatial_context(words: list[tuple], x: float, y: float) -> str:
    nearby = []
    for word in words:
        wx = (float(word[0]) + float(word[2])) / 2
        wy = (float(word[1]) + float(word[3])) / 2
        if abs(wx - x) <= 135 and abs(wy - y) <= 32:
            nearby.append((wy, wx, str(word[4])))
    nearby.sort(key=lambda item: (round(item[0] / 8), item[1]))
    return " ".join(item[2] for item in nearby)


def _extract_metadata(doc: fitz.Document) -> dict[str, str]:
    text = "\n".join(page.get_text() for page in doc)
    compact = re.sub(r"\s+", " ", text)
    metadata = {"os": "", "municipio": "", "equipamento": "", "data": ""}

    note = re.search(r"Nota\s*:?\s*(\d{9,15})", compact, re.I)
    if note:
        metadata["os"] = note.group(1)
    if not metadata["os"]:
        note = re.search(r"\b(300\d{9})\b", compact)
        if note:
            metadata["os"] = note.group(1)

    municipio = re.search(r"Munic[ií]pio\s*:\s*([A-Za-zÀ-ÿ ]+?)(?=Cliente|Obra|Endere|Respons|Escala|Data|Nota)", compact, re.I)
    if municipio:
        metadata["municipio"] = municipio.group(1).strip().upper()

    date = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", compact)
    if date:
        metadata["data"] = date.group(1)

    action = re.search(
        r"\b(Abrir|Fechar|Retirar|Instalar|Substituir)\s+(Transformador|Religador|Chave[^\d]{0,20})\s+(\d{6,7})\b",
        compact,
        re.I,
    )
    if action:
        kind = action.group(2).lower()
        prefix = "TR" if "transformador" in kind else "RL" if "religador" in kind else "CH"
        metadata["equipamento"] = f"{prefix} {action.group(3)}"
    return metadata


def _extract_actions(doc: fitz.Document) -> dict[str, str]:
    """Extract only explicit operational actions associated with asset codes."""

    text = "\n".join(page.get_text() for page in doc)
    compact = re.sub(r"\s+", " ", text)
    actions: dict[str, str] = {}
    action_pattern = re.compile(
        r"\b(Abrir|Fechar|Desligar|Ligar|Instalar|Incluir|Retirar|Excluir|"
        r"Substituir|Deslocar)\b"
        r"(?:\s+(?:o|a|os|as|um|uma|Transformador|Religador|Chave|"
        r"Fus[ií]vel|Faca|equipamento)){0,5}\s+"
        r"(?:TR|FU|FC|RL|RG|OL|SC|OMR)?\s*(\d{6,7})\b",
        re.I,
    )
    aliases = {
        "DESLIGAR": "DESLIGAR",
        "LIGAR": "LIGAR",
        "ABRIR": "ABRIR",
        "FECHAR": "FECHAR",
        "INSTALAR": "INSTALAR",
        "INCLUIR": "INSTALAR",
        "RETIRAR": "RETIRAR",
        "EXCLUIR": "RETIRAR",
        "SUBSTITUIR": "SUBSTITUIR",
        "DESLOCAR": "DESLOCAR",
    }
    for match in action_pattern.finditer(compact):
        actions.setdefault(match.group(2), aliases[match.group(1).upper()])
    return actions


def _placement_direction(
    pole_position: Position,
    label_position: Position,
    page_height: float,
) -> tuple[float, float] | None:
    """Preserve the orthogonal side evidenced by the source equipment label."""

    dx = label_position.x - pole_position.x
    dy = pole_position.y_pdf(page_height) - label_position.y_pdf(page_height)
    if abs(dx) <= 1e-6 and abs(dy) <= 1e-6:
        return None
    if abs(dy) >= abs(dx):
        return (0.0, 1.0 if dy > 0 else -1.0)
    return (1.0 if dx > 0 else -1.0, 0.0)


def _extract_equipment(doc: fitz.Document, extraction: ProjectExtraction) -> None:
    actions = _extract_actions(doc)
    occurrences: dict[
        str,
        list[
            tuple[
                int,
                float,
                float,
                str,
                float,
                Position,
                Position,
                tuple[float, float] | None,
            ]
        ],
    ] = defaultdict(list)
    for page_no, page in enumerate(doc):
        words = page.get_text("words")
        page_height = page.rect.height
        for index, word in enumerate(words):
            token = str(word[4]).strip()
            if not re.fullmatch(r"\d{6,7}", token) or token.startswith("300"):
                continue
            x = (float(word[0]) + float(word[2])) / 2
            y = (float(word[1]) + float(word[3])) / 2
            context = _spatial_context(words, x, y)
            pole, distance = nearest_pole(extraction.poles, page_no, x, y, page_height, max_distance=170.0)
            if pole is None:
                continue
            position = pole.position
            label_position = Position.from_pdf(page_no, x, y, page_height)
            occurrences[token].append(
                (
                    page_no,
                    x,
                    y,
                    context,
                    distance,
                    position,
                    label_position,
                    _placement_direction(position, label_position, page_height),
                )
            )

    for numero, rows in occurrences.items():
        (
            page_no,
            _,
            _,
            context,
            _,
            position,
            label_position,
            placement_direction,
        ) = min(rows, key=lambda row: row[4])
        all_context = " ".join(row[3] for row in rows)
        normalized_context = all_context.upper()
        is_reference = bool(
            re.search(rf"TR\s+REFER\w*\s+{re.escape(numero)}\b", normalized_context)
        )
        has_distributed_generation = (
            "GERAÇÃO DISTRIBUIDA" in normalized_context
            or "GERACAO DISTRIBUIDA" in normalized_context
            or "GD DISTRIBU" in normalized_context
        )
        is_private_generation = has_distributed_generation and bool(
            re.search(r"\b(?:150|300)[.,]00\b|\bS/N", normalized_context)
        )
        is_transformer = (
            "KVA" in normalized_context
            or "TRT" in normalized_context
            or ("13.8-380" in normalized_context and re.search(r"\b\d{2,3}[.,]\d{2}\b", normalized_context))
        )
        is_new = "INSTALAR" in normalized_context or "NOVO" in normalized_context
        if is_reference or (is_private_generation and not is_new):
            continue
        if is_transformer:
            kva_match = re.search(r"(\d+(?:[.,]\d+)?)\s*KVA", normalized_context)
            extraction.transformers.append(
                Transformer(
                    numero=numero,
                    position=position,
                    kva=kva_match.group(1).replace(",", ".") if kva_match else "",
                    novo=is_new,
                    acao=actions.get(numero, "INSTALAR" if is_new else ""),
                    label_position=label_position,
                    placement_direction=placement_direction,
                )
            )
            continue

        tipo = "EQUIPAMENTO"
        if re.search(r"\bR[123]\b|RELIG", normalized_context):
            tipo = "RELIGADOR"
        elif re.search(r"\b\d+K\b|FUS[IÍ]V|CHAVE", normalized_context):
            tipo = "CHAVE_FUSIVEL"
        extraction.existing_equipment.append(
            ExistingEquipment(
                numero=numero,
                position=position,
                tipo=tipo,
                contexto=all_context[:240],
                acao=actions.get(numero, ""),
                label_position=label_position,
                placement_direction=placement_direction,
            )
        )


class ProjectPdfExtractor:
    kind = "projeto_pdf"

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def extract(self, folder_id: str, path: Path) -> ProjectExtraction:
        path = Path(path)
        doc = fitz.open(path)
        try:
            segments, inventory = extract_conductor_segments(doc)
            extraction = ProjectExtraction(
                folder_id=folder_id,
                source_path=path,
                page_sizes={i: (float(page.rect.width), float(page.rect.height)) for i, page in enumerate(doc)},
                conductors=segments,
                color_inventory=inventory,
                metadata=_extract_metadata(doc),
            )
            extraction.poles = detect_poles(doc, segments)
            _extract_equipment(doc, extraction)
            if not extraction.metadata.get("equipamento"):
                new_transformers = [item for item in extraction.transformers if item.novo]
                existing_transformers = [item for item in extraction.transformers if not item.novo]
                if new_transformers and existing_transformers:
                    new_item = new_transformers[0]
                    page_height = extraction.page_sizes[new_item.position.page][1]
                    nx = new_item.position.x
                    ny = new_item.position.y_pdf(page_height)
                    nearest = min(
                        (item for item in existing_transformers if item.position.page == new_item.position.page),
                        key=lambda item: (
                            (item.position.x - nx) ** 2
                            + (item.position.y_pdf(page_height) - ny) ** 2
                        ),
                        default=None,
                    )
                    if nearest:
                        extraction.metadata["equipamento"] = f"TR {nearest.numero}"
            return extraction
        finally:
            doc.close()


PROJECT_PDF_EXTRACTOR = ProjectPdfExtractor()
