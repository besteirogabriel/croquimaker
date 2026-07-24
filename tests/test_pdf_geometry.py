import json
from pathlib import Path

import fitz

from sistema.extractors._pdf_geometry import classify_conductor_color
from sistema.generation.croqui_geometrico import (
    _viability_percentage,
    render_croqui_geometrico,
)
from sistema.generation.equipment_scene import resolve_equipment_scene
from sistema.parsing.entities import (
    ConductorSegment,
    ExistingEquipment,
    Pole,
    Position,
    ProjectExtraction,
    Transformer,
)
from sistema.topology.network import NetworkGraph, NetworkSelection


def _position(x: float, y_top: float) -> Position:
    return Position.from_pdf(0, x, y_top, 400.0)


def _segment(
    tension: str,
    start: tuple[float, float],
    end: tuple[float, float],
    sequence: int,
) -> ConductorSegment:
    return ConductorSegment(
        page=0,
        tensao=tension,
        x1=start[0],
        y1=start[1],
        x2=end[0],
        y2=end[1],
        path_id=f"synthetic-{tension}-{sequence}",
        sequence=sequence,
        color=(0.0, 0.0, 1.0) if tension == "MT" else (0.0, 0.699, 0.0),
        width=1.0,
    )


def _synthetic_extraction() -> ProjectExtraction:
    poles = [
        Pole("P1", _position(200, 80)),
        Pole("P2", _position(200, 200)),
        Pole("P3", _position(200, 320)),
        Pole("P4", _position(80, 200)),
    ]
    conductors = [
        _segment("MT", (200, 80), (200, 320), 0),
        _segment("BT", (206, 80), (206, 320), 1),
        _segment("MT", (80, 200), (200, 200), 2),
        _segment("BT", (80, 206), (200, 206), 3),
    ]
    return ProjectExtraction(
        folder_id="synthetic-operational-scene",
        source_path=Path("synthetic.pdf"),
        page_sizes={0: (600.0, 400.0)},
        conductors=conductors,
        poles=poles,
        transformers=[
            Transformer("910001", poles[0].position),
            Transformer("910003", poles[2].position),
        ],
        existing_equipment=[
            ExistingEquipment(
                "910002",
                poles[3].position,
                tipo="CHAVE_FUSIVEL",
            ),
        ],
        metadata={
            "equipamento": "TR 910001",
            "municipio": "MUNICIPIO TESTE",
            "data": "01/01/2030",
        },
    )


def _synthetic_project() -> dict:
    return {
        "meta": {
            "equipamento": "TR 910001",
            "municipio": "MUNICIPIO TESTE",
        },
        "nos": [
            {"id": "P1", "tipo": "POSTE_NOVO"},
            {"id": "P2", "tipo": "POSTE_EXISTENTE"},
            {"id": "P3", "tipo": "POSTE_EXISTENTE"},
            {"id": "P4", "tipo": "POSTE_EXISTENTE"},
        ],
        "trechos": [],
        "equipamentos": [
            {
                "tipo": "TRANSFORMADOR_RGE",
                "codigo": "910001",
                "no_id": "P1",
                "estado": "INSTALAR",
            },
            {
                "tipo": "CHAVE_FUSIVEL_SEM_CARGA",
                "codigo": "910002",
                "no_id": "P4",
                "estado": "",
            },
            {
                "tipo": "TRANSFORMADOR_RGE",
                "codigo": "910003",
                "no_id": "P3",
                "estado": "ABRIR",
            },
            {
                "tipo": "ATERRAMENTO_BT",
                "codigo": "",
                "no_id": "P1",
                "estado": "INSTALAR",
            },
            {
                "tipo": "ATERRAMENTO_BT",
                "codigo": "",
                "no_id": "P2",
                "estado": "INSTALAR",
            },
            {
                "tipo": "ATERRAMENTO_BT",
                "codigo": "",
                "no_id": "P3",
                "estado": "INSTALAR",
            },
        ],
        "areas": [
            {
                "nome": "LM",
                "tipo": "LM",
                "nos": "P1 P3",
                "observacao": "Instalar transformador",
            },
            {
                "nome": "LV",
                "tipo": "LV",
                "nos": "P1 P2",
                "observacao": "Abrir circuito de BT",
            },
        ],
        "textos": [
            {
                "texto": "Abrir circuito de BT",
                "no_id": "P2",
                "tipo": "MANOBRA",
            },
        ],
    }


