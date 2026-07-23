from croquimaker.core.schema import (
    assert_schema,
    normalizar_viabilidade,
    sanitizar_projeto,
    viabilidade_automatica,
)


def test_sanitizar_normaliza_vaos_e_cria_nos():
    projeto = sanitizar_projeto({
        "meta": {},
        "nos": [{"id": "P1"}],
        "trechos": [{"nome": "V1-2", "tipo": "MT"}],
        "equipamentos": [{"tipo": "RELIGADOR", "no_id": "P99"}],
        "areas": [{
            "nome": "Área de trabalho",
            "tipo": "LM",
            "nos": "P1 P2 P2",
            "observacao": "Instalar transformador",
        }],
        "textos": [],
    })
    assert {n["id"] for n in projeto["nos"]} == {"P1", "P2"}
    assert projeto["trechos"][0]["de"] == "P1"
    assert projeto["trechos"][0]["para"] == "P2"
    assert projeto["equipamentos"][0]["no_id"] in {"P1", "P2"}
    assert projeto["areas"] == [{
        "nome": "Área de trabalho",
        "tipo": "LM",
        "nos": "P1 P2",
        "observacao": "Instalar transformador",
    }]
    assert_schema(projeto)


def test_viabilidade_invalida_nunca_vira_confirmacao_implicita():
    assert normalizar_viabilidade(["Sim", "talvez"]) == [
        "Sim",
        "Não Avaliado",
        *(["Não Avaliado"] * 8),
    ]


def test_viabilidade_automatica_segue_perfil_padrao_rge():
    assert viabilidade_automatica() == ["Sim"] * 9 + ["Não"]
