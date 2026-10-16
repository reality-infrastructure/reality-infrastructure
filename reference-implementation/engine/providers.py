"""Provider layer.

One neutral message model; each provider translates.  Model swap is a manifest
edit (``model.provider`` / ``model.name``), never a code change.  Prices come
from config/prices.yaml.

Providers:
- ``anthropic``      official SDK, Messages API with tools.
- ``openai_compat``  any /v1/chat/completions endpoint (DeepSeek, vLLM, ...), stdlib HTTP.
- ``local``          deterministic fixture responders declared by a fixture pack.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Protocol

from engine.config import EngineConfig
from engine.errors import ProviderError

COST_PLACES = Decimal("0.00000001")


# ---------------------------------------------------------------------------
# Neutral message model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolUse:
    id: str
    name: str          # provider-safe tool name
    input: dict


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class Completion:
    text: str
    tool_uses: tuple[ToolUse, ...]
    stop_reason: str            # end_turn | tool_use | max_tokens | refusal | other
    usage: Usage
    model: str
    latency_ms: int = 0
    raw: dict | None = None


def text_message(role: str, text: str) -> dict:
    return {"role": role, "content": [{"type": "text", "text": text}]}


def assistant_message(completion: Completion) -> dict:
    content: list[dict] = []
    if completion.text:
        content.append({"type": "text", "text": completion.text})
    for tu in completion.tool_uses:
        content.append({"type": "tool_use", "id": tu.id, "name": tu.name, "input": tu.input})
    return {"role": "assistant", "content": content}


def tool_result_message(results: list[tuple[str, Any, bool]]) -> dict:
    """All tool results for one assistant turn go back in ONE user message."""
    return {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid,
         "content": json.dumps(result, sort_keys=True, default=str), "is_error": is_err}
        for tid, result, is_err in results]}


class Provider(Protocol):
    id: str

    def complete(self, *, model: str, system: str, messages: list[dict],
                 tools: list[dict], max_tokens: int, candidate_index: int = 0) -> Completion: ...

    def price(self, model: str, in_tokens: int, out_tokens: int) -> Decimal: ...


class _Priced:
    id: str

    def __init__(self, config: EngineConfig) -> None:
        self._config = config

    def price(self, model: str, in_tokens: int, out_tokens: int) -> Decimal:
        pin, pout = self._config.price_per_token(self.id, model)
        return (Decimal(in_tokens) * pin + Decimal(out_tokens) * pout).quantize(COST_PLACES)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicProvider(_Priced):
    id = "anthropic"

    def __init__(self, config: EngineConfig) -> None:
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ProviderError("anthropic SDK not installed") from e
            self._client = anthropic.Anthropic()
        return self._client

    def complete(self, *, model, system, messages, tools, max_tokens, candidate_index: int = 0) -> Completion:
        import anthropic
        client = self._get_client()
        request: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            # strict tool use needs a closed object schema; only promise it where the schema allows.
            request["tools"] = [
                dict(t, strict=True) if (t["input_schema"].get("additionalProperties") is False
                                         and "required" in t["input_schema"]) else t
                for t in tools]
        t0 = time.perf_counter()
        try:
            resp = client.messages.create(**request)
        except anthropic.RateLimitError as e:
            raise ProviderError(f"anthropic rate limited: {e}") from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"anthropic API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise ProviderError(f"anthropic connection error: {e}") from e
        latency = int((time.perf_counter() - t0) * 1000)
        text_parts, tool_uses = [], []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(ToolUse(id=block.id, name=block.name, input=dict(block.input)))
        return Completion(
            text="".join(text_parts), tool_uses=tuple(tool_uses),
            stop_reason=str(resp.stop_reason),
            usage=Usage(resp.usage.input_tokens, resp.usage.output_tokens),
            model=resp.model, latency_ms=latency,
            raw=resp.model_dump(mode="json"),
        )


# ---------------------------------------------------------------------------
# OpenAI-compatible (stdlib HTTP)
# ---------------------------------------------------------------------------

class OpenAICompatProvider(_Priced):
    id = "openai_compat"

    def __init__(self, config: EngineConfig, *, base_url: str | None = None,
                 api_key: str | None = None, timeout_s: float = 600.0) -> None:
        super().__init__(config)
        self._base_url = (base_url or os.environ.get("OPENAI_COMPAT_BASE_URL", "")).rstrip("/")
        self._api_key = api_key or os.environ.get("OPENAI_COMPAT_API_KEY", "")
        self._timeout = timeout_s

    @staticmethod
    def _to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
        out = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "assistant":
                text = "".join(b["text"] for b in m["content"] if b["type"] == "text")
                calls = [{"id": b["id"], "type": "function",
                          "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                         for b in m["content"] if b["type"] == "tool_use"]
                msg: dict = {"role": "assistant", "content": text or None}
                if calls:
                    msg["tool_calls"] = calls
                out.append(msg)
            else:
                for b in m["content"]:
                    if b["type"] == "text":
                        out.append({"role": "user", "content": b["text"]})
                    elif b["type"] == "tool_result":
                        out.append({"role": "tool", "tool_call_id": b["tool_use_id"],
                                    "content": b["content"]})
        return out

    def complete(self, *, model, system, messages, tools, max_tokens, candidate_index: int = 0) -> Completion:
        if not self._base_url:
            raise ProviderError("OPENAI_COMPAT_BASE_URL is not set")
        body: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": self._to_openai_messages(system, messages),
        }
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
                for t in tools]
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self._api_key}"} if self._api_key else {})},
            method="POST")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ProviderError(f"openai_compat HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise ProviderError(f"openai_compat request failed: {e}") from e
        latency = int((time.perf_counter() - t0) * 1000)
        try:
            choice = data["choices"][0]
            msg = choice["message"]
            usage = data.get("usage") or {}
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"openai_compat malformed response: {e}") from e
        tool_uses = []
        for call in msg.get("tool_calls") or []:
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError as e:
                raise ProviderError(f"openai_compat tool arguments not JSON: {e}") from e
            tool_uses.append(ToolUse(id=call["id"], name=call["function"]["name"], input=args))
        finish = choice.get("finish_reason")
        stop = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens",
                "content_filter": "refusal"}.get(finish, finish or "other")
        return Completion(
            text=msg.get("content") or "", tool_uses=tuple(tool_uses), stop_reason=stop,
            usage=Usage(int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))),
            model=data.get("model", model), latency_ms=latency, raw=data,
        )


# ---------------------------------------------------------------------------
# Local fixture responders
# ---------------------------------------------------------------------------

Responder = Callable[..., Completion]


class LocalProvider(_Priced):
    """Fixture models.  A pack with ``fixture: true`` declares ``local_models``
    mapping model name -> ``module:callable``; the callable is a Responder
    ``(model, system, messages, tools, candidate_index) -> Completion``.
    """

    id = "local"

    def __init__(self, config: EngineConfig, responders: dict[str, Responder]) -> None:
        super().__init__(config)
        self._responders = dict(responders)

    def complete(self, *, model, system, messages, tools, max_tokens, candidate_index: int = 0) -> Completion:
        fn = self._responders.get(model)
        if fn is None:
            raise ProviderError(f"local model {model!r} is not declared in the pack's local_models")
        t0 = time.perf_counter()
        completion = fn(model=model, system=system, messages=messages, tools=tools,
                        candidate_index=candidate_index)
        if not isinstance(completion, Completion):
            raise ProviderError(f"local model {model!r} returned {type(completion).__name__}, not Completion")
        latency = int((time.perf_counter() - t0) * 1000)
        return Completion(text=completion.text, tool_uses=completion.tool_uses,
                          stop_reason=completion.stop_reason, usage=completion.usage,
                          model=model, latency_ms=latency, raw=completion.raw)


@dataclass
class ProviderRegistry:
    config: EngineConfig
    local_responders: dict[str, Responder] = field(default_factory=dict)
    _cache: dict[str, Any] = field(default_factory=dict)

    def get(self, provider_id: str):
        if provider_id in self._cache:
            return self._cache[provider_id]
        if provider_id == "anthropic":
            p = AnthropicProvider(self.config)
        elif provider_id == "openai_compat":
            p = OpenAICompatProvider(self.config)
        elif provider_id == "local":
            p = LocalProvider(self.config, self.local_responders)
        else:
            raise ProviderError(f"unknown provider {provider_id!r}")
        self._cache[provider_id] = p
        return p


def parse_model_string(s: str) -> tuple[str, str]:
    """``provider/model`` -> (provider, model)."""
    if "/" not in s:
        raise ProviderError(f"model string {s!r} must be <provider>/<model>")
    provider, model = s.split("/", 1)
    if not provider or not model:
        raise ProviderError(f"model string {s!r} must be <provider>/<model>")
    return provider, model
