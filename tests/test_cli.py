import json
from datetime import date

from typer.testing import CliRunner

from app import project as project_module
from app.analysis import AnalysisError, AnalysisRow, ChapterReport, DryRunReport
from app.analyzer import AnalysisPlan, AnalysisServiceError, AnalyzeResult
from app.audio import AudioError, AudioResult
from app.cutter import CutOutcome, CutRunResult, CutterError
from app.downloader import DownloadError, DownloadResult
from app.metadata import MetadataError, VideoMetadata
from app.transcriber import TranscribeResult, TranscriptionError, TranscriptSegment
from cli import main as cli_main
from cli.main import app

runner = CliRunner()


def _configure_brands_env(tmp_path, monkeypatch):
    """Aponta VIDEO_EDITORIAL_BRANDS_DIR para um fixture isolado (não o brands/ real do repo)."""
    brands_dir = tmp_path / "brands"
    generic_dir = brands_dir / "generic"
    generic_dir.mkdir(parents=True)
    (generic_dir / "brand.toml").write_text(
        '[brand]\nslug = "generic"\nname = "Genérico"\n', encoding="utf-8"
    )
    monkeypatch.setenv("VIDEO_EDITORIAL_BRANDS_DIR", str(brands_dir))
    return brands_dir


def _fake_metadata(**overrides):
    defaults = dict(
        platform="youtube",
        source_id="7xgE4ZHNWRU",
        source_url="https://www.youtube.com/watch?v=7xgE4ZHNWRU",
        title="Podcast 3 Irmãos #1033",
        channel="Podcast 3 Irmãos",
        published_at=date(2026, 8, 12),
        duration_seconds=6300,
    )
    defaults.update(overrides)
    return VideoMetadata(**defaults)


def test_init_creates_project(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    _configure_brands_env(tmp_path, monkeypatch)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = runner.invoke(app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU"])

    assert result.exit_code == 0
    project_dir = tmp_path / "projetos" / "2026-08-12_podcast-3-irmaos-1033_7xgE4ZHNWRU"
    assert project_dir.is_dir()
    assert (project_dir / "project.json").is_file()
    assert (project_dir / "01 Fonte.md").is_file()
    assert "Projeto criado" in result.stdout
    assert "Brand: generic" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["brand"] == "generic"
    log_path = project_dir / "logs" / "pipeline.log"
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]
    assert len(entries) == 1
    assert entries[0]["etapa"] == "init"
    assert entries[0]["resultado"] == "ok"
    assert "duracao_segundos" in entries[0]


def test_init_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    _configure_brands_env(tmp_path, monkeypatch)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    runner.invoke(app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU"])
    second = runner.invoke(app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU"])

    assert second.exit_code == 0
    assert "Projeto já existente" in second.stdout


def test_init_reports_metadata_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    _configure_brands_env(tmp_path, monkeypatch)

    def _raise(url):
        raise MetadataError("mensagem acionável")

    monkeypatch.setattr(project_module, "fetch_metadata", _raise)

    result = runner.invoke(app, ["init", "https://www.youtube.com/watch?v=invalid"])

    assert result.exit_code == 1


def test_init_accepts_explicit_brand(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    brands_dir = _configure_brands_env(tmp_path, monkeypatch)
    (brands_dir / "bussola-politica").mkdir()
    (brands_dir / "bussola-politica" / "brand.toml").write_text(
        '[brand]\nslug = "bussola-politica"\nname = "Bússola Política"\n', encoding="utf-8"
    )
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = runner.invoke(
        app,
        ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU", "--brand", "bussola-politica"],
    )

    assert result.exit_code == 0
    assert "Brand: bussola-politica" in result.stdout
    project_dir = tmp_path / "projetos" / "2026-08-12_podcast-3-irmaos-1033_7xgE4ZHNWRU"
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["brand"] == "bussola-politica"


def test_init_reports_unknown_brand(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))
    _configure_brands_env(tmp_path, monkeypatch)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())

    result = runner.invoke(
        app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU", "--brand", "nao-existe"]
    )

    assert result.exit_code == 1


def _create_project(tmp_path, monkeypatch):
    projetos_dir = tmp_path / "projetos"
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(projetos_dir))
    _configure_brands_env(tmp_path, monkeypatch)
    monkeypatch.setattr(project_module, "fetch_metadata", lambda url: _fake_metadata())
    runner.invoke(app, ["init", "https://www.youtube.com/watch?v=7xgE4ZHNWRU"])
    return projetos_dir / "2026-08-12_podcast-3-irmaos-1033_7xgE4ZHNWRU"


def test_download_creates_file_and_updates_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_download(pdir, url, settings, force=False):
        final = pdir / "original" / "video-original.mp4"
        final.write_bytes(b"fake video bytes")
        return DownloadResult(path=final, skipped=False)

    monkeypatch.setattr(cli_main, "download_video", _fake_download)

    result = runner.invoke(app, ["download", str(project_dir)])

    assert result.exit_code == 0
    assert "Baixando vídeo..." in result.stdout
    assert "Download concluído" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "downloaded"
    log_path = project_dir / "logs" / "pipeline.log"
    all_entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]
    entries = [e for e in all_entries if e["etapa"] == "download"]
    assert [e["resultado"] for e in entries] == ["iniciado", "ok"]
    assert "duracao_segundos" in entries[1]


