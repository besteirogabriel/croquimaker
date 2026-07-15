from croqui_engine.parser.tes_parser import parse_tes_equipment, parse_tes_text

TES_TEXT = """
Numero: 31283669
Municipio: Caxias do Sul
Area de trabalho LM: Trocar postes, instalar vinte vao de MT novos,
retirar quatro vaos de MT, retirar FU 304220, instalar TRs 1297088,
1298166 novos.
Condicoes para a Execucao do Servico:
Area de trabalho LM: Abrir FC 1155828.
"""


def test_parse_tes_metadata():
    meta = parse_tes_text(TES_TEXT)

    assert meta["tes_number"] == "31283669"
    assert meta["municipality"] == "Caxias do Sul"
    assert meta["main_switching_equipment"] == "FC 1155828"


def test_parse_tes_equipment_actions():
    equipment = parse_tes_equipment(TES_TEXT)
    codes = {(item.code, item.type, item.status) for item in equipment}

    assert ("304220", "CHAVE_FUSIVEL", "retirar") in codes
    assert ("1155828", "CHAVE_COMANDO", "abrir") in codes
    assert ("1297088", "TRANSFORMADOR", "instalar") in codes
    assert ("1298166", "TRANSFORMADOR", "instalar") in codes
