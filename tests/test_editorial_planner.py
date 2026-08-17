import json
from datetime import date, datetime
from pathlib import Path

from app.brands import Brand, BrandAssets, BrandColors, BrandFeatures, BrandThumbnailConfig, BrandVideoConfig
from app.editorial_planner import (
    build_editorial_plan,
    extract_transcript_excerpt,
    find_highlight_timing,
    format_transcript_excerpt,
)
from app.editorial_provider import EditorialCandidate, RawContextCard, RawHighlight
from app.project import Project
from app.transcriber import TranscriptSegment


def _write_transcricao_json(tmp_path, segments):
    path = tmp_path / "transcricao.json"
    path.write_text(
        json.dumps(
            {
                "language": "pt",
                "segments": [
                    {"index": i, "start": s, "end": e, "text": t} for i, (s, e, t) in enumerate(segments)
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_extract_transcript_excerpt_filters_and_converts_to_relative(tmp_path):
    path = _write_transcricao_json(
        tmp_path,
        [
            (0.0, 5.0, "antes do corte"),
            (1747.0, 1752.0, "primeiro segmento do corte"),
            (1752.0, 1760.0, "segundo segmento do corte"),
            (5000.0, 5010.0, "bem depois"),
        ],
    )

    segments = extract_transcript_excerpt(path, start_seconds=1747.0, end_seconds=1760.0)

    assert len(segments) == 2
    assert segments[0].text == "primeiro segmento do corte"
    assert segments[0].start_seconds == 0.0
    assert segments[0].end_seconds == 5.0
    assert segments[1].start_seconds == 5.0
    assert segments[1].end_seconds == 13.0


def test_format_transcript_excerpt_includes_timestamps_and_text():
    segments = [TranscriptSegment(index=0, start_seconds=0.0, end_seconds=4.0, text="Olá mundo")]
    formatted = format_transcript_excerpt(segments)
    assert "[00:00:00 → 00:00:04] Olá mundo" == formatted


def test_find_highlight_timing_matches_single_segment():
    segments = [
        TranscriptSegment(index=0, start_seconds=0.0, end_seconds=5.0, text="O Centrão deve ser usado"),
        TranscriptSegment(index=1, start_seconds=5.0, end_seconds=10.0, text="não usar o governo"),
    ]

    timing = find_highlight_timing("O Centrão deve ser usado", segments)

    assert timing == (0.0, 5.0)


def test_find_highlight_timing_matches_across_adjacent_segments():
    segments = [
        TranscriptSegment(index=0, start_seconds=0.0, end_seconds=5.0, text="O Centrão deve ser usado,"),
        TranscriptSegment(index=1, start_seconds=5.0, end_seconds=10.0, text="não usar o governo."),
    ]

    timing = find_highlight_timing("usado, não usar o governo", segments)

    assert timing == (0.0, 10.0)


def test_find_highlight_timing_returns_none_when_not_found():
    segments = [TranscriptSegment(index=0, start_seconds=0.0, end_seconds=5.0, text="texto real")]

    assert find_highlight_timing("citação inventada que não existe", segments) is None


def test_find_highlight_timing_returns_none_for_empty_quote():
    segments = [TranscriptSegment(index=0, start_seconds=0.0, end_seconds=5.0, text="texto real")]

    assert find_highlight_timing("   ", segments) is None


def _brand(**overrides):
    defaults = dict(
        slug="bussola-politica",
        name="Bússola Política",
        colors=BrandColors(),
        features=BrandFeatures(cta_enabled=True),
        assets=BrandAssets(),
        video=BrandVideoConfig(cta_text="BÚSSOLA POLÍTICA"),
        thumbnail=BrandThumbnailConfig(),
    )
    defaults.update(overrides)
    return Brand(**defaults)


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


def test_build_editorial_plan_converts_fraction_to_seconds():
    candidate = EditorialCandidate(
        intro_text="Intro de teste",
        context_cards=[RawContextCard(kind="context", text="CONTEXTO", position_fraction=0.5)],
        highlights=[],
    )

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=_brand(),
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert plan.context_cards[0].timestamp == 50.0
    assert plan.intro.mode == "text_only"
    assert plan.intro.text == "Intro de teste"


def test_build_editorial_plan_caps_context_cards_at_four():
    candidate = EditorialCandidate(
        intro_text="",
        context_cards=[
            RawContextCard(kind="context", text=f"CARD {i}", position_fraction=i / 10) for i in range(7)
        ],
        highlights=[],
    )

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=_brand(),
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert len(plan.context_cards) == 4
    assert [c.text for c in plan.context_cards] == ["CARD 0", "CARD 1", "CARD 2", "CARD 3"]


def test_build_editorial_plan_clamps_out_of_range_fraction():
    candidate = EditorialCandidate(
        intro_text="",
        context_cards=[
            RawContextCard(kind="context", text="A", position_fraction=-0.5),
            RawContextCard(kind="context", text="B", position_fraction=1.5),
        ],
        highlights=[],
    )

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=_brand(),
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert plan.context_cards[0].timestamp == 0.0
    assert plan.context_cards[1].timestamp == 100.0


def test_build_editorial_plan_empty_intro_is_disabled():
    candidate = EditorialCandidate(intro_text="", context_cards=[], highlights=[])

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=_brand(),
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert plan.intro.mode == "disabled"
    assert plan.intro.text is None


def test_build_editorial_plan_discards_highlight_not_found_in_transcript():
    candidate = EditorialCandidate(
        intro_text="",
        context_cards=[],
        highlights=[RawHighlight(quote="citação real"), RawHighlight(quote="citação inventada")],
    )
    segments = [TranscriptSegment(index=0, start_seconds=0.0, end_seconds=5.0, text="citação real aqui")]

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=_brand(),
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=segments,
    )

    assert len(plan.highlights) == 1
    assert plan.highlights[0].text == "citação real"
    assert plan.highlights[0].start == 0.0
    assert plan.highlights[0].end == 5.0


def test_build_editorial_plan_source_attribution_includes_channel():
    candidate = EditorialCandidate(intro_text="", context_cards=[], highlights=[])

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=_brand(),
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert "Podcast 3 Irmãos #1033" in plan.source_attribution.text
    assert "Podcast 3 Irmãos" in plan.source_attribution.text


def test_build_editorial_plan_cta_from_brand_not_ai():
    candidate = EditorialCandidate(intro_text="", context_cards=[], highlights=[])

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=_brand(),
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert plan.cta.enabled is True
    assert plan.cta.text == "BÚSSOLA POLÍTICA"


def test_build_editorial_plan_cta_from_brand_image():
    candidate = EditorialCandidate(intro_text="", context_cards=[], highlights=[])
    brand = _brand(video=BrandVideoConfig(cta_image=Path("/brands/bussola/assets/cta.png")))

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=brand,
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert plan.cta.enabled is True
    assert plan.cta.text is None
    assert plan.cta.image == "/brands/bussola/assets/cta.png"
    assert plan.cta.video is None


def test_build_editorial_plan_cta_from_brand_video():
    candidate = EditorialCandidate(intro_text="", context_cards=[], highlights=[])
    brand = _brand(video=BrandVideoConfig(cta_video=Path("/brands/bussola/assets/cta.mp4")))

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=brand,
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert plan.cta.enabled is True
    assert plan.cta.text is None
    assert plan.cta.video == "/brands/bussola/assets/cta.mp4"
    assert plan.cta.image is None


def test_build_editorial_plan_cta_disabled_when_brand_feature_disabled():
    candidate = EditorialCandidate(intro_text="", context_cards=[], highlights=[])
    brand = _brand(features=BrandFeatures(cta_enabled=False), video=BrandVideoConfig(cta_text=None))

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=brand,
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert plan.cta.enabled is False
    assert plan.cta.text is None


def test_build_editorial_plan_lower_thirds_always_empty():
    candidate = EditorialCandidate(intro_text="", context_cards=[], highlights=[])

    plan = build_editorial_plan(
        candidate,
        chapter="8",
        cut_file="008_cap08_teste.mp4",
        brand=_brand(),
        project=_project(),
        version=1,
        provider="claude",
        model="claude-sonnet-5",
        cut_duration_seconds=100.0,
        transcript_segments=[],
    )

    assert plan.lower_thirds == []
