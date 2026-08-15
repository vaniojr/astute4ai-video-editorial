import pytest

from app.thumbnail_provider import (
    ManualThumbnailProvider,
    ThumbnailProviderError,
    ThumbnailRequest,
    get_thumbnail_provider,
)


def test_manual_provider_never_generates_images():
    provider = ManualThumbnailProvider()
    request = ThumbnailRequest(reference_images=[], briefing="briefing de teste")

    result = provider.generate(request)

    assert result.images == []
    assert result.provider == "manual"


def test_get_thumbnail_provider_returns_manual():
    provider = get_thumbnail_provider("manual")
    assert isinstance(provider, ManualThumbnailProvider)


def test_get_thumbnail_provider_raises_for_unknown_name():
    with pytest.raises(ThumbnailProviderError) as exc_info:
        get_thumbnail_provider("openai")
    assert "manual" in str(exc_info.value)
