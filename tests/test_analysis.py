import csv
from dataclasses import dataclass

import pytest

from app import analysis as analysis_module
from app import ffmpeg_utils as ffmpeg_utils_module
from app.analysis import (
    AnalysisError,
    AnalysisRow,
    ChapterReport,
    build_dry_run_report,
    classify_action,
    filter_chapters,
    load_analysis,
    select_single_chapter,
    write_analysis_csv,
)

_HEADERS = [
    "Ordem Publicacao",
    "Prioridade",
    "Capitulo",
    "Bloco Editorial",
    "Acao Editorial",
    "Timestamp Inicial",
    "Timestamp Final",
    "Duracao",
    "Tema Principal",
    "Titulo Sugerido",
    "Palavra-chave Principal",
    "Trecho para Validar Primeiro",
    "Resumo",
    "Pergunta Principal",
    "Independente",
    "Precisa Contexto Anterior",
    "Grau de Confianca",
    "Observacoes",
]


def _write_csv(path, rows, headers=_HEADERS, encoding="utf-8-sig"):
    with path.open("w", encoding=encoding, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _row(**overrides):
    base = {h: "" for h in _HEADERS}
    base.update(overrides)
    return base


def test_load_analysis_reads_utf8(tmp_path):
    csv_path = tmp_path / "03 Analise.csv"
    _write_csv(
        csv_path,
        [_row(**{"Ordem Publicacao": "1", "Capitulo": "08", "Acao Editorial": "Manter"})],
        encoding="utf-8",
    )

    rows = load_analysis(csv_path)

    assert len(rows) == 1
    assert rows[0].capitulo == "08"
    assert rows[0].acao_editorial == "Manter"


def test_load_analysis_reads_utf8_sig(tmp_path):
    csv_path = tmp_path / "03 Analise.csv"
    _write_csv(
        csv_path,
        [_row(**{"Ordem Publicacao": "1", "Capitulo": "08", "Acao Editorial": "Manter"})],
        encoding="utf-8-sig",
    )

    rows = load_analysis(csv_path)

    assert len(rows) == 1
    assert rows[0].capitulo == "08"


def test_load_analysis_raises_on_missing_required_columns(tmp_path):
    csv_path = tmp_path / "03 Analise.csv"
    headers = [h for h in _HEADERS if h not in ("Timestamp Inicial", "Timestamp Final")]
    _write_csv(csv_path, [{h: "" for h in headers}], headers=headers)

    with pytest.raises(AnalysisError) as exc_info:
        load_analysis(csv_path)
    assert "Timestamp Inicial" in str(exc_info.value)
    assert "Timestamp Final" in str(exc_info.value)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Manter", "keep"),
        ("manter", "keep"),
        ("Descartar", "discard"),
        ("Não publicar", "discard"),
        ("Arquivar", "discard"),
        ("Unir", "manual"),
        ("Separar", "manual"),
        ("Transformar em teaser", "manual"),
        ("Revisar", "manual"),
        ("Alguma coisa aleatória", "unknown"),
    ],
)
def test_classify_action(raw, expected):
    assert classify_action(raw) == expected


def _fake_ffprobe(monkeypatch, duration_seconds):
    @dataclass
    class _FakeCompletedProcess:
        returncode: int
        stdout: str = ""
        stderr: str = ""

    def _fake_run(cmd, capture_output=True, text=True):
        return _FakeCompletedProcess(returncode=0, stdout=str(duration_seconds))

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: f"/usr/bin/{name}")


def _make_project(tmp_path, csv_rows=None, headers=_HEADERS):
    project_dir = tmp_path / "projeto"
    original_dir = project_dir / "original"
    original_dir.mkdir(parents=True)
    (original_dir / "video-original.mp4").write_bytes(b"fake video bytes")
    if csv_rows is not None:
        _write_csv(project_dir / "03 Analise.csv", csv_rows, headers=headers)
    return project_dir


def test_build_dry_run_report_raises_when_video_missing(tmp_path):
    project_dir = tmp_path / "projeto"
    project_dir.mkdir()

    with pytest.raises(AnalysisError):
        build_dry_run_report(project_dir)