def _synthetic_selection(extraction: ProjectExtraction) -> NetworkSelection:
    return NetworkSelection(
        page=0,
        segment_ranges={
            index: [(0.0, 1.0)]
            for index in range(len(extraction.conductors))
        },
        pole_indexes=set(range(len(extraction.poles))),
        anchor_codes=["910001", "910002", "910003"],
        primary_code="910001",
        component=0,
        graph=NetworkGraph(
            page=0,
            snap_tolerance=1.0,
            pole_tolerance=8.0,
        ),
    )


def test_classificacao_usa_cores_cad_comprovadas():
    assert classify_conductor_color((0, 0, 1)) == "MT"
    assert classify_conductor_color((0, 0.699, 0)) == "BT"
    assert classify_conductor_color((0, 0.578, 1)) is None
    assert classify_conductor_color((0.398, 0.066, 0)) is None
    assert classify_conductor_color((0, 0, 0)) is None


def test_viabilidade_repete_formula_do_template_rge():
    assert _viability_percentage(["Sim"] * 9 + ["Não"]) == "100,0%"
    assert _viability_percentage(
        ["Não", "Sim"] + ["Não Avaliado"] * 7 + ["Não"]
    ) == "12,5%"


def test_cena_sintetica_preserva_simbolos_e_omite_anotacoes(tmp_path):
    extraction = _synthetic_extraction()
    projeto = _synthetic_project()
    selection = _synthetic_selection(extraction)
    scene = resolve_equipment_scene(extraction, projeto, selection)

    assert {item.code for item in scene.equipment if item.code} == {
        "910001",
        "910002",
        "910003",
    }
    assert sum(
        item.kind == "ATERRAMENTO_BT" for item in scene.equipment
    ) == 3
    assert scene.new_pole_indexes == {0}

    croqui = tmp_path / "croqui.pdf"
    diagnostics = tmp_path / "network_selection.json"
    render_croqui_geometrico(
        extraction,
        projeto,
        croqui,
        selection=selection,
        selection_path=diagnostics,
    )

    payload = json.loads(diagnostics.read_text(encoding="utf-8"))
    assert payload["symbol_catalog"]["sheet"] == "Simbologia"
    assert {
        row["kind"] for row in payload["rendered_equipment"]
    } >= {
        "TRANSFORMADOR_RGE",
        "CHAVE_FUSIVEL_SEM_CARGA",
        "ATERRAMENTO_BT",
    }
    assert all(
        tuple(row["direction"]) in {
            (1.0, 0.0),
            (0.0, 1.0),
            (-1.0, 0.0),
            (0.0, -1.0),
        }
        for row in payload["rendered_equipment"]
    )
    assert payload["work_areas"] == []
    assert payload["operational_notes"] == []

    with fitz.open(croqui) as doc:
        text = doc[0].get_text().upper()
        assert doc.page_count == 1
        assert round(doc[0].rect.width, 1) == 841.9
        assert round(doc[0].rect.height, 1) == 595.3
        assert {"910001", "910002", "910003"} <= set(text.split())
        assert "ÁREA DE TRABALHO" not in text
        assert "INSTALAR" not in text
        assert "ABRIR" not in text
        assert text.count("SIM") == 9
        assert "VIABILIDADE: 100,0%" in text


def test_areas_e_textos_sao_ignorados_mesmo_quando_presentes(tmp_path):
    extraction = _synthetic_extraction()
    projeto = _synthetic_project()
    croqui = tmp_path / "sem_areas.pdf"
    render_croqui_geometrico(
        extraction,
        projeto,
        croqui,
        selection=_synthetic_selection(extraction),
    )
    with fitz.open(croqui) as doc:
        text = doc[0].get_text().upper()
        assert "ÁREA DE TRABALHO" not in text
        assert "ABRIR CIRCUITO DE BT" not in text
        assert "INSTALAR TRANSFORMADOR" not in text
