from pathlib import Path

import fitz

from sistema.extractors import base
from sistema.extractors._pdf_geometry import classify_conductor_color
from sistema.generation.clean_projeto import render_clean_projeto
from sistema.generation.croqui_geometrico import render_croqui_geometrico


ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "CROQUI IA" / "300001134401"
PROJECT = CASE_DIR / "300001134401 PROJETO A3.pdf"


def test_classificacao_usa_cores_cad_comprovadas():
    assert classify_conductor_color((0, 0, 1)) == "MT"
    assert classify_conductor_color((0, 0.699, 0)) == "BT"
    assert classify_conductor_color((0, 0.578, 1)) is None
    assert classify_conductor_color((0.398, 0.066, 0)) is None
    assert classify_conductor_color((0, 0, 0)) is None


def test_regressao_300001134401_preserva_geometria_real(tmp_path):
    extraction = base.get_extractor("projeto_pdf").extract("300001134401", PROJECT)
    assert sum(segment.tensao == "MT" for segment in extraction.conductors) == 125
    assert sum(segment.tensao == "BT" for segment in extraction.conductors) == 96
    assert round(sum(segment.length for segment in extraction.conductors if segment.tensao == "MT"), 1) == 3024.3
    assert round(sum(segment.length for segment in extraction.conductors if segment.tensao == "BT"), 1) == 5186.4
    assert len(extraction.poles) >= 45
    transformer_codes = {item.numero for item in extraction.transformers}
    assert {"1317501", "744770", "631892"} <= transformer_codes
    assert extraction.metadata["equipamento"] == "TR 631892"

    clean_pdf = tmp_path / "clean_projeto.pdf"
    clean_png = tmp_path / "clean_projeto.png"
    render_clean_projeto(PROJECT, extraction, clean_pdf, png_path=clean_png)
    assert clean_pdf.exists() and clean_png.exists()

    projeto = {
        "meta": {"equipamento": "TR 631892", "municipio": "CAXIAS DO SUL"},
        "equipamentos": [{"codigo": "1317501"}],
        "areas": [{"nome": "LM"}, {"nome": "LV"}],
    }
    croqui = tmp_path / "croqui.pdf"
    render_croqui_geometrico(extraction, projeto, croqui)
    doc = fitz.open(croqui)
    try:
        assert doc.page_count == 1
        assert round(doc[0].rect.width, 1) == 841.9
        assert round(doc[0].rect.height, 1) == 595.3
    finally:
        doc.close()
