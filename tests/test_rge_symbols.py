from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
from reportlab.pdfgen import canvas

from sistema.generation.croqui_geometrico import (
    _draw_equipment,
    _placement_direction,
)
from sistema.generation.equipment_scene import SceneEquipment
from sistema.generation.rge_symbols import (
    load_rge_symbol_catalog,
    symbol_for_equipment,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_WORKBOOK = ROOT / "data" / "templates" / "croqui_template.xls"


def test_catalogo_vem_da_aba_simbologia_do_excel_de_referencia():
    catalog = load_rge_symbol_catalog()
    source = catalog["source"]

    assert source["sheet"] == "Simbologia"
    assert source["workbook"] == "data/templates/croqui_template.xls"
    assert source["sha256"] == hashlib.sha256(
        REFERENCE_WORKBOOK.read_bytes()
    ).hexdigest()

    required_symbols = {
        "POSTE_EXISTENTE",
        "POSTE_NOVO",
        "TRANSFORMADOR_RGE",
        "TRANSFORMADOR_PARTICULAR",
        "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA",
        "CHAVE_FUSIVEL_COM_ABERTURA_CARGA",
        "CHAVE_FUSIVEL_RELIGADORA",
        "CHAVE_FACA_SEM_ABERTURA_CARGA",
        "CHAVE_FACA_COM_ABERTURA_CARGA",
        "RELIGADOR",
        "SECCIONALIZADORA",
        "ATERRAMENTO_BT",
        "ATERRAMENTO_AT",
        "FIM_REDE_PRIMARIA",
        "FIM_REDE_SECUNDARIA",
        "ELEMENTO_RETIRAR",
        "ELEMENTO_DESLOCAR",
        "ESTAI",
    }
    assert catalog["version"] == 2
    assert len(catalog["symbols"]) >= 40
    assert required_symbols <= set(catalog["symbols"])
    assert all(
        symbol["sheet"] == "Simbologia" and symbol["paths"]
        for symbol in catalog["symbols"].values()
    )


def test_mapeamento_nao_inventa_simbolo_generico():
    assert symbol_for_equipment("TRANSFORMADOR_RGE") == "TRANSFORMADOR_RGE"
    assert (
        symbol_for_equipment("CHAVE_FUSIVEL_SEM_CARGA")
        == "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA"
    )
    assert (
        symbol_for_equipment("CHAVE_FUSIVEL_COM_CARGA")
        == "CHAVE_FUSIVEL_COM_ABERTURA_CARGA"
    )
    assert symbol_for_equipment("CHAVE_FUSIVEL_RELIGADORA") == "CHAVE_FUSIVEL_RELIGADORA"
    assert symbol_for_equipment("CHAVE_FACA_SEM_CARGA") == "CHAVE_FACA_SEM_ABERTURA_CARGA"
    assert symbol_for_equipment("RELIGADOR") == "RELIGADOR"
    assert symbol_for_equipment("ATERRAMENTO_BT") == "ATERRAMENTO_BT"
    assert symbol_for_equipment("EQUIPAMENTO_DESCONHECIDO") is None


def test_transformador_a_instalar_preserva_cor_e_preenchimento_do_excel(tmp_path):
    output = tmp_path / "transformador_instalar.pdf"
    pdf = canvas.Canvas(str(output), pagesize=(100, 100))
    _draw_equipment(
        pdf,
        SceneEquipment(
            code="910001",
            kind="TRANSFORMADOR_RGE",
            state="INSTALAR",
            pole_index=0,
            new=True,
        ),
        50,
        60,
        (0.0, -1.0),
    )
    pdf.showPage()
    pdf.save()

    with fitz.open(output) as document:
        drawings = document[0].get_drawings()
        assert any(
            drawing.get("color") == (0.0, 0.0, 0.0)
            and drawing.get("fill") == (1.0, 1.0, 1.0)
            for drawing in drawings
        )
        assert not any(
            color is not None
            and color[0] >= 0.9
            and color[1] <= 0.1
            and color[2] <= 0.1
            for drawing in drawings
            for color in (drawing.get("color"), drawing.get("fill"))
        )
        identifier_spans = [
            span
            for block in document[0].get_text("dict")["blocks"]
            for line in block.get("lines", [])
            for span in line.get("spans", [])
            if span["text"] == "910001"
        ]
        assert identifier_spans
        assert all(span["color"] == 0 for span in identifier_spans)


def test_posicionamento_fica_fora_dos_condutores():
    transformer_direction = _placement_direction(
        pole=(10.0, 10.0),
        center=(10.0, 0.0),
        incident=[(0.0, 1.0), (0.0, -1.0)],
        right_bias=1.1,
    )
    assert transformer_direction[0] >= 0.35

    endpoint_direction = _placement_direction(
        pole=(10.0, 10.0),
        center=(20.0, 10.0),
        incident=[(1.0, 0.0)],
    )
    assert endpoint_direction[0] < 0

    branch_endpoint_direction = _placement_direction(
        pole=(0.0, 0.0),
        center=(10.0, -10.0),
        incident=[(-0.2, -1.0)],
    )
    assert branch_endpoint_direction == (0.0, 1.0)

    for direction in (
        transformer_direction,
        endpoint_direction,
        branch_endpoint_direction,
    ):
        assert direction in {
            (1.0, 0.0),
            (0.0, 1.0),
            (-1.0, 0.0),
            (0.0, -1.0),
        }