def test_download_reports_existing_file_without_changing_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_download(pdir, url, settings, force=False):
        final = pdir / "original" / "video-original.mp4"
        return DownloadResult(path=final, skipped=True)

    monkeypatch.setattr(cli_main, "download_video", _fake_download)

    result = runner.invoke(app, ["download", str(project_dir)])

    assert result.exit_code == 0
    assert "Arquivo original já existe." in result.stdout
    assert "Nenhum download realizado." in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "created"


def test_download_reports_download_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _raise(pdir, url, settings, force=False):
        raise DownloadError("mensagem acionável")

    monkeypatch.setattr(cli_main, "download_video", _raise)

    result = runner.invoke(app, ["download", str(project_dir)])

    assert result.exit_code == 1


def test_download_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["download", "nao-existe"])

    assert result.exit_code == 1


def test_audio_creates_file_and_updates_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_extract(pdir, force=False):
        final = pdir / "audio" / "audio.wav"
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(b"fake wav bytes")
        return AudioResult(path=final, skipped=False)

    monkeypatch.setattr(cli_main, "extract_audio", _fake_extract)

    result = runner.invoke(app, ["audio", str(project_dir)])

    assert result.exit_code == 0
    assert "Extraindo áudio..." in result.stdout
    assert "Áudio extraído" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "audio_ready"
    log_path = project_dir / "logs" / "pipeline.log"
    all_entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]
    entries = [e for e in all_entries if e["etapa"] == "audio"]
    assert [e["resultado"] for e in entries] == ["iniciado", "ok"]


def test_audio_reports_existing_file_without_changing_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_extract(pdir, force=False):
        final = pdir / "audio" / "audio.wav"
        return AudioResult(path=final, skipped=True)

    monkeypatch.setattr(cli_main, "extract_audio", _fake_extract)

    result = runner.invoke(app, ["audio", str(project_dir)])

    assert result.exit_code == 0
    assert "Arquivo de áudio já existe." in result.stdout
    assert "Nenhuma extração realizada." in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "created"


def test_audio_reports_extraction_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _raise(pdir, force=False):
        raise AudioError("mensagem acionável")

    monkeypatch.setattr(cli_main, "extract_audio", _raise)

    result = runner.invoke(app, ["audio", str(project_dir)])

    assert result.exit_code == 1


def test_audio_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["audio", "nao-existe"])

    assert result.exit_code == 1


