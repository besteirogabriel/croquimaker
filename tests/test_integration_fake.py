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
    doc.save(pdf)
    doc.close()
    result = gerar(pdf, tmp_path / "job")
    assert result["sha256"]
    assert (tmp_path / "job/croqui.pdf").exists()
