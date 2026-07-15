from croqui_engine.ingestion.page_classifier import classify_page


def test_classifies_tes_admin_page():
    page = classify_page(
        "TES Dados Gerais Numero: 31283669 Municipio: Caxias do Sul",
        width=595,
        height=842,
        page_index=0,
    )

    assert page.kind == "TES_ADMINISTRATIVO"
    assert page.confidence >= 0.7


def test_classifies_project_network_by_poles_and_spans():
    text = "(P1) (P2) (V1-2) 36.41m + 3E70-1A Gerencia de Obras e Manutencao"
    page = classify_page(text, width=1190, height=842, drawings_count=120)

    assert page.kind == "PROJETO_REDE"
    assert page.confidence > 0.5
