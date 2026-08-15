from dataclasses import dataclass
from pathlib import Path

from app import cutter as cutter_module
from app import ffmpeg_utils as ffmpeg_utils_module
from app.analysis import AnalysisRow, ChapterReport, DryRunReport
from app.config import Settings
from app.cutter import CutterError, generate_cuts


def _settings(tmp_path):
    return Settings(
        projetos_dir=tmp_path / "projetos",
        whisper_model="tiny",
        whisper_language="pt",
        ffmpeg_crf=18,
        ffmpeg_preset="medium",
        audio_bitrate_kbps=192,
        output_format="mp4",
        max_video_height=None,
        analysis_provider="claude",
        analysis_model="claude-sonnet-5",
        analysis_temperature=0.0,
        default_brand="generic",
        brands_dir=tmp_path / "brands",
        thumbnail_provider="manual",
        editorial_provider="claude",
        editorial_model="claude-sonnet-5",
        editorial_temperature=0.0,
    )


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _patch_ffmpeg(monkeypatch, returncode=0, stderr=""):
    def _fake_run(cmd, capture_output=True, text=True):
        if returncode == 0:
            Path(cmd[-1]).write_bytes(b"fake cut bytes")
        return _FakeCompletedProcess(returncode=returncode, stderr=stderr)

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)


def _make_report(tmp_path, chapters):
    project_dir = tmp_path / "projeto"
    (project_dir / "original").mkdir(parents=True)
    video_path = project_dir / "original" / "video-original.mp4"
    video_path.write_bytes(b"fake video")
    report = DryRunReport(
        project_dir=project_dir,
        video_path=video_path,
        video_duration_seconds=6303.0,
        csv_path=project_dir / "03 Analise.csv",
        chapters=chapters,
        warnings=[],
    )
    return project_dir, report


def _ok_chapter(**overrides):
    defaults = dict(
        ordem_publicacao="8",
        capitulo="8",
        acao_editorial="Manter",
        titulo_sugerido="Não vou ser usado pelo Centrão",
    )
    defaults.update(overrides)
    row = AnalysisRow(**defaults)
    return ChapterReport(row=row, status="ok", start_seconds=1747.0, end_seconds=2242.0)


