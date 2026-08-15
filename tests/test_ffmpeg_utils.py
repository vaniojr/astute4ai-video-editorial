from dataclasses import dataclass

from app import ffmpeg_utils as ffmpeg_utils_module
from app.ffmpeg_utils import is_binary_available, run, truncate_stderr


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
