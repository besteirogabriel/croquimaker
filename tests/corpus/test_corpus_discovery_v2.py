from pathlib import Path

from croqui_engine.corpus.discovery import discover_corpus


def _touch(path: Path, content: bytes = b"fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_discover_corpus_classifies_complete_and_incomplete_cases(tmp_path):
    root = tmp_path / "CROQUI IA"
    complete = root / "300000000001"
    missing_target = root / "300000000002"

    _touch(complete / "PROJETO A1.pdf")
    _touch(complete / "Croqui TR 123456.pdf")
    _touch(complete / "Croqui TR 123456.xls")
    _touch(missing_target / "PROJETO A2.pdf")
    _touch(missing_target / "Croqui FU 654321.xls")

    registry = discover_corpus(root)

    assert registry.total_cases == 2
    assert registry.complete_cases == 1
    assert registry.missing_target_pdf == 1
    assert registry.equipment_type_counts == {"FU": 1, "TR": 1}

    case = registry.case_map()["300000000001"]
    assert case.status == "COMPLETE"
    assert case.project_pdfs[0].kind == "PROJECT_PDF"
    assert case.target_croqui_pdfs[0].kind == "TARGET_CROQUI_PDF"
    assert case.target_croqui_xls is not None
    assert case.equipment_type_from_name == "TR"
    assert case.equipment_code_from_name == "123456"
