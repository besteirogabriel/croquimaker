from croqui_engine.rendering.layout_profile import default_layout_profile


def test_default_layout_profile_keeps_drawing_inside_page():
    profile = default_layout_profile()
    page_width, page_height = profile.page_size

    assert profile.name == "corpus-a4-landscape"
    assert profile.header_area.y1 < profile.drawing_area.y0
    assert profile.drawing_area.y1 < profile.viability_area.y0
    assert 0 <= profile.drawing_area.x0 < profile.drawing_area.x1 <= page_width
    assert 0 <= profile.viability_area.y0 < profile.viability_area.y1 <= page_height
