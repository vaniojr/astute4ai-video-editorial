"""Testes de ClaudeAnalysisProvider — cliente Anthropic sempre mockado."""

from dataclasses import dataclass, field
from typing import Any, List, Optional

import httpx
import pytest

import app.claude_provider as claude_provider_module
from app.analyzer import AnalysisRequest, AnalysisServiceError
from app.claude_provider import ClaudeAnalysisProvider


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
    monkeypatch.setattr(claude_provider_module.anthropic, "Anthropic", lambda **kwargs: fake_client)


def _valid_chapter(**overrides):
    base = dict(
        capitulo=1,
        prioridade="A",
        bloco_editorial="Bloco 1",
        acao_editorial="Manter",
        timestamp_inicial="00:00:05",
        timestamp_final="00:00:15",
        tema_principal="Tema",
        titulo_sugerido="Titulo",
        palavra_chave_principal="palavra",
        trecho_para_validar_primeiro="",
        resumo="Resumo",
        pergunta_principal="",
        independente="Sim",
        precisa_contexto_anterior="Nao",
        grau_de_confianca="Alto",
        observacoes="",
    )
    base.update(overrides)
    return base


def _request():
    return AnalysisRequest(
        source_content="fonte",
        transcript_content="transcricao completa aqui",
        system_instructions="instrucoes de sistema",
        editorial_instructions="instrucoes editoriais",
        metadata={"titulo": "Video de teste"},
    )


def _fake_auth_error():
    import anthropic

    response = httpx.Response(
        status_code=401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    return anthropic.AuthenticationError("invalid api key", response=response, body=None)


def test_provider_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(AnalysisServiceError):
        ClaudeAnalysisProvider(model="claude-sonnet-5", temperature=0)


def test_analyze_maps_tool_use_response_to_chapters(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    tool_use = _FakeToolUseBlock(input={"capitulos": [_valid_chapter()]})
    message = _FakeMessage(content=[tool_use], usage=_FakeUsage(input_tokens=100, output_tokens=50))
    fake_client = _FakeClient(_FakeMessages(response=message))
    _patch_client(monkeypatch, fake_client)

    provider = ClaudeAnalysisProvider(model="claude-sonnet-5", temperature=0)
    result = provider.analyze(_request())

    assert result.provider == "claude"
    assert result.model == "claude-sonnet-5"
    assert len(result.chapters) == 1
    assert result.chapters[0].titulo_sugerido == "Titulo"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50


def test_analyze_forwards_model_system_and_tool_choice(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    tool_use = _FakeToolUseBlock(input={"capitulos": [_valid_chapter()]})
    message = _FakeMessage(content=[tool_use])
    messages = _FakeMessages(response=message)
    _patch_client(monkeypatch, _FakeClient(messages))

    provider = ClaudeAnalysisProvider(model="claude-sonnet-5", temperature=0)
    provider.analyze(_request())

    kwargs = messages.last_kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["system"] == "instrucoes de sistema"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "submeter_analise_editorial"}
    assert "transcricao completa aqui" in kwargs["messages"][0]["content"]


def test_analyze_raises_when_no_tool_use_block(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    message = _FakeMessage(content=[])
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(response=message)))

    provider = ClaudeAnalysisProvider(model="claude-sonnet-5", temperature=0)

    with pytest.raises(AnalysisServiceError):
        provider.analyze(_request())


def test_analyze_raises_on_missing_required_field(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    bad_chapter = _valid_chapter()
    del bad_chapter["resumo"]
    tool_use = _FakeToolUseBlock(input={"capitulos": [bad_chapter]})
    message = _FakeMessage(content=[tool_use])
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(response=message)))

    provider = ClaudeAnalysisProvider(model="claude-sonnet-5", temperature=0)

    with pytest.raises(AnalysisServiceError):
        provider.analyze(_request())


def test_analyze_wraps_authentication_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    _patch_client(monkeypatch, _FakeClient(_FakeMessages(raise_error=_fake_auth_error())))

    provider = ClaudeAnalysisProvider(model="claude-sonnet-5", temperature=0)

    with pytest.raises(AnalysisServiceError):
        provider.analyze(_request())
