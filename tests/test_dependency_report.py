from croqui_engine.generators.dependency_report_generator import generate_dependency_report


def test_dependency_report_is_generated(tmp_path):
    output = tmp_path / "jobel_dependencias.pdf"

    path = generate_dependency_report(output)

    assert path.exists()
    assert path.stat().st_size > 1000
