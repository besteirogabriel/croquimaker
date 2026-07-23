from __future__ import annotations

import hashlib
from pathlib import Path

from sistema.generation.croqui_geometrico import _placement_direction
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

    expected_symbols = {
        "POSTE_EXISTENTE",
        "POSTE_NOVO",
        "TRANSFORMADOR_RGE",
        "CHAVE_FUSIVEL_SEM_ABERTURA_CARGA",
        "CHAVE_FUSIVEL_COM_ABERTURA_CARGA",
    }
    assert expected_symbols == set(catalog["symbols"])
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
    assert symbol_for_equipment("RELIGADOR") is None
    assert symbol_for_equipment("EQUIPAMENTO_DESCONHECIDO") is None


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
    assert branch_endpoint_direction[0] < 0
    assert branch_endpoint_direction[1] >= 0
