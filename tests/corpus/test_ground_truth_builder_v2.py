from pathlib import Path

import fitz
import xlwt

from croqui_engine.corpus.models import CorpusFile, GoldenCase
from croqui_engine.ground_truth.target_builder import build_target_for_case


def _make_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=420, height=300)
    page.insert_text((24, 40), "Municipio TESTE Equipamento TR 123456")
    page.insert_text((24, 240), "Avaliacao de viabilidade")
    page.draw_line((40, 120), (320, 120))
    doc.save(path)
    doc.close()


def _make_xls(path: Path) -> None:
    book = xlwt.Workbook()
    sheet = book.add_sheet("Croqui")
    sheet.write(0, 0, "TR 123456")
    simbologia = book.add_sheet("Simbologia")
    simbologia.write(0, 0, "Transformador")
    book.save(str(path))


def _corpus_file(path: Path, kind: str) -> CorpusFile:
    return CorpusFile(path=str(path), name=path.name, kind=kind, size_bytes=path.stat().st_size, sha256="x")


def test_build_target_for_case_extracts_pdf_and_xls(tmp_path, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    pdf_path = case_dir / "Croqui TR 123456.pdf"
    xls_path = case_dir / "Croqui TR 123456.xls"
    _make_pdf(pdf_path)
    _make_xls(xls_path)

    monkeypatch.setattr(
        "croqui_engine.ground_truth.target_builder.ground_truth_dir",
        lambda case_id: tmp_path / "ground_truth" / case_id,
    )

    case = GoldenCase(
        case_id="case-001",
        directory=str(case_dir),
        project_pdfs=[],
        target_croqui_pdfs=[_corpus_file(pdf_path, "TARGET_CROQUI_PDF")],
        target_croqui_xls=_corpus_file(xls_path, "TARGET_CROQUI_XLS"),
        status="COMPLETE",
    )

    payload = build_target_for_case(case)

    assert payload.extracted_from_pdf is True
    assert payload.extracted_from_xls is True
    assert payload.page_size == (420.0, 300.0)
    assert payload.lines
    assert any(text.label == "Municipio" for text in payload.texts)
    assert payload.xls_profile["sheet_names"] == ["Croqui", "Simbologia"]
    assert (tmp_path / "ground_truth" / "case-001" / "target_payload.json").exists()
