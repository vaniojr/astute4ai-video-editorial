from app.analysis import AnalysisRow, write_analysis_csv
from app.chapter_status import get_chapter_statuses
from app.config import Settings


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
    )


def _make_project(tmp_path):
    project_dir = tmp_path / "projeto"
    (project_dir / "cortes").mkdir(parents=True)
    return project_dir


def test_get_chapter_statuses_empty_when_csv_missing(tmp_path):
    project_dir = _make_project(tmp_path)
    settings = _settings(tmp_path)

    assert get_chapter_statuses(project_dir, settings) == []


def test_get_chapter_statuses_reflects_cut_presence(tmp_path):
    project_dir = _make_project(tmp_path)
    settings = _settings(tmp_path)
    write_analysis_csv(
        project_dir / "03 Analise.csv",
        [
            AnalysisRow(
                ordem_publicacao="1",
                capitulo="1",
                acao_editorial="Manter",
                titulo_sugerido="Capitulo Um",
            ),
            AnalysisRow(
                ordem_publicacao="2",
                capitulo="2",
                acao_editorial="Manter",
                titulo_sugerido="Capitulo Dois",
            ),
        ],
    )
    (project_dir / "cortes" / "001_cap01_capitulo-um.mp4").write_bytes(b"fake")

    statuses = get_chapter_statuses(project_dir, settings)

    assert len(statuses) == 2
    by_capitulo = {s.capitulo: s for s in statuses}
    assert by_capitulo["1"].cut is True
    assert by_capitulo["1"].cut_path == project_dir / "cortes" / "001_cap01_capitulo-um.mp4"
    assert by_capitulo["2"].cut is False
    assert by_capitulo["2"].cut_path is None


def test_get_chapter_statuses_skips_non_keep_rows(tmp_path):
    project_dir = _make_project(tmp_path)
    settings = _settings(tmp_path)
    write_analysis_csv(
        project_dir / "03 Analise.csv",
        [
            AnalysisRow(
                ordem_publicacao="1",
                capitulo="1",
                acao_editorial="Descartar",
                titulo_sugerido="Descartado",
            ),
        ],
    )

    assert get_chapter_statuses(project_dir, settings) == []
