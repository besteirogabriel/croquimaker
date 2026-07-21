from croquimaker.core.schema import assert_schema, sanitizar_projeto


def test_sanitizar_normaliza_vaos_e_cria_nos():
    projeto = sanitizar_projeto({
        "meta": {},
        "nos": [{"id": "P1"}],
        "trechos": [{"nome": "V1-2", "tipo": "MT"}],
        "equipamentos": [{"tipo": "RELIGADOR", "no_id": "P99"}],
        "areas": [{"nos": "P1 P2 P2"}],
        "textos": [],
    })
    assert {n["id"] for n in projeto["nos"]} == {"P1", "P2"}
    assert projeto["trechos"][0]["de"] == "P1"
    assert projeto["trechos"][0]["para"] == "P2"
    assert projeto["equipamentos"][0]["no_id"] in {"P1", "P2"}
    assert projeto["areas"][0]["nos"] == "P1|P2"
    assert_schema(projeto)
