from croqui_engine.parser.equipment_parser import parse_equipment_from_text
from croqui_engine.parser.span_parser import parse_spans


def test_parse_spans_with_length_and_cable():
    text = """
    (V1-2) 36.41m + 3E70-1A # 3 ESP. # + EPP953
    (V17-18) 34.26m + 3E70-1A # 3ESP
    """

    spans = parse_spans(text)

    assert spans[0].id == "V1-2"
    assert spans[0].from_node == "P1"
    assert spans[0].to_node == "P2"
    assert spans[0].length_m == 36.41
    assert spans[0].cable == "3E70-1A"
    assert spans[1].id == "V17-18"
    assert spans[1].length_m == 34.26


def test_parse_equipment_synthetic_text():
    equipment = parse_equipment_from_text(
        "1297088 45.00 kVA 13.8-380\n304220 25K Proprio\nFaca LB 1155828"
    )
    by_code = {item.code: item.type for item in equipment}

    assert by_code["1297088"] == "TRANSFORMADOR"
    assert by_code["304220"] == "CHAVE_FUSIVEL"
    assert by_code["1155828"] == "CHAVE_COMANDO"
