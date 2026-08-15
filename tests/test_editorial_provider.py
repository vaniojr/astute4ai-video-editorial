import pytest

from app.editorial_provider import EditorialProviderError, get_editorial_provider


def test_get_editorial_provider_raises_for_unknown_name():
    with pytest.raises(EditorialProviderError) as exc_info:
        get_editorial_provider("outro", model="x", temperature=0.0)
    assert "claude" in str(exc_info.value)


def test_get_editorial_provider_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(EditorialProviderError) as exc_info:
        get_editorial_provider("claude", model="claude-sonnet-5", temperature=0.0)
    assert "ANTHROPIC_API_KEY" in str(exc_info.value)


def test_get_editorial_provider_returns_claude_provider_with_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    provider = get_editorial_provider("claude", model="claude-sonnet-5", temperature=0.0)

    from app.editorial_claude_provider import ClaudeEditorialProvider

    assert isinstance(provider, ClaudeEditorialProvider)
