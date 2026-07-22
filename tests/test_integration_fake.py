from pathlib import Path

import fitz

from croquimaker.core.pipeline import gerar


def test_pipeline_com_provedor_simulado(tmp_path, monkeypatch):
    monkeypatch.setenv("CROQUIMAKER_PROVIDER", "fake")
    monkeypatch.chdir(tmp_path)
    pdf = tmp_path / "entrada.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Projeto teste P1 P2 P3 V1-2 V2-3")
    page.draw_line((60, 130), (300, 130), color=(0, 0, 1), width=1)
    page.draw_line((180, 80), (180, 300), color=(0, 0.7, 0), width=1)
    doc.save(pdf)
    doc.close()
    result = gerar(pdf, tmp_path / "job")
    assert result["sha256"]
    assert result["engine"] == "geometry-cad-v2-dynamic-areas"
    assert (tmp_path / "job/croqui.pdf").exists()
    assert (tmp_path / "job/clean_projeto.pdf").exists()
    assert (tmp_path / "job/clean_projeto.png").exists()
    assert (tmp_path / "job/projeto.json").exists()
    assert not (tmp_path / "job/croqui.xls").exists()
    with fitz.open(tmp_path / "job/croqui.pdf") as result_pdf:
        assert "AREA DE TRABALHO" not in result_pdf[0].get_text().upper()
