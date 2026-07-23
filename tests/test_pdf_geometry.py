import json
from pathlib import Path

import fitz

from sistema.extractors import base
from sistema.extractors._pdf_geometry import classify_conductor_color
from sistema.generation.clean_projeto import render_clean_projeto
from sistema.generation.croqui_geometrico import (
    _viability_percentage,
    render_croqui_geometrico,
)
from sistema.generation.equipment_scene import resolve_equipment_scene
from sistema.topology.network import select_service_network


ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "CROQUI IA" / "300001134401"
PROJECT = CASE_DIR / "300001134401 PROJETO A3.pdf"


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


def test_regressao_300001134401_preserva_rede_postes_e_equipamentos(tmp_path):
    extraction = base.get_extractor("projeto_pdf").extract("300001134401", PROJECT)
    assert sum(segment.tensao == "MT" for segment in extraction.conductors) == 125
    assert sum(segment.tensao == "BT" for segment in extraction.conductors) == 96
    assert round(sum(segment.length for segment in extraction.conductors if segment.tensao == "MT"), 1) == 3024.3
    assert round(sum(segment.length for segment in extraction.conductors if segment.tensao == "BT"), 1) == 5186.4
    assert len(extraction.poles) >= 45
    assert {"P2", "P3", "P4", "P5"} <= {pole.codigo for pole in extraction.poles}
    transformer_codes = {item.numero for item in extraction.transformers}
    assert {"1317501", "744770", "631892"} <= transformer_codes
    switch_codes = {item.numero for item in extraction.existing_equipment}
    assert {"1291687", "748794"} <= switch_codes
    assert extraction.metadata["equipamento"] == "TR 631892"

    clean_pdf = tmp_path / "clean_projeto.pdf"
    clean_png = tmp_path / "clean_projeto.png"
    render_clean_projeto(PROJECT, extraction, clean_pdf, png_path=clean_png)
    assert clean_pdf.exists() and clean_png.exists()
    with fitz.open(clean_pdf) as clean_doc:
        assert clean_doc[0].get_text().strip() == ""

    projeto = {
        "meta": {"equipamento": "TR 631892", "municipio": "CAXIAS DO SUL"},
        "nos": [
            {"id": "P2", "tipo": "POSTE_NOVO"},
            {"id": "P3", "tipo": "POSTE_NOVO"},
            {"id": "P5", "tipo": "POSTE_NOVO"},
        ],
        "equipamentos": [
            {
                "tipo": "TRANSFORMADOR_RGE",
                "codigo": "1317501",
                "no_id": "P3",
                "estado": "INSTALAR",
            },
            {
                "tipo": "TRANSFORMADOR_RGE",
                "codigo": "631892",
                "no_id": "P5",
                "estado": "ABRIR",
            },
            {
                "tipo": "TRANSFORMADOR_RGE",
                "codigo": "744770",
                "no_id": "AUTO5",
                "estado": "",
            },
            {
                "tipo": "CHAVE_FUSIVEL_SEM_CARGA",
                "codigo": "1291687",
                "no_id": "AUTO22",
                "estado": "",
            },
            {
                "tipo": "CHAVE_FUSIVEL_SEM_CARGA",
                "codigo": "748794",
                "no_id": "AUTO43",
                "estado": "",
            },
        ],
        "areas": [
            {"nome": "LM", "tipo": "LM", "nos": "P2", "observacao": "Instalar transformador"},
            {"nome": "LV", "tipo": "LV", "nos": "P5", "observacao": "Abrir circuito de BT"},
        ],
    }
    selection = select_service_network(extraction, projeto, 0)
    assert selection.primary_code == "631892"
    assert {"631892", "1317501", "744770", "1291687", "748794"} <= set(
        selection.anchor_codes
    )
    assert len(selection.pole_indexes) == 25
    assert len(selection.pole_indexes) < len(extraction.poles)
    assert len(selection.segment_indexes) < len(extraction.conductors)
    selected_tensions = {
        tension: sum(
            extraction.conductors[index].tensao == tension
            for index in selection.segment_indexes
        )
        for tension in ("MT", "BT")
    }
    assert selected_tensions["MT"] >= 15
    assert selected_tensions["BT"] >= 20
    assert selection.to_dict(extraction)["selected_voltage_segment_counts"] == (
        selected_tensions
    )
    scene = resolve_equipment_scene(extraction, projeto, selection)
    resolved_codes = {item.code for item in scene.equipment}
    assert {
        "631892",
        "1317501",
        "744770",
        "748794",
        "1291687",
    } <= resolved_codes
    assert "1060277" not in resolved_codes
    assert "748749" not in resolved_codes
    assert len(selection.pole_indexes) == 25
    assert scene.new_pole_indexes
    croqui = tmp_path / "croqui.pdf"
    selection_json = tmp_path / "network_selection.json"
    render_croqui_geometrico(
        extraction,
        projeto,
        croqui,
        selection=selection,
        selection_path=selection_json,
    )
    assert selection_json.exists()
    selection_payload = json.loads(selection_json.read_text(encoding="utf-8"))
    assert {
        "631892",
        "1317501",
        "744770",
        "748794",
        "1291687",
    } <= {
        row["code"] for row in selection_payload["rendered_equipment"]
    }
    assert selection_payload["new_pole_indexes"]
    sem_areas = tmp_path / "croqui_sem_areas.pdf"
    render_croqui_geometrico(
        extraction,
        {**projeto, "areas": []},
        sem_areas,
    )
    doc = fitz.open(croqui)
    baseline = fitz.open(sem_areas)
    try:
        assert doc.page_count == 1
        assert round(doc[0].rect.width, 1) == 841.9
        assert round(doc[0].rect.height, 1) == 595.3
        text = doc[0].get_text().upper()
        assert "AREA DE TRABALHO" not in text
        assert "INSTALAR TRANSFORMADOR" not in text
        assert "ABRIR CIRCUITO DE BT" not in text
        assert {
            "631892",
            "1317501",
            "744770",
            "748794",
            "1291687",
        } <= set(text.split())
        assert "1060277" not in text
        assert "748749" not in text
        assert doc[0].get_text().count("Sim") == 9
        assert "Viabilidade: 100,0%" in doc[0].get_text()
        assert doc[0].get_pixmap(dpi=120, alpha=False).samples == baseline[0].get_pixmap(
            dpi=120, alpha=False
        ).samples
    finally:
        doc.close()
        baseline.close()


def test_metadados_nao_reintroduzem_areas_e_ativos_ficam_com_evidencia(tmp_path):
    extraction = base.get_extractor("projeto_pdf").extract("300001134401", PROJECT)
    croqui = tmp_path / "sem_areas.pdf"
    render_croqui_geometrico(
        extraction,
        {
            "meta": {"equipamento": "TR 631892"},
            "equipamentos": [{"codigo": "631892", "no_id": "P5"}],
            "areas": [],
        },
        croqui,
    )
    with fitz.open(croqui) as doc:
        text = doc[0].get_text().upper()
        assert "AREA DE TRABALHO" not in text
        assert "1317501" in text
        assert "744770" in text
        assert " SERRA" not in text
