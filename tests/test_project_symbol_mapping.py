from __future__ import annotations

from pathlib import Path

from sistema.extractors.project_symbols import (
    classify_circular_pole,
    croqui_symbol_for_project_kind,
    load_project_symbol_mapping,
)
from sistema.extractors.projeto_pdf import PROJECT_PDF_EXTRACTOR
from sistema.generation.rge_symbols import (
    load_rge_symbol_catalog,
    symbol_for_equipment,
)
from sistema.parsing.entities import (
    ConductorSegment,
    Position,
    ProjectExtraction,
    StructureType,
)
from sistema.topology.network import build_network_graph


ROOT = Path(__file__).resolve().parents[1]
REVIEWED_PROJECT = (
    ROOT
    / "CROQUI IA"
    / "300001082616"
    / "300001082616 Projeto A3.pdf"
)


def _brown(rect, items=24):
    return {
        "rect": rect,
        "color": (0.398, 0.066, 0.0),
        "items": [("l",)] * items,
    }


def _segment(
    start: tuple[float, float],
    end: tuple[float, float],
    sequence: int,
) -> ConductorSegment:
    return ConductorSegment(
        page=0,
        tensao="BT",
        x1=start[0],
        y1=start[1],
        x2=end[0],
        y2=end[1],
        path_id=f"segment-{sequence}",
        sequence=sequence,
        color=(0.0, 0.699, 0.0),
        width=1.0,
    )


def test_depara_registra_todas_as_comparacoes_revisadas():
    mapping = load_project_symbol_mapping()
    by_reference = {
        reference: rule["croqui_symbol"]
        for rule in mapping["rules"].values()
        for reference in rule["reference_codes"]
    }

    assert by_reference == {
        "ICON-002": "POSTE_CONCRETO",
        "ICON-004": "POSTE_MADEIRA",
        "ICON-005": "POSTE_CONCRETO",
        "ICON-006": "POSTE_CONCRETO",
        "ICON-007": "POSTE_CONCRETO",
        "ICON-008": "POSTE_DUPLO_T",
        "ICON-009": "TRANSFORMADOR_RGE",
        "ICON-010": "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA",
        "ICON-011": "TRANSFORMADOR_RGE",
        "ICON-016": "POSTE_MADEIRA",
        "ICON-018": "POSTE_NOVO",
        "ICON-019": "CRUZAMENTO_COM_CONEXAO",
        "ICON-020": "CRUZAMENTO_COM_CONEXAO",
        "ICON-021": "CRUZAMENTO_SEM_CONEXAO",
        "ICON-022": "PASSAGEM_PRIMARIO",
        "ICON-023": "PASSAGEM_SECUNDARIO",
        "ICON-024": "ENCABECAMENTO_PRIMARIO",
        "ICON-025": "ENCABECAMENTO_SECUNDARIO",
    }


def test_postes_usam_vetores_da_simbologia_oficial():
    catalog = load_rge_symbol_catalog()["symbols"]

    assert len(catalog["POSTE_MADEIRA"]["paths"]) == 1
    assert len(catalog["POSTE_CONCRETO"]["paths"]) == 2
    assert len(catalog["POSTE_DUPLO_T"]["paths"]) == 3
    assert catalog["POSTE_MADEIRA"]["sheet"] == "Simbologia"
    assert catalog["POSTE_CONCRETO"]["sheet"] == "Simbologia"
    assert catalog["POSTE_DUPLO_T"]["sheet"] == "Simbologia"


def test_perfil_vetorial_distingue_madeira_de_concreto():
    wood = [
        _brown((-4.1, -4.2, 4.1, 0.1), 48),
        _brown((-4.1, 0.0, 4.1, 4.2), 48),
    ]
    concrete = [
        _brown((-4.1, -4.1, 0.1, 0.1)),
        _brown((0.0, -4.1, 4.1, 0.1)),
        _brown((-4.1, 0.0, 0.1, 4.1)),
        _brown((0.0, 0.0, 4.1, 4.1)),
        _brown((-2.8, -2.8, 2.8, 0.0), 32),
        _brown((-2.8, 0.0, 2.8, 2.8), 32),
    ]

    assert classify_circular_pole(wood, 0.0, 0.0) == "POSTE_CIRCULAR_MADEIRA"
    assert classify_circular_pole(concrete, 0.0, 0.0) == "POSTE_CIRCULAR_CONCRETO"


def test_aliases_de_componentes_agrupados_resolvem_simbolo_correto():
    assert (
        croqui_symbol_for_project_kind("TRANSFORMADOR_COM_PARA_RAIO")
        == "TRANSFORMADOR_RGE"
    )
    assert (
        symbol_for_equipment("CHAVE_FUSIVEL_COM_PARA_RAIO")
        == "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA"
    )
    assert (
        croqui_symbol_for_project_kind("POSTE_MADEIRA_COM_ESTAI")
        == "POSTE_MADEIRA"
    )


def test_projeto_revisado_produz_perfis_e_estruturas_sem_codigo_hardcoded():
    extraction = PROJECT_PDF_EXTRACTOR.extract(
        REVIEWED_PROJECT.parent.name,
        REVIEWED_PROJECT,
    )
    pole_kinds = {pole.project_kind for pole in extraction.poles}
    structure_symbols = {item.codigo for item in extraction.structure_types}

    assert {
        "POSTE_CIRCULAR_CONCRETO",
        "POSTE_CIRCULAR_MADEIRA",
        "POSTE_DUPLO_T",
    } <= pole_kinds
    assert any(pole.novo and pole.croqui_symbol == "POSTE_NOVO" for pole in extraction.poles)
    assert {
        "CRUZAMENTO_COM_CONEXAO",
        "CRUZAMENTO_SEM_CONEXAO",
        "PASSAGEM_PRIMARIO",
        "PASSAGEM_SECUNDARIO",
    } <= structure_symbols
    assert all(
        item.evidence.startswith("project_")
        for item in extraction.structure_types
    )


def test_cruzamento_sem_conexao_nao_funde_as_duas_redes():
    extraction = ProjectExtraction(
        folder_id="crossing-without-connection",
        source_path=Path("synthetic.pdf"),
        page_sizes={0: (200.0, 200.0)},
        conductors=[
            _segment((20.0, 100.0), (180.0, 100.0), 0),
            _segment((100.0, 20.0), (100.0, 180.0), 1),
        ],
        structure_types=[
            StructureType(
                codigo="CRUZAMENTO_SEM_CONEXAO",
                position=Position.from_pdf(0, 100.0, 100.0, 200.0),
                project_kind="CRUZAMENTO_SEM_CONEXAO",
            )
        ],
    )

    graph = build_network_graph(
        extraction,
        0,
        snap_tolerance=1.0,
        pole_tolerance=5.0,
    )

    assert len(graph.component_by_node.values()) == 4
    assert len(set(graph.component_by_node.values())) == 2
