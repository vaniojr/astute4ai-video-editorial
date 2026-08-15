from dataclasses import dataclass
from pathlib import Path

import pytest

from app import ffmpeg_utils as ffmpeg_utils_module
from app.thumbnail_frames import (
    ThumbnailFramesError,
    compute_frame_offsets,
    extract_frames,
)


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def test_compute_frame_offsets_returns_requested_count():
    offsets = compute_frame_offsets(100.0, count=9)
    assert len(offsets) == 9
    assert offsets[0] == 0.0
    assert offsets[-1] < 100.0


def test_compute_frame_offsets_covers_expected_anchors():
    offsets = compute_frame_offsets(100.0, count=9)
    assert offsets[0] == 0.0
    assert offsets[2] == pytest.approx(24.975, abs=0.5)
    assert offsets[4] == pytest.approx(49.95, abs=0.5)
    assert offsets[6] == pytest.approx(74.925, abs=0.5)


def test_compute_frame_offsets_raises_on_invalid_duration():
    with pytest.raises(ThumbnailFramesError):
        compute_frame_offsets(0.0)


def test_compute_frame_offsets_raises_on_count_below_two():
    with pytest.raises(ThumbnailFramesError):
        compute_frame_offsets(100.0, count=1)


def test_extract_frames_raises_when_ffmpeg_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: None)

    with pytest.raises(ThumbnailFramesError) as exc_info:
        extract_frames(tmp_path / "corte.mp4", tmp_path / "frames", 60.0)
    assert "FFmpeg" in str(exc_info.value)


def test_extract_frames_writes_one_file_per_offset(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: f"/usr/bin/{name}")

    def _fake_run(cmd, capture_output=True, text=True):
        Path(cmd[-1]).write_bytes(b"fake jpeg")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)

    frame_paths = extract_frames(tmp_path / "corte.mp4", tmp_path / "frames", 60.0, count=5)

    assert len(frame_paths) == 5
    assert [p.name for p in frame_paths] == [
        "frame-01.jpg",
        "frame-02.jpg",
        "frame-03.jpg",
        "frame-04.jpg",
        "frame-05.jpg",
    ]
    for path in frame_paths:
        assert path.exists()


def test_extract_frames_raises_and_stops_on_first_ffmpeg_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    calls = {"count": 0}

    def _fake_run(cmd, capture_output=True, text=True):
        calls["count"] += 1
        if calls["count"] == 2:
            return _FakeCompletedProcess(returncode=1, stderr="erro de seek")
        Path(cmd[-1]).write_bytes(b"fake jpeg")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)

    with pytest.raises(ThumbnailFramesError) as exc_info:
        extract_frames(tmp_path / "corte.mp4", tmp_path / "frames", 60.0, count=5)
    assert "erro de seek" in str(exc_info.value)
    assert calls["count"] == 2