def test_generate_cuts_creates_file_with_expected_name(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _patch_ffmpeg(monkeypatch)
    project_dir, report = _make_report(tmp_path, [_ok_chapter()])

    result = generate_cuts(report, project_dir, settings)

    assert result.cut_count == 1
    outcome = result.outcomes[0]
    assert outcome.status == "cut"
    assert outcome.output_path.name == "008_cap08_nao-vou-ser-usado-pelo-centrao.mp4"
    assert outcome.output_path.exists()


def test_generate_cuts_calls_on_progress_before_each_eligible_cut(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _patch_ffmpeg(monkeypatch)
    project_dir, report = _make_report(
        tmp_path,
        [
            _ok_chapter(ordem_publicacao="1", capitulo="1"),
            _ok_chapter(ordem_publicacao="2", capitulo="2"),
        ],
    )

    seen = []
    result = generate_cuts(report, project_dir, settings, on_progress=seen.append)

    assert len(seen) == 2
    assert [c.row.capitulo for c in seen] == ["1", "2"]
    assert result.cut_count == 2


def test_generate_cuts_does_not_call_on_progress_for_ineligible_chapters(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    row = AnalysisRow(ordem_publicacao="1", capitulo="1", acao_editorial="Unir")
    chapter = ChapterReport(row=row, status="manual_action", message="requer edição manual")
    project_dir, report = _make_report(tmp_path, [chapter])

    def _fail_if_called(cmd, capture_output=True, text=True):
        raise AssertionError("ffmpeg não deveria ser chamado")

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fail_if_called)

    seen = []
    generate_cuts(report, project_dir, settings, on_progress=seen.append)

    assert seen == []


def test_generate_cuts_precise_mode_uses_libx264_with_settings(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    captured = {}

    def _fake_run(cmd, capture_output=True, text=True):
        captured["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"fake")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)
    project_dir, report = _make_report(tmp_path, [_ok_chapter()])

    generate_cuts(report, project_dir, settings, mode="precise")

    cmd = captured["cmd"]
    assert "-c:v" in cmd
    assert "libx264" in cmd
    assert "18" in cmd
    assert "medium" in cmd
    assert "192k" in cmd


def test_generate_cuts_fast_mode_uses_stream_copy(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    captured = {}

    def _fake_run(cmd, capture_output=True, text=True):
        captured["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"fake")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)
    project_dir, report = _make_report(tmp_path, [_ok_chapter()])

    generate_cuts(report, project_dir, settings, mode="fast")

    cmd = captured["cmd"]
    assert "copy" in cmd
    assert "libx264" not in cmd


def test_generate_cuts_skips_existing_file(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir, report = _make_report(tmp_path, [_ok_chapter()])
    cortes_dir = project_dir / "cortes"
    cortes_dir.mkdir()
    existing = cortes_dir / "008_cap08_nao-vou-ser-usado-pelo-centrao.mp4"
    existing.write_bytes(b"ja existe")

    def _fail_if_called(cmd, capture_output=True, text=True):
        raise AssertionError("ffmpeg não deveria ser chamado quando o arquivo já existe")

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fail_if_called)

    result = generate_cuts(report, project_dir, settings)

    assert result.cut_count == 0
    assert result.outcomes[0].status == "skipped_exists"
    assert existing.read_bytes() == b"ja existe"


def test_generate_cuts_marks_invalid_ordem_publicacao_as_error(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir, report = _make_report(tmp_path, [_ok_chapter(ordem_publicacao="abc")])

    def _fail_if_called(cmd, capture_output=True, text=True):
        raise AssertionError("ffmpeg não deveria ser chamado")

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fail_if_called)

    result = generate_cuts(report, project_dir, settings)

    assert result.outcomes[0].status == "error"
    assert "Ordem Publicacao" in result.outcomes[0].message


def test_generate_cuts_marks_invalid_capitulo_as_error(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir, report = _make_report(tmp_path, [_ok_chapter(capitulo="")])

    def _fail_if_called(cmd, capture_output=True, text=True):
        raise AssertionError("ffmpeg não deveria ser chamado")

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fail_if_called)

    result = generate_cuts(report, project_dir, settings)

    assert result.outcomes[0].status == "error"
    assert "Capitulo" in result.outcomes[0].message


def test_generate_cuts_ffmpeg_failure_does_not_abort_other_rows(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    calls = {"count": 0}

    def _fake_run(cmd, capture_output=True, text=True):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeCompletedProcess(returncode=1, stderr="erro de codec")
        Path(cmd[-1]).write_bytes(b"fake")
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)
    project_dir, report = _make_report(
        tmp_path,
        [
            _ok_chapter(ordem_publicacao="1", capitulo="1"),
            _ok_chapter(ordem_publicacao="2", capitulo="2"),
        ],
    )

    result = generate_cuts(report, project_dir, settings)

    assert result.outcomes[0].status == "error"
    assert result.outcomes[1].status == "cut"
    assert result.cut_count == 1


def test_generate_cuts_skips_ineligible_chapters(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    row = AnalysisRow(ordem_publicacao="1", capitulo="1", acao_editorial="Unir")
    chapter = ChapterReport(row=row, status="manual_action", message="requer edição manual")
    project_dir, report = _make_report(tmp_path, [chapter])

    def _fail_if_called(cmd, capture_output=True, text=True):
        raise AssertionError("ffmpeg não deveria ser chamado")

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fail_if_called)

    result = generate_cuts(report, project_dir, settings)

    assert result.outcomes[0].status == "skipped_ineligible"
    assert result.cut_count == 0


def test_generate_cuts_raises_when_ffmpeg_missing(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    project_dir, report = _make_report(tmp_path, [_ok_chapter()])
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: None)

    def _fail_if_called(cmd, capture_output=True, text=True):
        raise AssertionError("ffmpeg não deveria ser chamado")

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fail_if_called)

    try:
        generate_cuts(report, project_dir, settings)
        assert False, "deveria ter levantado CutterError"
    except CutterError as exc:
        assert "FFmpeg" in str(exc)
