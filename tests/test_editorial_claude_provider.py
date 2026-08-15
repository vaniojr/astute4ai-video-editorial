"""Testes de ClaudeEditorialProvider — cliente Anthropic sempre mockado."""

from dataclasses import dataclass
from typing import Any, List, Optional

import httpx
import pytest

import app.editorial_claude_provider as editorial_claude_provider_module
from app.editorial_claude_provider import ClaudeEditorialProvider
from app.editorial_provider import EditorialProviderError, EditorialRequest


@dataclass
class _FakeToolUseBlock:
    input: dict
    type: str = "tool_use"


@dataclass
class _FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class _FakeMessage:
    content: List[Any]
    usage: Optional[_FakeUsage] = None


class _FakeMessages:
    def __init__(self, response=None, raise_error=None):
        self._response = response
        self._raise_error = raise_error
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._raise_error is not None:
            raise self._raise_error
        return self._response


class _FakeClient:
    def __init__(self, messages: _FakeMessages):
        self.messages = messages


def _patch_client(monkeypatch, fake_client):
    monkeypatch.setattr(editorial_claude_provider_module.anthropic, "Anthropic", lambda **kwargs: fake_client)


def _valid_response(**overrides):
    base = dict(
        intro_text="Neste trecho...",
        context_cards=[{"kind": "context", "text": "CONTEXTO", "position_fraction": 0.1}],
        highlights=[{"quote": "uma citação qualquer"}],
    )
    base.update(overrides)
    return base


def _request():
    return EditorialRequest(
        tema_principal="Tema",
        titulo_sugerido="Titulo",
        resumo="Resumo",
        pergunta_principal="Pergunta",
        trecho_para_validar_primeiro="",
        observacoes="",
        transcript_excerpt="[00:00:00 → 00:00:04] trecho da transcricao",
        source_title="Fonte de teste",
        source_channel="Canal de teste",
        system_instructions="instrucoes de sistema",
        editorial_instructions="instrucoes editoriais",
    )


def _fake_auth_error():
    import anthropic

    response = httpx.Response(
        status_code=401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    return anthropic.AuthenticationError("invalid api key", response=response, body=None)


def test_provider_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(EditorialProviderError):
        ClaudeEditorialProvider(model="claude-sonnet-5", temperature=0)


def test_plan_maps_tool_use_response_to_candidate(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    tool_use = _FakeToolUseBlock(input=_valid_response())
    message = _FakeMessage(content=[tool_use], usage=_FakeUsage(input_tokens=100, output_tokens=50))
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(response=message)))

    provider = ClaudeEditorialProvider(model="claude-sonnet-5", temperature=0)
    result = provider.plan(_request())

    assert result.provider == "claude"
    assert result.model == "claude-sonnet-5"
    assert result.candidate.intro_text == "Neste trecho..."
    assert len(result.candidate.context_cards) == 1
    assert result.candidate.context_cards[0].kind == "context"
    assert result.candidate.context_cards[0].position_fraction == 0.1
    assert result.candidate.highlights[0].quote == "uma citação qualquer"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50


def test_plan_forwards_model_system_and_tool_choice(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    tool_use = _FakeToolUseBlock(input=_valid_response())
    message = _FakeMessage(content=[tool_use])
    messages = _FakeMessages(response=message)
    _patch_client(monkeypatch, _FakeClient(messages))

    provider = ClaudeEditorialProvider(model="claude-sonnet-5", temperature=0)
    provider.plan(_request())

    kwargs = messages.last_kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["system"] == "instrucoes de sistema"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "submeter_plano_editorial"}
    assert "temperature" not in kwargs
    assert "trecho da transcricao" in kwargs["messages"][0]["content"]


def test_plan_accepts_empty_intro_and_lists(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    tool_use = _FakeToolUseBlock(
        input=_valid_response(intro_text="", context_cards=[], highlights=[])
    )
    message = _FakeMessage(content=[tool_use])
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(response=message)))

    provider = ClaudeEditorialProvider(model="claude-sonnet-5", temperature=0)
    result = provider.plan(_request())

    assert result.candidate.intro_text == ""
    assert result.candidate.context_cards == []
    assert result.candidate.highlights == []


def test_plan_raises_when_no_tool_use_block(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    message = _FakeMessage(content=[])
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(response=message)))

    provider = ClaudeEditorialProvider(model="claude-sonnet-5", temperature=0)

    with pytest.raises(EditorialProviderError):
        provider.plan(_request())


def test_plan_raises_on_missing_required_field(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    bad_response = _valid_response()
    del bad_response["highlights"]
    tool_use = _FakeToolUseBlock(input=bad_response)
    message = _FakeMessage(content=[tool_use])
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(response=message)))

    provider = ClaudeEditorialProvider(model="claude-sonnet-5", temperature=0)

    with pytest.raises(EditorialProviderError):
        provider.plan(_request())


def test_plan_raises_on_malformed_card(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    bad_response = _valid_response(context_cards=[{"kind": "context", "text": "sem posicao"}])
    tool_use = _FakeToolUseBlock(input=bad_response)
    message = _FakeMessage(content=[tool_use])
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(response=message)))

    provider = ClaudeEditorialProvider(model="claude-sonnet-5", temperature=0)

    with pytest.raises(EditorialProviderError):
        provider.plan(_request())


def test_plan_wraps_authentication_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(raise_error=_fake_auth_error())))

    provider = ClaudeEditorialProvider(model="claude-sonnet-5", temperature=0)

    with pytest.raises(EditorialProviderError):
        provider.plan(_request())