def test_build_dry_run_report_raises_when_csv_missing(tmp_path, monkeypatch):
    project_dir = _make_project(tmp_path, csv_rows=None)
    _fake_ffprobe(monkeypatch, 6303)

    with pytest.raises(AnalysisError):
        build_dry_run_report(project_dir)


def test_build_dry_run_report_raises_when_ffprobe_missing(tmp_path, monkeypatch):
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "00:00:01",
                    "Timestamp Final": "00:00:02",
                }
            ),
        ],
    )
    monkeypatch.setattr(ffmpeg_utils_module.shutil, "which", lambda name: None)

    def _fail_if_called(cmd, capture_output=True, text=True):
        raise AssertionError("ffprobe não deveria ser chamado")

    monkeypatch.setattr(ffmpeg_utils_module.subprocess, "run", _fail_if_called)

    with pytest.raises(AnalysisError) as exc_info:
        build_dry_run_report(project_dir)
    assert "FFmpeg" in str(exc_info.value)


def test_build_dry_run_report_marks_ok_row(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 6303)
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "00:29:07",
                    "Timestamp Final": "00:37:22",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert report.eligible_count == 1
    assert report.chapters[0].status == "ok"
    assert report.chapters[0].start_seconds == 29 * 60 + 7
    assert report.chapters[0].end_seconds - report.chapters[0].start_seconds == 8 * 60 + 15


def test_build_dry_run_report_auto_resolves_spreadsheet_mangled_timestamp(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 6303)  # 01:45:03 -- 29h seria incompatível
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "29:07:00",
                    "Timestamp Final": "00:37:22",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert report.chapters[0].status == "ok"
    assert report.chapters[0].start_seconds == 29 * 60 + 7
    assert report.chapters[0].message is not None


def test_build_dry_run_report_marks_ambiguous_row(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 1000)  # nem a leitura H:MM:SS nem a MM:SS de "29:07:00" cabem
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "29:07:00",
                    "Timestamp Final": "00:00:05",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert report.eligible_count == 0
    assert report.chapters[0].status == "ambiguous"


def test_build_dry_run_report_marks_manual_action_row(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 6303)
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Unir",
                    "Timestamp Inicial": "00:29:07",
                    "Timestamp Final": "00:37:22",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert report.eligible_count == 0
    assert report.chapters[0].status == "manual_action"


def test_build_dry_run_report_marks_unknown_action_as_error(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 6303)
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Talvez",
                    "Timestamp Inicial": "00:29:07",
                    "Timestamp Final": "00:37:22",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert report.chapters[0].status == "error"


def test_build_dry_run_report_excludes_discarded_from_eligible(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 6303)
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Descartar",
                    "Timestamp Inicial": "00:29:07",
                    "Timestamp Final": "00:37:22",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert report.eligible_count == 0
    assert report.chapters[0].status == "discarded"


def test_build_dry_run_report_flags_duracao_mismatch(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 6303)
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "00:29:07",
                    "Timestamp Final": "00:37:22",
                    "Duracao": "00:01:00",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert report.chapters[0].status == "error"
    assert "não confere" in report.chapters[0].message


