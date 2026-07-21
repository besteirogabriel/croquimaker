from croquimaker.core.gerador_croqui_v4 import _calcular_layout


def test_layout_ortogonal_com_ramal():
    nos = {f"P{i}": {"id": f"P{i}"} for i in range(1, 6)}
    trechos = [
        {"de": "P1", "para": "P2"},
        {"de": "P2", "para": "P3"},
        {"de": "P2", "para": "P4"},
        {"de": "P4", "para": "P5"},
    ]
    pos = _calcular_layout(nos, trechos)
    assert set(pos) == set(nos)
    ys = {}
    for _, y in pos.values():
        ys[y] = ys.get(y, 0) + 1
    assert max(ys.values()) >= 3
    for t in trechos:
        a = pos[t["de"]]
        b = pos[t["para"]]
        assert a[0] == b[0] or a[1] == b[1]