def test_transcribe_creates_files_and_updates_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_transcribe(pdir, settings, force=False, on_segment=None):
        if on_segment is not None:
            on_segment(TranscriptSegment(index=0, start_seconds=0.0, end_seconds=4.2, text="Ola"))
        md_path = pdir / "02 Transcricao.md"
        json_path = pdir / "transcricao.json"
        md_path.write_text("# Transcrição", encoding="utf-8")
        json_path.write_text("{}", encoding="utf-8")
        return TranscribeResult(md_path=md_path, json_path=json_path, skipped=False)

    monkeypatch.setattr(cli_main, "transcribe_project", _fake_transcribe)

    result = runner.invoke(app, ["transcribe", str(project_dir)])

    assert result.exit_code == 0
    assert "Transcrevendo áudio" in result.stdout
    assert "[00:00:00 → 00:00:04] transcrito" in result.stdout
    assert "Transcrição concluída" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "transcribed"
    log_path = project_dir / "logs" / "pipeline.log"
    all_entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]
    entries = [e for e in all_entries if e["etapa"] == "transcribe"]
    assert [e["resultado"] for e in entries] == ["iniciado", "ok"]


def test_transcribe_reports_existing_file_without_changing_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _fake_transcribe(pdir, settings, force=False, on_segment=None):
        return TranscribeResult(
            md_path=pdir / "02 Transcricao.md", json_path=pdir / "transcricao.json", skipped=True
        )

    monkeypatch.setattr(cli_main, "transcribe_project", _fake_transcribe)

    result = runner.invoke(app, ["transcribe", str(project_dir)])

    assert result.exit_code == 0
    assert "Transcrição já existe." in result.stdout
    assert "Nenhuma transcrição realizada." in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "created"


def test_transcribe_reports_transcription_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _raise(pdir, settings, force=False):
        raise TranscriptionError("mensagem acionável")

    monkeypatch.setattr(cli_main, "transcribe_project", _raise)

    result = runner.invoke(app, ["transcribe", str(project_dir)])

    assert result.exit_code == 1


def test_transcribe_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["transcribe", "nao-existe"])

    assert result.exit_code == 1


def _fake_plan(project_dir, **overrides):
    defaults = dict(
        project_dir=project_dir,
        provider="claude",
        model="claude-sonnet-5",
        source_path=project_dir / "01 Fonte.md",
        transcript_path=project_dir / "02 Transcricao.md",
        transcript_char_count=1234,
        csv_path=project_dir / "03 Analise.csv",
        already_exists=False,
        long_transcript_warning=None,
    )
    defaults.update(overrides)
    return AnalysisPlan(**defaults)


