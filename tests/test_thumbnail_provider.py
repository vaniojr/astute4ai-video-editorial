import pytest

from app.thumbnail_provider import (
    ManualThumbnailProvider,
    ThumbnailProviderError,
    ThumbnailRequest,
    get_thumbnail_provider,
    is_supported_provider,
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
        get_thumbnail_provider("azure")
    assert "manual" in str(exc_info.value)
    assert "openai" in str(exc_info.value)


def test_get_thumbnail_provider_openai_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ThumbnailProviderError) as exc_info:
        get_thumbnail_provider("openai", model="gpt-image-1")
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_get_thumbnail_provider_openai_succeeds_with_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")

    from app.thumbnail_openai_provider import OpenAIThumbnailProvider

    provider = get_thumbnail_provider("openai", model="gpt-image-1")
    assert isinstance(provider, OpenAIThumbnailProvider)


def test_is_supported_provider():
    assert is_supported_provider("manual") is True
    assert is_supported_provider("openai") is True
    assert is_supported_provider("azure") is False
