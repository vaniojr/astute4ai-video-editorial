import json

import pytest

from app.logging_utils import log_event, log_operation


def test_log_event_writes_expected_fields(tmp_path):
    project_dir = tmp_path / "projeto"
    project_dir.mkdir()

    log_event(project_dir, etapa="cut", comando="cut PROJECT --dry-run=False", resultado="ok")

    log_path = project_dir / "logs" / "pipeline.log"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["etapa"] == "cut"
    assert entry["comando"] == "cut PROJECT --dry-run=False"
    assert entry["resultado"] == "ok"
    assert entry["erro"] is None
    assert "timestamp" in entry


def test_log_event_appends_multiple_entries(tmp_path):
    project_dir = tmp_path / "projeto"
    project_dir.mkdir()

    log_event(project_dir, etapa="cut", comando="cut PROJECT --dry-run=True", resultado="ok")
    log_event(
        project_dir,
        etapa="cut",
        comando="cut PROJECT --dry-run=False",
        resultado="erro",
        erro="FFmpeg falhou",
    )

    log_path = project_dir / "logs" / "pipeline.log"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    second = json.loads(lines[1])
    assert second["resultado"] == "erro"
    assert second["erro"] == "FFmpeg falhou"


def _read_log_lines(project_dir):
    log_path = project_dir / "logs" / "pipeline.log"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]


def test_log_operation_success_writes_start_and_end_with_duration(tmp_path):
    project_dir = tmp_path / "projeto"
    project_dir.mkdir()

    with log_operation(project_dir, etapa="download", comando="download PROJECT"):
        pass

    entries = _read_log_lines(project_dir)
    assert len(entries) == 2
    assert entries[0]["resultado"] == "iniciado"
    assert entries[1]["resultado"] == "ok"
    assert "duracao_segundos" in entries[1]
    assert entries[1]["duracao_segundos"] >= 0


def test_log_operation_failure_writes_start_and_error_and_reraises(tmp_path):
    project_dir = tmp_path / "projeto"
    project_dir.mkdir()

    class _BoomError(Exception):
        pass

    with pytest.raises(_BoomError):
        with log_operation(project_dir, etapa="audio", comando="audio PROJECT"):
            raise _BoomError("falha simulada")

    entries = _read_log_lines(project_dir)
    assert len(entries) == 2
    assert entries[0]["resultado"] == "iniciado"
    assert entries[1]["resultado"] == "erro"
    assert entries[1]["erro"] == "falha simulada"
    assert "duracao_segundos" in entries[1]


def test_log_operation_yields_mutable_extra_included_in_success_line(tmp_path):
    project_dir = tmp_path / "projeto"
    project_dir.mkdir()

    with log_operation(project_dir, etapa="analyze", comando="analyze PROJECT") as extra:
        extra["provider"] = "claude"
        extra["input_tokens"] = 123

    entries = _read_log_lines(project_dir)
    assert entries[1]["provider"] == "claude"
    assert entries[1]["input_tokens"] == 123