def test_build_dry_run_report_flags_duplicate_chapters(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 6303)
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "00:00:00",
                    "Timestamp Final": "00:01:00",
                }
            ),
            _row(
                **{
                    "Ordem Publicacao": "2",
                    "Capitulo": "08",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "00:10:00",
                    "Timestamp Final": "00:11:00",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert any("duplicado" in w for w in report.warnings)


def test_build_dry_run_report_flags_overlapping_ranges(tmp_path, monkeypatch):
    _fake_ffprobe(monkeypatch, 6303)
    project_dir = _make_project(
        tmp_path,
        csv_rows=[
            _row(
                **{
                    "Ordem Publicacao": "1",
                    "Capitulo": "08",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "00:00:00",
                    "Timestamp Final": "00:05:00",
                }
            ),
            _row(
                **{
                    "Ordem Publicacao": "2",
                    "Capitulo": "09",
                    "Acao Editorial": "Manter",
                    "Timestamp Inicial": "00:03:00",
                    "Timestamp Final": "00:08:00",
                }
            ),
        ],
    )

    report = build_dry_run_report(project_dir)

    assert any("Sobreposição" in w for w in report.warnings)


def _chapter(**overrides):
    defaults = dict(ordem_publicacao="1", capitulo="1", prioridade="A")
    defaults.update(overrides)
    row = AnalysisRow(**defaults)
    return ChapterReport(row=row, status="ok", start_seconds=0.0, end_seconds=10.0)


def test_filter_chapters_without_filters_returns_all():
    chapters = [_chapter(capitulo="1"), _chapter(capitulo="2")]
    assert filter_chapters(chapters) == chapters


def test_filter_chapters_by_priority_is_case_insensitive():
    chapters = [_chapter(prioridade="A"), _chapter(prioridade="b")]
    result = filter_chapters(chapters, priority="a")
    assert len(result) == 1
    assert result[0].row.prioridade == "A"


def test_filter_chapters_by_chapter_number():
    chapters = [_chapter(capitulo="8"), _chapter(capitulo="14")]
    result = filter_chapters(chapters, chapter=14)
    assert len(result) == 1
    assert result[0].row.capitulo == "14"


def test_filter_chapters_by_order():
    chapters = [_chapter(ordem_publicacao="1"), _chapter(ordem_publicacao="2")]
    result = filter_chapters(chapters, order=2)
    assert len(result) == 1
    assert result[0].row.ordem_publicacao == "2"


def test_filter_chapters_combines_filters_with_and():
    chapters = [
        _chapter(capitulo="8", prioridade="A"),
        _chapter(capitulo="8", prioridade="B"),
        _chapter(capitulo="14", prioridade="A"),
    ]
    result = filter_chapters(chapters, chapter=8, priority="A")
    assert len(result) == 1
    assert result[0].row.capitulo == "8"
    assert result[0].row.prioridade == "A"


def test_filter_chapters_by_chapter_ignores_non_numeric_capitulo():
    chapters = [_chapter(capitulo="abc")]
    assert filter_chapters(chapters, chapter=8) == []


def test_select_single_chapter_returns_the_one_match():
    chapters = [_chapter(capitulo="8"), _chapter(capitulo="14")]
    result = select_single_chapter(chapters, chapter=8)
    assert result.row.capitulo == "8"


def test_select_single_chapter_raises_when_no_match():
    chapters = [_chapter(capitulo="8")]
    with pytest.raises(AnalysisError):
        select_single_chapter(chapters, chapter=99)


def test_select_single_chapter_raises_when_multiple_matches():
    chapters = [_chapter(capitulo="8", prioridade="A"), _chapter(capitulo="8", prioridade="B")]
    with pytest.raises(AnalysisError):
        select_single_chapter(chapters, chapter=8)


def test_write_analysis_csv_round_trips_through_load_analysis(tmp_path):
    csv_path = tmp_path / "03 Analise.csv"
    rows = [
        AnalysisRow(
            ordem_publicacao="1",
            prioridade="A",
            capitulo="8",
            acao_editorial="Manter",
            timestamp_inicial="00:29:07",
            timestamp_final="00:37:22",
            duracao="00:08:15",
            tema_principal='Tema com "aspas", vírgula e acentuação: é, ção',
            titulo_sugerido="Título, com vírgula",
            resumo="Linha 1\nLinha 2",
            observacoes="",
        ),
    ]

    write_analysis_csv(csv_path, rows)
    loaded = load_analysis(csv_path)

    assert len(loaded) == 1
    assert loaded[0].tema_principal == 'Tema com "aspas", vírgula e acentuação: é, ção'
    assert loaded[0].titulo_sugerido == "Título, com vírgula"
    assert loaded[0].resumo == "Linha 1\nLinha 2"
    assert loaded[0].timestamp_inicial == "00:29:07"


def test_write_analysis_csv_uses_exact_header_order(tmp_path):
    csv_path = tmp_path / "03 Analise.csv"
    write_analysis_csv(csv_path, [AnalysisRow(ordem_publicacao="1", capitulo="1", acao_editorial="Manter")])

    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        header = next(csv.reader(fh))

    assert header == _HEADERS
