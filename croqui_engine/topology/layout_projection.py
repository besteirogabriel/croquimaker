from __future__ import annotations


def project_to_croqui_space(x: float, y: float, page_size: tuple[float, float]) -> tuple[float, float]:
    width, height = page_size
    return (x / width if width else x, y / height if height else y)

