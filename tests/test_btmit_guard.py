from pathlib import Path

from sistema.parsing.entities import ConductorSegment, Position, ProjectExtraction, StructureType
from sistema.topology.btmit_guard import mark_unverified_crossings_as_non_connections


def _segment(x1, y1, x2, y2):
    return ConductorSegment(
        page=0,
        tensao="BT",
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        path_id="test",
        sequence=0,
        color=(0.0, 1.0, 0.0),
        width=1.0,
    )


def _extraction():
    return ProjectExtraction(
        folder_id="test",
        source_path=Path("test.pdf"),
        page_sizes={0: (600.0, 800.0)},
        conductors=[
            _segment(100, 300, 500, 300),
            _segment(300, 100, 300, 500),
        ],
    )


def test_interior_crossing_without_evidence_is_not_a_connection():
    extraction = _extraction()

    added = mark_unverified_crossings_as_non_connections(extraction)

    assert added == 1
    marker = extraction.structure_types[0]
    assert marker.codigo == "CRUZAMENTO_SEM_CONEXAO"
    assert marker.evidence == "btmit_geometry_guard"
    assert marker.position.x == 300
    assert marker.position.y_pdf(800) == 300


def test_explicit_connection_marker_is_preserved_as_connection():
    extraction = _extraction()
    extraction.structure_types.append(
        StructureType(
            codigo="CRUZAMENTO_COM_CONEXAO",
            position=Position.from_pdf(0, 300, 300, 800),
        )
    )

    added = mark_unverified_crossings_as_non_connections(extraction)

    assert added == 0
    assert [item.codigo for item in extraction.structure_types] == ["CRUZAMENTO_COM_CONEXAO"]
