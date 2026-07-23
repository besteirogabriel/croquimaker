from pathlib import Path

from sistema.parsing.entities import (
    ConductorSegment,
    Pole,
    Position,
    ProjectExtraction,
    Transformer,
)
from sistema.topology.network import build_network_graph, select_service_network


def _segment(
    index: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    tension: str = "MT",
) -> ConductorSegment:
    return ConductorSegment(
        page=0,
        tensao=tension,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        path_id=f"path-{index}",
        sequence=0,
        color=(0.0, 0.0, 1.0) if tension == "MT" else (0.0, 0.7, 0.0),
        width=1.0,
    )


def _position(x: float, y_top: float) -> Position:
    return Position.from_pdf(0, x, y_top, 200.0)


def test_selecao_fica_no_componente_do_equipamento_principal():
    extraction = ProjectExtraction(
        folder_id="synthetic",
        source_path=Path("synthetic.pdf"),
        page_sizes={0: (300.0, 200.0)},
        conductors=[
            _segment(0, 20, 60, 140, 60),
            _segment(1, 210, 140, 280, 140),
        ],
        poles=[
            Pole("P1", _position(20, 60)),
            Pole("P2", _position(80, 60)),
            Pole("P3", _position(140, 60)),
            Pole("P4", _position(210, 140)),
            Pole("P5", _position(280, 140)),
        ],
        transformers=[Transformer("631892", _position(80, 60))],
        metadata={"equipamento": "TR 631892"},
    )

    selection = select_service_network(
        extraction,
        {"meta": {"equipamento": "TR 631892"}, "equipamentos": []},
        0,
    )

    assert selection.primary_code == "631892"
    assert selection.warnings == []
    assert selection.segment_indexes == {0}
    assert selection.pole_indexes == {0, 1, 2}
    assert {3, 4}.isdisjoint(selection.pole_indexes)


def test_geometria_insuficiente_e_marcada_para_revisao():
    extraction = ProjectExtraction(
        folder_id="sparse",
        source_path=Path("sparse.pdf"),
        page_sizes={0: (300.0, 200.0)},
        conductors=[_segment(0, 20, 60, 140, 60)],
        poles=[Pole("P1", _position(20, 60)), Pole("P2", _position(140, 60))],
    )

    selection = select_service_network(
        extraction,
        {"meta": {"equipamento": "FU 754726"}, "equipamentos": []},
        0,
    )
    payload = selection.to_dict(extraction)

    assert payload["status"] == "needs_review"
    assert "LOW_CONDUCTOR_COVERAGE" in payload["warnings"]
    assert "LOW_POLE_COVERAGE" in payload["warnings"]
    assert "NO_SERVICE_ANCHOR" in payload["warnings"]


def test_cruzamento_de_tensoes_so_conecta_quando_existe_poste():
    extraction = ProjectExtraction(
        folder_id="crossing",
        source_path=Path("crossing.pdf"),
        page_sizes={0: (300.0, 200.0)},
        conductors=[
            _segment(0, 20, 100, 280, 100, "MT"),
            _segment(1, 150, 20, 150, 180, "BT"),
        ],
    )
    graph_without_pole = build_network_graph(extraction, 0)
    mt_component = graph_without_pole.component_by_node[graph_without_pole.edges[0].start]
    bt_edge = next(edge for edge in graph_without_pole.edges if edge.segment_index == 1)
    assert graph_without_pole.component_by_node[bt_edge.start] != mt_component

    extraction.poles = [Pole("P1", _position(150, 100))]
    graph_with_pole = build_network_graph(extraction, 0)
    pole_node = graph_with_pole.pole_nodes[0]
    conductor_components = {
        graph_with_pole.component_by_node[node.id]
        for node in graph_with_pole.nodes
        if node.kind == "conductor"
    }
    assert conductor_components == {graph_with_pole.component_by_node[pole_node]}


def test_cruzamento_mesma_tensao_e_dividido_sem_mudar_coordenadas():
    extraction = ProjectExtraction(
        folder_id="junction",
        source_path=Path("junction.pdf"),
        page_sizes={0: (300.0, 200.0)},
        conductors=[
            _segment(0, 20, 100, 280, 100, "MT"),
            _segment(1, 150, 20, 150, 180, "MT"),
        ],
    )
    graph = build_network_graph(extraction, 0, snap_tolerance=0.5, pole_tolerance=2.0)
    junctions = [
        node
        for node in graph.nodes
        if abs(node.x - 150.0) < 1e-6 and abs(node.y - 100.0) < 1e-6
    ]
    assert len(junctions) == 1
    junction = junctions[0]
    conductor_edges = [
        graph.edges[edge_id]
        for _, edge_id, _ in graph.adjacency[junction.id]
        if graph.edges[edge_id].kind == "conductor"
    ]
    assert len(conductor_edges) == 4


def test_selecao_preserva_mt_e_bt_paralelas_entre_os_mesmos_postes():
    extraction = ProjectExtraction(
        folder_id="parallel",
        source_path=Path("parallel.pdf"),
        page_sizes={0: (300.0, 200.0)},
        conductors=[
            _segment(0, 20, 98, 280, 98, "MT"),
            _segment(1, 20, 102, 280, 102, "BT"),
        ],
        poles=[
            Pole("P1", _position(20, 100)),
            Pole("P2", _position(150, 100)),
            Pole("P3", _position(280, 100)),
        ],
        transformers=[Transformer("631892", _position(150, 100))],
        metadata={"equipamento": "TR 631892"},
    )

    selection = select_service_network(
        extraction,
        {"meta": {"equipamento": "TR 631892"}, "equipamentos": []},
        0,
    )

    assert selection.pole_indexes == {0, 1, 2}
    assert selection.segment_indexes == {0, 1}
