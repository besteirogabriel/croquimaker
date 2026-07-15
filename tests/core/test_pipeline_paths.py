from __future__ import annotations

from types import SimpleNamespace

from croqui_engine.core import pipeline


def test_path_for_payload_allows_shared_upload_dir_outside_release(tmp_path, monkeypatch):
    release_root = tmp_path / "releases" / "release-20260710120635"
    shared_thumb = tmp_path / "shared" / "data" / "uploads" / "job123" / "pages" / "page_001.png"
    shared_thumb.parent.mkdir(parents=True)
    shared_thumb.write_bytes(b"png")
    monkeypatch.setattr(pipeline, "settings", SimpleNamespace(root_dir=release_root))

    assert pipeline._path_for_payload(shared_thumb) == str(shared_thumb)


def test_path_for_payload_keeps_relative_path_inside_release(tmp_path, monkeypatch):
    release_root = tmp_path / "releases" / "release-20260710120635"
    thumb = release_root / "data" / "uploads" / "job123" / "pages" / "page_001.png"
    thumb.parent.mkdir(parents=True)
    thumb.write_bytes(b"png")
    monkeypatch.setattr(pipeline, "settings", SimpleNamespace(root_dir=release_root))

    assert pipeline._path_for_payload(thumb) == "data/uploads/job123/pages/page_001.png"
