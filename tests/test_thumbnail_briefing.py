from datetime import date, datetime

from app.analysis import AnalysisRow
from app.brands import Brand, BrandAssets, BrandColors, BrandFeatures, BrandThumbnailConfig, BrandVideoConfig
from app.project import Project
from app.thumbnail_briefing import build_briefing, build_headline_options


def _row(**overrides):
    defaults = dict(
        ordem_publicacao="1",
        capitulo="8",
        acao_editorial="Manter",
        tema_principal="Governabilidade",
        titulo_sugerido="Não vou ser usado pelo Centrão",
        palavra_chave_principal="centrão",
        resumo="Resumo do trecho.",
        pergunta_principal="Como formar maioria?",
        trecho_para_validar_primeiro="",
        observacoes="",
    )
    defaults.update(overrides)
    return AnalysisRow(**defaults)


def _project(**overrides):
    defaults = dict(
        schema_version=2,
        platform="youtube",
        source_id="7xgE4ZHNWRU",
        source_url="https://www.youtube.com/watch?v=7xgE4ZHNWRU",
        title="Podcast 3 Irmãos #1033",
        channel="Podcast 3 Irmãos",
        published_at=date(2026, 8, 12),
        duration_seconds=6300,
        slug="podcast-3-irmaos-1033",
        created_at=datetime(2026, 8, 12, 10, 0, 0),
        status="cut",
        brand="bussola-politica",
    )
    defaults.update(overrides)
    return Project(**defaults)


def _brand(**overrides):
    defaults = dict(
        slug="bussola-politica",
        name="Bússola Política",
        colors=BrandColors(primary="#F5C400", background="#090909", text="#FFFFFF", accent="#C92020"),
        features=BrandFeatures(),
        assets=BrandAssets(),
        video=BrandVideoConfig(),
        thumbnail=BrandThumbnailConfig(),
    )
    defaults.update(overrides)
    return Brand(**defaults)


def test_build_briefing_includes_csv_fields():
    briefing = build_briefing(_row(), _project(), _brand())

    assert "Governabilidade" in briefing
    assert "Não vou ser usado pelo Centrão" in briefing
    assert "centrão" in briefing
    assert "Resumo do trecho." in briefing
    assert "Como formar maioria?" in briefing
    assert "Podcast 3 Irmãos #1033" in briefing
    assert "Bússola Política" in briefing


def test_build_briefing_never_invents_participants():
    briefing = build_briefing(_row(), _project(), _brand())

    assert "participants_unknown" in briefing
    assert "Não inventar participantes." in briefing


def test_build_briefing_omits_validation_note_when_not_flagged():
    briefing = build_briefing(_row(trecho_para_validar_primeiro="", observacoes=""), _project(), _brand())

    assert "sinalizado para validação" not in briefing


def test_build_briefing_adds_validation_note_when_trecho_flagged():
    briefing = build_briefing(
        _row(trecho_para_validar_primeiro="Verificar afirmação sobre X."), _project(), _brand()
    )

    assert "sinalizado para validação" in briefing


def test_build_briefing_adds_validation_note_when_observacoes_flagged():
    briefing = build_briefing(_row(observacoes="Conteúdo sensível."), _project(), _brand())

    assert "sinalizado para validação" in briefing


def test_build_headline_options_returns_distinct_csv_fields_in_order():
    options = build_headline_options(_row())

    assert options == [
        "Não vou ser usado pelo Centrão",
        "Como formar maioria?",
        "Governabilidade",
    ]


def test_build_headline_options_deduplicates_repeated_values():
    options = build_headline_options(
        _row(titulo_sugerido="Mesmo texto", pergunta_principal="Mesmo texto", tema_principal="Tema único")
    )

    assert options == ["Mesmo texto", "Tema único"]


def test_build_headline_options_skips_empty_fields():
    options = build_headline_options(
        _row(titulo_sugerido="", pergunta_principal="", tema_principal="Único tema disponível")
    )

    assert options == ["Único tema disponível"]


def test_build_headline_options_returns_empty_list_when_no_fields_filled():
    options = build_headline_options(_row(titulo_sugerido="", pergunta_principal="", tema_principal=""))

    assert options == []


def test_build_headline_options_caps_at_three():
    options = build_headline_options(
        _row(titulo_sugerido="Um", pergunta_principal="Dois", tema_principal="Três")
    )

    assert len(options) == 3
