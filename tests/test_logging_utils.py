import json

from app.logging_utils import log_event


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
