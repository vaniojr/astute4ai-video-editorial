import json
from dataclasses import dataclass

import pytest

from app import ffmpeg_utils as ffmpeg_utils_module
from app.ffmpeg_utils import is_binary_available, probe_video_properties, run, truncate_stderr


def test_is_binary_available_true_when_which_finds_it(monkeypatch):
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert is_binary_available("ffmpeg") is True


def test_is_binary_available_false_when_which_returns_none(monkeypatch):
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: None)
    assert is_binary_available("ffmpeg") is False


def test_run_delegates_to_subprocess_run(monkeypatch):
    @dataclass
    class _FakeCompletedProcess:
        returncode: int
        stdout: str = ""
        stderr: str = ""

    captured = {}

    def _fake_run(cmd, capture_output=True, text=True):
        captured["cmd"] = cmd
        captured["capture_output"] = capture_output
        captured["text"] = text
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)

    result = run(["ffmpeg", "-version"])

    assert result.returncode == 0
    assert captured["cmd"] == ["ffmpeg", "-version"]
    assert captured["capture_output"] is True
    assert captured["text"] is True


def test_truncate_stderr_strips_and_limits_length():
    long_stderr = "  " + ("x" * 3000) + "  "
    result = truncate_stderr(long_stderr)
    assert result == ("x" * 2000)
    assert len(result) == 2000


def _fake_ffprobe_json(monkeypatch, streams):
    @dataclass
    class _FakeCompletedProcess:
        returncode: int
        stdout: str = ""
        stderr: str = ""

    def _fake_run(cmd, capture_output=True, text=True):
        return _FakeCompletedProcess(returncode=0, stdout=json.dumps({"streams": streams}))

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)


def test_probe_video_properties_parses_video_and_audio_streams(monkeypatch):
    _fake_ffprobe_json(
        monkeypatch,
        [
            {"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1"},
            {"codec_type": "audio", "sample_rate": "44100"},
        ],
    )

    props = probe_video_properties("corte.mp4")

    assert props.width == 1920
    assert props.height == 1080
    assert props.fps == 30.0
    assert props.sample_rate == 44100


def test_probe_video_properties_parses_fractional_frame_rate(monkeypatch):
    _fake_ffprobe_json(
        monkeypatch,
        [{"codec_type": "video", "width": 1280, "height": 720, "r_frame_rate": "30000/1001"}],
    )

    props = probe_video_properties("corte.mp4")

    assert props.fps == pytest.approx(29.97, abs=0.01)


def test_probe_video_properties_defaults_sample_rate_when_no_audio_stream(monkeypatch):
    _fake_ffprobe_json(
        monkeypatch, [{"codec_type": "video", "width": 640, "height": 360, "r_frame_rate": "25/1"}]
    )

    props = probe_video_properties("corte.mp4")

    assert props.sample_rate == 48000


def test_probe_video_properties_raises_when_ffprobe_fails(monkeypatch):
    @dataclass
    class _FakeCompletedProcess:
        returncode: int
        stdout: str = ""
        stderr: str = ""

    monkeypatch.setattr(
        ffmpeg_utils_module.subprocess,
        "run",
        lambda cmd, capture_output=True, text=True: _FakeCompletedProcess(returncode=1, stderr="erro"),
    )

    with pytest.raises(RuntimeError):
        probe_video_properties("corte.mp4")


def test_probe_video_properties_raises_when_no_video_stream(monkeypatch):
    _fake_ffprobe_json(monkeypatch, [{"codec_type": "audio", "sample_rate": "48000"}])

    with pytest.raises(RuntimeError):
        probe_video_properties("corte.mp4")
