from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sistema.parsing.entities import (
    ExistingEquipment,
    Position,
    ProjectExtraction,
    Transformer,
)
from sistema.topology.network import NetworkSelection


@dataclass(frozen=True)
class SceneEquipment:
    code: str
    kind: str
    state: str
    pole_index: int
    new: bool = False
    evidence: str = "source_pdf"


@dataclass(frozen=True)
class EquipmentScene:
    equipment: tuple[SceneEquipment, ...]
    new_pole_indexes: frozenset[int]


def _numeric_code(value: str) -> str:
    match = re.search(r"\b(\d{6,7})\b", str(value))
    return match.group(1) if match else ""


def _nearest_pole_index(
    extraction: ProjectExtraction,
    position: Position,
    page: int,
) -> int | None:
    height = extraction.page_sizes[page][1]
    candidates = [
        (
            math.hypot(
                pole.position.x - position.x,
                pole.position.y_pdf(height) - position.y_pdf(height),
            ),
            index,
        )
        for index, pole in enumerate(extraction.poles)
        if pole.position.page == page
    ]
    return min(candidates)[1] if candidates else None


def _source_equipment(
    extraction: ProjectExtraction,
) -> dict[str, Transformer | ExistingEquipment]:
    result: dict[str, Transformer | ExistingEquipment] = {}
    for item in [*extraction.transformers, *extraction.existing_equipment]:
        if item.numero:
            result.setdefault(item.numero, item)
    return result


def _semantic_equipment(projeto: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    rows = projeto.get("equipamentos", []) if isinstance(projeto, dict) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _numeric_code(row.get("codigo", ""))
        if code:
            result.setdefault(code, row)
    return result


def _kind(
    item: Transformer | ExistingEquipment | None,
    semantic: dict | None,
) -> str:
    semantic_kind = str((semantic or {}).get("tipo", "")).strip().upper()
    if semantic_kind:
        return semantic_kind
    if isinstance(item, Transformer):
        return "TRANSFORMADOR_RGE"
    source_kind = str(getattr(item, "tipo", "")).upper()
    if "FUS" in source_kind or source_kind == "CHAVE":
        return "CHAVE_FUSIVEL_SEM_CARGA"
    return source_kind or "EQUIPAMENTO"


def _state(
    item: Transformer | ExistingEquipment | None,
    semantic: dict | None,
) -> str:
    semantic_state = str((semantic or {}).get("estado", "")).strip().upper()
    if semantic_state:
        return semantic_state
    return str(getattr(item, "acao", "")).strip().upper()


def _pole_by_source_code(
    extraction: ProjectExtraction,
    page: int,
) -> dict[str, int]:
    return {
        code: pole_index
        for code, item in _source_equipment(extraction).items()
        if item.position.page == page
        for pole_index in [_nearest_pole_index(extraction, item.position, page)]
        if pole_index is not None
    }


def _semantic_new_poles(
    extraction: ProjectExtraction,
    projeto: dict,
    pole_by_code: dict[str, int],
) -> set[int]:
    pole_by_name = {
        pole.codigo.upper(): index for index, pole in enumerate(extraction.poles)
    }
    new_nodes = {
        str(row.get("id", "")).strip().upper()
        for row in projeto.get("nos", [])
        if isinstance(row, dict)
        and any(
            marker in str(row.get("tipo", "")).upper()
            for marker in ("NOVO", "SUBSTIT")
        )
    }
    result = {
        pole_by_name[node_id]
        for node_id in new_nodes
        if node_id in pole_by_name
    }
    for row in projeto.get("equipamentos", []):
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("no_id", "")).strip().upper()
        if node_id not in new_nodes:
            continue
        state = str(row.get("estado", "")).strip().upper()
        if state not in {"INSTALAR", "INCLUIR", "SUBSTITUIR"}:
            continue
        code = _numeric_code(row.get("codigo", ""))
        if code in pole_by_code:
            result.add(pole_by_code[code])
    return result


def resolve_equipment_scene(
    extraction: ProjectExtraction,
    projeto: dict,
    selection: NetworkSelection,
) -> EquipmentScene:
    """Resolve verified assets, labels and pole states for the final scene."""

    source = _source_equipment(extraction)
    semantic = _semantic_equipment(projeto)
    pole_by_code = _pole_by_source_code(extraction, selection.page)

    resolved: dict[str, SceneEquipment] = {}
    for source_code, item in source.items():
        pole_index = pole_by_code.get(source_code)
        if pole_index is None or pole_index not in selection.pole_indexes:
            continue
        semantic_row = semantic.get(source_code)
        resolved[source_code] = SceneEquipment(
            code=source_code,
            kind=_kind(item, semantic_row),
            state=_state(item, semantic_row),
            pole_index=pole_index,
            new=bool(getattr(item, "novo", False)),
        )

    new_poles = {
        index
        for index, pole in enumerate(extraction.poles)
        if pole.novo and index in selection.pole_indexes
    }
    new_poles.update(
        index
        for index in _semantic_new_poles(extraction, projeto, pole_by_code)
        if index in selection.pole_indexes
    )
    return EquipmentScene(
        equipment=tuple(
            sorted(
                resolved.values(),
                key=lambda item: (item.pole_index, item.code),
            )
        ),
        new_pole_indexes=frozenset(new_poles),
    )