def test_analyze_dry_run_prints_plan_without_calling_service(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    plan = _fake_plan(project_dir)
    monkeypatch.setattr(cli_main, "plan_analysis", lambda pdir, settings, provider=None, model=None: plan)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("analyze_project não deveria ser chamado em --dry-run")

    monkeypatch.setattr(cli_main, "analyze_project", _fail_if_called)

    result = runner.invoke(app, ["analyze", str(project_dir), "--dry-run"])

    assert result.exit_code == 0
    assert "DRY RUN" in result.stdout
    assert "Nenhuma chamada de API realizada." in result.stdout
    assert "1.234" in result.stdout


def test_analyze_reports_existing_analysis_without_force(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    plan = _fake_plan(project_dir, already_exists=True)
    monkeypatch.setattr(cli_main, "plan_analysis", lambda pdir, settings, provider=None, model=None: plan)

    result = runner.invoke(app, ["analyze", str(project_dir), "--yes"])

    assert result.exit_code == 0
    assert "A análise já existe" in result.stdout


def test_analyze_confirmation_prompt_cancels_without_yes(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    plan = _fake_plan(project_dir)
    monkeypatch.setattr(cli_main, "plan_analysis", lambda pdir, settings, provider=None, model=None: plan)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("analyze_project não deveria ser chamado se o usuário cancelar")

    monkeypatch.setattr(cli_main, "analyze_project", _fail_if_called)

    result = runner.invoke(app, ["analyze", str(project_dir)], input="n\n")

    assert result.exit_code == 0
    assert "Cancelado" in result.stdout


def test_analyze_yes_skips_confirmation_and_calls_service(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    plan = _fake_plan(project_dir)
    monkeypatch.setattr(cli_main, "plan_analysis", lambda pdir, settings, provider=None, model=None: plan)

    analyze_result = AnalyzeResult(plan=plan, skipped=False, dry_run_report=None, usage=None)
    monkeypatch.setattr(
        cli_main,
        "analyze_project",
        lambda pdir, settings, provider=None, model=None, force=False: analyze_result,
    )

    result = runner.invoke(app, ["analyze", str(project_dir), "--yes"])

    assert result.exit_code == 0
    assert "Chamando a API da Claude" in result.stdout
    assert "Análise concluída" in result.stdout


def test_analyze_force_is_forwarded_to_service(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    plan = _fake_plan(project_dir, already_exists=True)
    monkeypatch.setattr(cli_main, "plan_analysis", lambda pdir, settings, provider=None, model=None: plan)

    analyze_result = AnalyzeResult(plan=plan, skipped=False, dry_run_report=None, usage=None)
    captured = {}

    def _fake_analyze(pdir, settings, provider=None, model=None, force=False):
        captured["force"] = force
        return analyze_result

    monkeypatch.setattr(cli_main, "analyze_project", _fake_analyze)

    result = runner.invoke(app, ["analyze", str(project_dir), "--yes", "--force"])

    assert result.exit_code == 0
    assert captured["force"] is True


def test_analyze_reports_service_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    plan = _fake_plan(project_dir)
    monkeypatch.setattr(cli_main, "plan_analysis", lambda pdir, settings, provider=None, model=None: plan)

    def _raise(pdir, settings, provider=None, model=None, force=False):
        raise AnalysisServiceError("mensagem acionável")

    monkeypatch.setattr(cli_main, "analyze_project", _raise)

    result = runner.invoke(app, ["analyze", str(project_dir), "--yes"])

    assert result.exit_code == 1


def test_analyze_reports_plan_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _raise(pdir, settings, provider=None, model=None):
        raise AnalysisServiceError("02 Transcricao.md não encontrado")

    monkeypatch.setattr(cli_main, "plan_analysis", _raise)

    result = runner.invoke(app, ["analyze", str(project_dir), "--dry-run"])

    assert result.exit_code == 1


def test_analyze_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["analyze", "nao-existe", "--dry-run"])

    assert result.exit_code == 1


def test_cut_dry_run_prints_report_and_advances_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    row = AnalysisRow(ordem_publicacao="1", capitulo="08", acao_editorial="Manter")
    chapter = ChapterReport(row=row, status="ok", start_seconds=1747.0, end_seconds=2242.0)
    report = DryRunReport(
        project_dir=project_dir,
        video_path=project_dir / "original" / "video-original.mp4",
        video_duration_seconds=6303.0,
        csv_path=project_dir / "03 Analise.csv",
        chapters=[chapter],
        warnings=[],
    )
    monkeypatch.setattr(cli_main, "build_dry_run_report", lambda pdir: report)

    result = runner.invoke(app, ["cut", str(project_dir), "--dry-run"])

    assert result.exit_code == 0
    assert "Cortes elegíveis:" in result.stdout
    assert "[OK] Capítulo 08" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "analyzed"


def _report_with_chapters(project_dir, chapters):
    return DryRunReport(
        project_dir=project_dir,
        video_path=project_dir / "original" / "video-original.mp4",
        video_duration_seconds=6303.0,
        csv_path=project_dir / "03 Analise.csv",
        chapters=chapters,
        warnings=[],
    )


def test_cut_generates_real_cuts_and_advances_status(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    row = AnalysisRow(ordem_publicacao="1", capitulo="08", acao_editorial="Manter", titulo_sugerido="Titulo")
    chapter = ChapterReport(row=row, status="ok", start_seconds=1747.0, end_seconds=2242.0)
    report = _report_with_chapters(project_dir, [chapter])
    monkeypatch.setattr(cli_main, "build_dry_run_report", lambda pdir: report)

    output_path = project_dir / "cortes" / "001_cap08_titulo.mp4"

    def _fake_generate_cuts(rep, pdir, settings, mode="precise", on_progress=None):
        if on_progress is not None:
            on_progress(rep.chapters[0])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake")
        outcome = CutOutcome(chapter=rep.chapters[0], status="cut", output_path=output_path)
        return CutRunResult(outcomes=[outcome])

    monkeypatch.setattr(cli_main, "generate_cuts", _fake_generate_cuts)

    result = runner.invoke(app, ["cut", str(project_dir)])

    assert result.exit_code == 0
    assert "Cortando: Capítulo 08..." in result.stdout
    assert "Cortes gerados:" in result.stdout
    assert "[CORTADO] Capítulo 08" in result.stdout
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "cut"
    log_path = project_dir / "logs" / "pipeline.log"
    all_entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").strip().splitlines()]
    entries = [e for e in all_entries if e["etapa"] == "cut"]
    assert [e["resultado"] for e in entries] == ["iniciado", "ok"]
    assert entries[1]["cortes_gerados"] == 1
    assert "duracao_segundos" in entries[1]


def test_cut_does_not_advance_status_when_nothing_cut(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    row = AnalysisRow(ordem_publicacao="1", capitulo="08", acao_editorial="Unir")
    chapter = ChapterReport(row=row, status="manual_action", message="requer edição manual")
    report = _report_with_chapters(project_dir, [chapter])
    monkeypatch.setattr(cli_main, "build_dry_run_report", lambda pdir: report)

    def _fake_generate_cuts(rep, pdir, settings, mode="precise", on_progress=None):
        outcome = CutOutcome(chapter=rep.chapters[0], status="skipped_ineligible")
        return CutRunResult(outcomes=[outcome])

    monkeypatch.setattr(cli_main, "generate_cuts", _fake_generate_cuts)

    result = runner.invoke(app, ["cut", str(project_dir)])

    assert result.exit_code == 0
    data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["status"] == "created"


def test_cut_fast_mode_prints_keyframe_warning(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    row = AnalysisRow(ordem_publicacao="1", capitulo="08", acao_editorial="Manter")
    chapter = ChapterReport(row=row, status="ok", start_seconds=0.0, end_seconds=10.0)
    report = _report_with_chapters(project_dir, [chapter])
    monkeypatch.setattr(cli_main, "build_dry_run_report", lambda pdir: report)
    monkeypatch.setattr(
        cli_main,
        "generate_cuts",
        lambda rep, pdir, settings, mode="precise", on_progress=None: CutRunResult(outcomes=[]),
    )

    result = runner.invoke(app, ["cut", str(project_dir), "--mode", "fast"])

    assert result.exit_code == 0
    assert "Modo rápido utiliza keyframes" in result.stdout


def test_cut_reports_cutter_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    row = AnalysisRow(ordem_publicacao="1", capitulo="08", acao_editorial="Manter")
    chapter = ChapterReport(row=row, status="ok", start_seconds=0.0, end_seconds=10.0)
    report = _report_with_chapters(project_dir, [chapter])
    monkeypatch.setattr(cli_main, "build_dry_run_report", lambda pdir: report)

    def _raise(rep, pdir, settings, mode="precise"):
        raise CutterError("mensagem acionável")

    monkeypatch.setattr(cli_main, "generate_cuts", _raise)

    result = runner.invoke(app, ["cut", str(project_dir)])

    assert result.exit_code == 1


def test_cut_applies_chapter_filter(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    row_a = AnalysisRow(ordem_publicacao="1", capitulo="08", acao_editorial="Manter")
    row_b = AnalysisRow(ordem_publicacao="2", capitulo="14", acao_editorial="Manter")
    chapter_a = ChapterReport(row=row_a, status="ok", start_seconds=0.0, end_seconds=10.0)
    chapter_b = ChapterReport(row=row_b, status="ok", start_seconds=20.0, end_seconds=30.0)
    report = _report_with_chapters(project_dir, [chapter_a, chapter_b])
    monkeypatch.setattr(cli_main, "build_dry_run_report", lambda pdir: report)

    captured = {}

    def _fake_generate_cuts(rep, pdir, settings, mode="precise", on_progress=None):
        captured["chapters"] = rep.chapters
        return CutRunResult(outcomes=[])

    monkeypatch.setattr(cli_main, "generate_cuts", _fake_generate_cuts)

    runner.invoke(app, ["cut", str(project_dir), "--chapter", "14"])

    assert len(captured["chapters"]) == 1
    assert captured["chapters"][0].row.capitulo == "14"


def test_cut_dry_run_reports_analysis_errors(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    def _raise(pdir):
        raise AnalysisError("mensagem acionável")

    monkeypatch.setattr(cli_main, "build_dry_run_report", _raise)

    result = runner.invoke(app, ["cut", str(project_dir), "--dry-run"])

    assert result.exit_code == 1


def test_cut_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["cut", "nao-existe", "--dry-run"])

    assert result.exit_code == 1


def test_status_shows_project_info_and_missing_artifacts(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)

    result = runner.invoke(app, ["status", str(project_dir)])

    assert result.exit_code == 0
    assert "Status: created" in result.stdout
    assert "Brand: generic" in result.stdout
    assert "Podcast 3 Irmãos" in result.stdout
    assert "- Vídeo original: ausente" in result.stdout
    assert "- Cortes: 0 arquivo(s) em cortes/" in result.stdout


def test_status_shows_present_artifacts(tmp_path, monkeypatch):
    project_dir = _create_project(tmp_path, monkeypatch)
    (project_dir / "original" / "video-original.mp4").write_bytes(b"fake")
    (project_dir / "audio" / "audio.wav").write_bytes(b"fake")
    (project_dir / "cortes" / "001_cap01_titulo.mp4").write_bytes(b"fake")

    result = runner.invoke(app, ["status", str(project_dir)])

    assert result.exit_code == 0
    assert "- Vídeo original: presente" in result.stdout
    assert "- Áudio: presente" in result.stdout
    assert "- Cortes: 1 arquivo(s) em cortes/" in result.stdout


def test_status_shows_per_chapter_cut_presence(tmp_path, monkeypatch):
    from app.analysis import write_analysis_csv

    project_dir = _create_project(tmp_path, monkeypatch)
    write_analysis_csv(
        project_dir / "03 Analise.csv",
        [
            AnalysisRow(
                ordem_publicacao="1",
                capitulo="1",
                acao_editorial="Manter",
                timestamp_inicial="00:00:01",
                timestamp_final="00:00:02",
                titulo_sugerido="Capitulo Um",
            ),
            AnalysisRow(
                ordem_publicacao="2",
                capitulo="2",
                acao_editorial="Manter",
                timestamp_inicial="00:00:03",
                timestamp_final="00:00:04",
                titulo_sugerido="Capitulo Dois",
            ),
        ],
    )
    (project_dir / "cortes" / "001_cap01_capitulo-um.mp4").write_bytes(b"fake")

    result = runner.invoke(app, ["status", str(project_dir)])

    assert result.exit_code == 0
    assert "Capítulo 1: cut ✓" in result.stdout
    assert "Capítulo 2: cut ✗" in result.stdout


def test_status_reports_project_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_EDITORIAL_PROJETOS_DIR", str(tmp_path / "projetos"))

    result = runner.invoke(app, ["status", "nao-existe"])

    assert result.exit_code == 1
