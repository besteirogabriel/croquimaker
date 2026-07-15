from pathlib import Path
from types import SimpleNamespace

import fitz

from croqui_engine.core.models import TechnicalPayload
from croqui_engine.corpus.matcher import find_project_match
from croqui_engine.corpus.models import CorpusFile, CorpusRegistry, GoldenCase
from croqui_engine.corpus.reference_outputs import generate_reference_outputs_if_available


def _write_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=240, height=160)
    page.insert_text((24, 50), text)
    doc.save(path)
    doc.close()


def _corpus_file(path: Path, kind: str, sha256: str) -> CorpusFile:
    return CorpusFile(
        path=str(path),
        name=path.name,
        kind=kind,
        size_bytes=path.stat().st_size,
        sha256=sha256,
    )


def test_find_project_match_uses_project_sha256(tmp_path, monkeypatch):
    from croqui_engine.corpus.discovery import sha256_file

    project = tmp_path / "6722545 PROJETO A2.pdf"
    target = tmp_path / "CROQUI TR 631802 TES.pdf"
    _write_pdf(project, "Projeto bruto")
    _write_pdf(target, "Croqui aprovado")
    digest = sha256_file(project)
    registry = CorpusRegistry(
        source_path=str(tmp_path),
        cases=[
            GoldenCase(
                case_id="6722545",
                directory=str(tmp_path),
                project_pdfs=[_corpus_file(project, "PROJECT_PDF", digest)],
                target_croqui_pdfs=[_corpus_file(target, "TARGET_CROQUI_PDF", "target")],
                equipment_type_from_name="TR",
                equipment_code_from_name="631802",
                status="COMPLETE",
            )
        ],
    )
    monkeypatch.setattr("croqui_engine.corpus.matcher.load_registry", lambda: registry)

    match = find_project_match(project)

    assert match is not None
    assert match.case_id == "6722545"
    assert match.equipment_code == "631802"
    assert match.target_pdf_name == "CROQUI TR 631802 TES.pdf"


def test_generate_reference_outputs_copies_approved_pdf_and_xls(tmp_path, monkeypatch):
    from croqui_engine.corpus.discovery import sha256_file

    project = tmp_path / "6722545 PROJETO A2.pdf"
    target_pdf = tmp_path / "CROQUI TR 631802 TES.pdf"
    target_xls = tmp_path / "CROQUI TR 631802 TES.xls"
    _write_pdf(project, "Projeto bruto")
    _write_pdf(target_pdf, "Croqui aprovado")
    target_xls.write_bytes(b"approved xls")
    digest = sha256_file(project)
    registry = CorpusRegistry(
        source_path=str(tmp_path),
        cases=[
            GoldenCase(
                case_id="6722545",
                directory=str(tmp_path),
                project_pdfs=[_corpus_file(project, "PROJECT_PDF", digest)],
                target_croqui_pdfs=[_corpus_file(target_pdf, "TARGET_CROQUI_PDF", "target")],
                target_croqui_xls=_corpus_file(target_xls, "TARGET_CROQUI_XLS", "xls"),
                status="COMPLETE",
            )
        ],
    )
    monkeypatch.setattr("croqui_engine.corpus.matcher.load_registry", lambda: registry)
    monkeypatch.setattr(
        "croqui_engine.corpus.reference_outputs.settings",
        SimpleNamespace(use_corpus_reference_outputs=True),
    )

    payload = TechnicalPayload(job_id="job-001")
    pdf_out = tmp_path / "out" / "croqui_final.pdf"
    png_out = tmp_path / "out" / "croqui_final.png"
    xls_out = tmp_path / "out" / "croqui_final.xls"

    used = generate_reference_outputs_if_available(payload, project, pdf_out, png_out, xls_out)

    assert used is True
    assert pdf_out.read_bytes() == target_pdf.read_bytes()
    assert xls_out.read_bytes() == b"approved xls"
    assert png_out.exists()
    assert payload.meta["output_mode"] == "CORPUS_REFERENCE_APPROVED"
    assert payload.meta["corpus_case_id"] == "6722545"
    assert {item.code for item in payload.validations} >= {
        "CORPUS_PROJECT_MATCH",
        "CORPUS_REFERENCE_OUTPUT_USED",
    }


def test_reference_output_copy_is_disabled_without_explicit_calibration_mode(tmp_path, monkeypatch):
    from croqui_engine.corpus.discovery import sha256_file

    project = tmp_path / "novo PROJETO A2.pdf"
    target_pdf = tmp_path / "CROQUI TR 111111 TES.pdf"
    _write_pdf(project, "Projeto bruto")
    _write_pdf(target_pdf, "Croqui aprovado")
    digest = sha256_file(project)
    registry = CorpusRegistry(
        source_path=str(tmp_path),
        cases=[
            GoldenCase(
                case_id="case-001",
                directory=str(tmp_path),
                project_pdfs=[_corpus_file(project, "PROJECT_PDF", digest)],
                target_croqui_pdfs=[_corpus_file(target_pdf, "TARGET_CROQUI_PDF", "target")],
                status="COMPLETE",
            )
        ],
    )
    monkeypatch.setattr("croqui_engine.corpus.matcher.load_registry", lambda: registry)
    monkeypatch.setattr(
        "croqui_engine.corpus.reference_outputs.settings",
        SimpleNamespace(use_corpus_reference_outputs=False),
    )

    used = generate_reference_outputs_if_available(
        TechnicalPayload(job_id="job-001"),
        project,
        tmp_path / "out" / "croqui_final.pdf",
        tmp_path / "out" / "croqui_final.png",
        tmp_path / "out" / "croqui_final.xls",
    )

    assert used is False
