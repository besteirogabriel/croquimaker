from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Position:
    """Posicao no contrato legado: origem no canto inferior esquerdo."""

    page: int
    x: float
    y: float

    @classmethod
    def from_pdf(cls, page: int, x: float, y_top: float, page_height: float) -> "Position":
        return cls(page=page, x=float(x), y=float(page_height - y_top))

    def y_pdf(self, page_height: float) -> float:
        return float(page_height - self.y)


@dataclass(frozen=True)
class ConductorSegment:
    page: int
    tensao: str
    x1: float
    y1: float
    x2: float
    y2: float
    path_id: str
    sequence: int
    color: tuple[float, float, float]
    width: float

    @property
    def length(self) -> float:
        return ((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2) ** 0.5


@dataclass(frozen=True)
class Pole:
    codigo: str
    position: Position


@dataclass(frozen=True)
class Transformer:
    numero: str
    position: Position
    kva: str = ""
    novo: bool = False


@dataclass(frozen=True)
class StructureType:
    codigo: str
    position: Position


@dataclass(frozen=True)
class ExistingEquipment:
    numero: str
    position: Position
    tipo: str = "EQUIPAMENTO"
    contexto: str = ""


@dataclass
class ProjectExtraction:
    folder_id: str
    source_path: Path
    page_sizes: dict[int, tuple[float, float]] = field(default_factory=dict)
    conductors: list[ConductorSegment] = field(default_factory=list)
    poles: list[Pole] = field(default_factory=list)
    transformers: list[Transformer] = field(default_factory=list)
    structure_types: list[StructureType] = field(default_factory=list)
    existing_equipment: list[ExistingEquipment] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    color_inventory: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_path"] = str(self.source_path)
        return payload
