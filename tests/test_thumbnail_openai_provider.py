"""Testes de OpenAIThumbnailProvider — cliente OpenAI sempre mockado."""

from dataclasses import dataclass
from typing import List, Optional

import httpx2
import pytest

import app.thumbnail_openai_provider as openai_provider_module
from app.brands import Brand, BrandAssets, BrandColors, BrandFeatures, BrandThumbnailConfig, BrandVideoConfig
from app.thumbnail_openai_provider import OpenAIThumbnailProvider
from app.thumbnail_provider import ThumbnailProviderError, ThumbnailRequest


@dataclass
class _FakeImageData:
    b64_json: Optional[str] = None


@dataclass
class _FakeImagesResponse:
    data: List[_FakeImageData]


class _FakeImages:
    def __init__(self, response=None, raise_error=None):
        self._response = response
        self._raise_error = raise_error
        self.last_kwargs = None

    def edit(self, **kwargs):
        self.last_kwargs = kwargs
        if self._raise_error is not None:
            raise self._raise_error
        return self._response


class _FakeClient:
    def __init__(self, images: _FakeImages):
        self.images = images


def _patch_client(monkeypatch, fake_client):
    monkeypatch.setattr(openai_provider_module.openai, "OpenAI", lambda **kwargs: fake_client)


def _brand(**overrides):
    defaults = dict(
        slug="bussola-politica",
        name="Bússola Política",
        colors=BrandColors(primary="#F5C400", background="#090909", text="#FFFFFF", accent="#C92020"),
        features=BrandFeatures(),
        assets=BrandAssets(),
        video=BrandVideoConfig(),
        thumbnail=BrandThumbnailConfig(width=1280, height=720, style="political-editorial"),
    )
    defaults.update(overrides)
    return Brand(**defaults)


def _request(tmp_path, **overrides):
    frame = tmp_path / "frame-01.jpg"
    frame.write_bytes(b"fake jpeg bytes")
    defaults = dict(
        reference_images=[frame],
        briefing="# Thumbnail Briefing\n\nTexto principal sugerido: Teste",
        aspect_ratio="16:9",
        brand=_brand(),
    )
    defaults.update(overrides)
    return ThumbnailRequest(**defaults)


def _fake_auth_error():
    response = httpx2.Response(
        status_code=401, request=httpx2.Request("POST", "https://api.openai.com/v1/images/edits")
    )
    import openai

    return openai.AuthenticationError("invalid api key", response=response, body=None)


def test_provider_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ThumbnailProviderError) as exc_info:
        OpenAIThumbnailProvider(model="gpt-image-1")
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_generate_raises_when_no_reference_images(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = OpenAIThumbnailProvider(model="gpt-image-1")

    request = _request(tmp_path, reference_images=[])

    with pytest.raises(ThumbnailProviderError):
        provider.generate(request)


def test_generate_returns_decoded_image_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    import base64

    encoded = base64.b64encode(b"fake png bytes").decode("ascii")
    response = _FakeImagesResponse(data=[_FakeImageData(b64_json=encoded)])
    _patch_client(monkeypatch, _FakeClient(_FakeImages(response=response)))

    provider = OpenAIThumbnailProvider(model="gpt-image-1")
    result = provider.generate(_request(tmp_path))

    assert result.provider == "openai"
    assert len(result.images) == 1
    assert result.images[0].content == b"fake png bytes"
    assert result.images[0].content_type == "image/png"


def test_generate_forwards_model_and_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    import base64

    encoded = base64.b64encode(b"x").decode("ascii")
    response = _FakeImagesResponse(data=[_FakeImageData(b64_json=encoded)])
    images = _FakeImages(response=response)
    _patch_client(monkeypatch, _FakeClient(images))

    provider = OpenAIThumbnailProvider(model="gpt-image-1")
    provider.generate(_request(tmp_path))

    kwargs = images.last_kwargs
    assert kwargs["model"] == "gpt-image-1"
    assert "Texto principal sugerido: Teste" in kwargs["prompt"]
    assert "Bússola Política" in kwargs["prompt"]
    assert kwargs["n"] == 1
    assert len(kwargs["image"]) == 1


def test_generate_resolves_landscape_size_from_brand(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    import base64

    encoded = base64.b64encode(b"x").decode("ascii")
    response = _FakeImagesResponse(data=[_FakeImageData(b64_json=encoded)])
    images = _FakeImages(response=response)
    _patch_client(monkeypatch, _FakeClient(images))

    provider = OpenAIThumbnailProvider(model="gpt-image-1")
    provider.generate(_request(tmp_path, brand=_brand(thumbnail=BrandThumbnailConfig(width=1280, height=720))))

    assert images.last_kwargs["size"] == "1536x1024"


def test_generate_resolves_square_size_from_brand(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    import base64

    encoded = base64.b64encode(b"x").decode("ascii")
    response = _FakeImagesResponse(data=[_FakeImageData(b64_json=encoded)])
    images = _FakeImages(response=response)
    _patch_client(monkeypatch, _FakeClient(images))

    provider = OpenAIThumbnailProvider(model="gpt-image-1")
    provider.generate(_request(tmp_path, brand=_brand(thumbnail=BrandThumbnailConfig(width=1024, height=1024))))

    assert images.last_kwargs["size"] == "1024x1024"


def test_generate_raises_when_response_has_no_data(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    _patch_client(monkeypatch, _FakeClient(_FakeImages(response=_FakeImagesResponse(data=[]))))

    provider = OpenAIThumbnailProvider(model="gpt-image-1")

    with pytest.raises(ThumbnailProviderError):
        provider.generate(_request(tmp_path))


def test_generate_raises_when_no_b64_json_in_response(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    response = _FakeImagesResponse(data=[_FakeImageData(b64_json=None)])
    _patch_client(monkeypatch, _FakeClient(_FakeImages(response=response)))

    provider = OpenAIThumbnailProvider(model="gpt-image-1")

    with pytest.raises(ThumbnailProviderError):
        provider.generate(_request(tmp_path))


def test_generate_wraps_authentication_error(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    _patch_client(monkeypatch, _FakeClient(_FakeImages(raise_error=_fake_auth_error())))

    provider = OpenAIThumbnailProvider(model="gpt-image-1")

    with pytest.raises(ThumbnailProviderError):
        provider.generate(_request(tmp_path))
