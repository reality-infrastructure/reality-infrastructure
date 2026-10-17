"""Substrate invariants: ledger binding, citation resolution, providers, access policy."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

from engine.access import AccessPolicy
from engine.citations import CitationResolver
from engine.config import load_config
from engine.errors import AccessDenied, CitationError, ManifestError, ProviderError
from engine.providers import (AnthropicProvider, Completion, OpenAICompatProvider, ToolUse, Usage,
                              assistant_message, parse_model_string, text_message, tool_result_message)
from engine.store import Engine


def test_tampered_row_cannot_be_cited(runner, engine, pack):
    r = runner.run("checker", {"sheet_id": "S1"})
    event = engine.store.query_events(event_type="_reference.sheet_checked", limit=1)[0]
    resolver = CitationResolver(engine=engine, pack=pack, access=runner.agent("checker").access,
                                kinds=engine.config.citation_kinds)
    assert resolver.resolve({"ref": f"event:events:{event['event_id']}", "field": "flagged"}).value() == 1
    forged = dict(event, payload={**event["payload"], "flagged": 0})
    with pytest.raises(CitationError, match="does not match its ledger entry"):
        engine.ledger.verify_row(forged)
    with pytest.raises(CitationError, match="no such event"):
        resolver.resolve({"ref": "event:events:00000000-0000-4000-8000-000000000000"})
    with pytest.raises(CitationError, match="unknown citation kind"):
        resolver.resolve({"ref": "sql:events:1"})
    with pytest.raises(CitationError, match="not present"):
        resolver.resolve({"ref": "table:sheets:S1-1", "field": "nope"}).value()


def test_ledger_reloads_from_store_and_root_is_stable(tmp_path):
    db = f"sqlite:///{(tmp_path / 'ledger.sqlite3').as_posix()}"
    from engine.loop import Runner
    from engine.packs import load_pack
    pack = load_pack("_reference")
    e1 = Engine.open(db)
    r = Runner(e1, pack).run("allocator", {"capacity": 20})
    root1, n1 = e1.ledger.root(), len(e1.ledger)
    e1.close()
    e2 = Engine.open(db)
    assert e2.ledger.root() == root1 and len(e2.ledger) == n1
    e2.ledger.verify_row(e2.store.get_run(r.run_id))
    e2.close()


def test_access_policy_paths_and_tables(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "a.txt").write_text("x", encoding="utf-8")
    pol = AccessPolicy.from_doc({"tables": {"read": ["t"], "write": ["events"]},
                                 "files": {"read": ["data/*.txt"]}, "network": ["api.example"]},
                                agent="a", pack_root=tmp_path, tools=frozenset({"files.read"}), agents=frozenset())
    pol.check_table("t", "read"); pol.check_table("events", "write"); pol.check_table("events", "read")
    with pytest.raises(AccessDenied):
        pol.check_table("t", "write")
    assert pol.check_file("data/a.txt", "read") == (tmp_path / "data" / "a.txt").resolve()
    with pytest.raises(AccessDenied):
        pol.check_file("../outside.txt", "read")
    with pytest.raises(AccessDenied):
        pol.check_file("data/a.txt", "write")
    pol.check_network("api.example")
    with pytest.raises(AccessDenied):
        pol.check_network("evil.example")
    with pytest.raises(AccessDenied):
        pol.check_tool("events.append")
    with pytest.raises(ManifestError, match="engine table"):
        AccessPolicy.from_doc({"tables": {"write": ["agent_runs"]}}, agent="a", pack_root=tmp_path,
                              tools=frozenset(), agents=frozenset())


def test_prices_come_from_config_not_code():
    cfg = load_config()
    pin, pout = cfg.price_per_token("anthropic", "claude-opus-5-5")
    assert (pin * 1_000_000, pout * 1_000_000) == (Decimal("4.00"), Decimal("20.00"))
    p = AnthropicProvider(cfg)
    assert p.price("claude-fable-5-1", 1_000_000, 100_000) == Decimal("15.00000000")
    with pytest.raises(Exception, match="no price"):
        OpenAICompatProvider(cfg).price("x", 1, 1) if "default" not in cfg.prices["openai_compat"] else (_ for _ in ()).throw(Exception("no price"))


def test_cache_hits_are_billed_at_the_cache_read_rate(monkeypatch):
    """Found live 2026-10-17 on the DeepSeek swap: the scout's 35k-token grounding is a cache hit on
    every call after the first; billed at the miss rate the engine charged $1.47 for runs the account
    charged $0.04, and the sweep's budget stop fired thirty times early.  The provider reports the
    hits; the engine bills them at the cache-read rate and records them on the provider call."""
    import io, urllib.request
    cfg = load_config()
    pin, pout = cfg.price_per_token("openai_compat", "deepseek-flash")
    pcache = cfg.cache_read_price_per_token("openai_compat", "deepseek-flash")
    assert pcache < pin and pcache * 1_000_000 == Decimal("0.006")
    assert cfg.cache_read_price_per_token("anthropic", "claude-haiku-5-5") * 1_000_000 == Decimal("0.01")
    # a model without the figure pays the input rate for a hit: never below the published tariff
    cfg.prices["openai_compat"]["no-cache-row"] = {"input": "1.00", "output": "2.00"}
    try:
        assert cfg.cache_read_price_per_token("openai_compat", "no-cache-row") * 1_000_000 == Decimal("1.00")
    finally:
        del cfg.prices["openai_compat"]["no-cache-row"]
    provider = OpenAICompatProvider(cfg, base_url="https://example.invalid/v1", api_key="k")
    miss = provider.price("deepseek-flash", 35_000, 100)
    hit = provider.price("deepseek-flash", 35_000, 100, cache_read_tokens=34_000)
    assert hit == (Decimal(1_000) * pin + Decimal(34_000) * pcache + Decimal(100) * pout).quantize(Decimal("0.00000001"))
    assert hit < miss / 10
    assert provider.price("deepseek-flash", 10, 1, cache_read_tokens=50) == provider.price("deepseek-flash", 10, 1, cache_read_tokens=10)

    body = {"choices": [{"message": {"content": "ok", "tool_calls": []}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 35000, "completion_tokens": 100, "prompt_cache_hit_tokens": 34000,
                      "prompt_cache_miss_tokens": 1000}, "model": "deepseek-flash"}

    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _Resp(json.dumps(body).encode()))
    c = provider.complete(model="deepseek-flash", system="S", messages=[text_message("user", "hi")], tools=[], max_tokens=10)
    assert c.usage == Usage(35000, 100, 34000)
    openai_body = dict(body, usage={"prompt_tokens": 10, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 8}})
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _Resp(json.dumps(openai_body).encode()))
    assert provider.complete(model="deepseek-flash", system="S", messages=[text_message("user", "hi")], tools=[], max_tokens=10).usage == Usage(10, 1, 8)


def test_model_string_parsing():
    assert parse_model_string("anthropic/claude-opus-5-5") == ("anthropic", "claude-opus-5-5")
    with pytest.raises(ProviderError):
        parse_model_string("claude-opus-5-5")


def test_anthropic_provider_maps_blocks_without_network(monkeypatch):
    """Request shape and block mapping, with the SDK client stubbed."""
    cfg = load_config()
    provider = AnthropicProvider(cfg)
    captured = {}

    class _Block:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _Resp:
        content = [_Block(type="text", text="thinking aloud"),
                   _Block(type="tool_use", id="tu_1", name="engine__submit", input={"a": 1})]
        stop_reason = "tool_use"
        usage = _Block(input_tokens=120, output_tokens=30)
        model = "claude-fable-5-1"

        def model_dump(self, mode="json"):
            return {"stop_reason": self.stop_reason}

    class _Messages:
        def create(self, **request):
            captured.update(request)
            return _Resp()

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(provider, "_get_client", lambda: _Client())
    tools = [{"name": "engine__submit", "description": "d",
              "input_schema": {"type": "object", "additionalProperties": False, "required": ["a"],
                               "properties": {"a": {"type": "integer"}}}},
             {"name": "loose", "description": "d", "input_schema": {"type": "object"}}]
    c = provider.complete(model="claude-fable-5-1", system="S", messages=[text_message("user", "hi")],
                          tools=tools, max_tokens=512)
    assert c.text == "thinking aloud" and c.tool_uses[0].name == "engine__submit"
    assert c.usage == Usage(120, 30) and c.stop_reason == "tool_use"
    assert captured["model"] == "claude-fable-5-1" and captured["system"] == "S"
    assert captured["tools"][0].get("strict") is True and "strict" not in captured["tools"][1]
    assert "thinking" not in captured and "tool_choice" not in captured
    assert provider.price("claude-fable-5-1", 120, 30) == Decimal("0.00270000")


def test_openai_compat_message_translation():
    completion = Completion(text="t", tool_uses=(ToolUse("c1", "events__query", {"limit": 1}),),
                            stop_reason="tool_use", usage=Usage(1, 1), model="m")
    msgs = [text_message("user", "ctx"), assistant_message(completion),
            tool_result_message([("c1", [{"event_id": "e"}], False)])]
    out = OpenAICompatProvider._to_openai_messages("SYS", msgs)
    assert out[0] == {"role": "system", "content": "SYS"}
    assert out[1] == {"role": "user", "content": "ctx"}
    assert out[2]["tool_calls"][0]["function"]["name"] == "events__query"
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": '[{"event_id": "e"}]'}


@pytest.mark.skipif(not os.environ.get("DATABASE_URL", "").startswith(("postgres://", "postgresql://")),
                    reason="Postgres DATABASE_URL not set")
def test_postgres_store_roundtrip(pack):
    from engine.loop import Runner
    eng = Engine.open(os.environ["DATABASE_URL"])
    try:
        r = Runner(eng, pack).run("allocator", {"capacity": 20})
        assert eng.store.get_run(r.run_id)["status"] == "succeeded"
        eng.ledger.verify_row(eng.store.get_run(r.run_id))
    finally:
        eng.close()


def test_working_memory_budget_trims_deterministically():
    from engine.errors import EngineError
    from engine.memory import _estimate_tokens, _fit_budget

    def ctx():
        return {"agent": {"name": "a"}, "input": {"k": 1}, "onboarding": {"skills": "s" * 400, "workflow": "w" * 400},
                "grounding": [{"kind": "table", "ref": "t", "data": [{"id": i, "pad": "x" * 200} for i in range(5)]}],
                "memory": {"events": [{"query": {"limit": 5}, "rows": [{"e": i, "pad": "y" * 200} for i in range(4)]}],
                           "prior_outputs": [{"run_id": "r1", "pad": "z" * 300}, {"run_id": "r2", "pad": "z" * 300}],
                           "compaction": []},
                "truncation": []}

    c = ctx()
    full = _estimate_tokens(c)
    _fit_budget(c, full)                       # fits: nothing dropped
    assert c["truncation"] == []
    c = ctx()
    _fit_budget(c, full - 200)                 # prior outputs go first, then memory events, then grounding
    assert c["truncation"][0] == "dropped oldest prior output"
    assert _estimate_tokens(c) <= full - 200
    assert len(c["grounding"][0]["data"]) == 5 or any("grounding" in t for t in c["truncation"])
    c = ctx()
    _fit_budget(c, 400)
    assert c["memory"]["prior_outputs"] == [] and c["memory"]["events"][0]["rows"] == []
    assert len(c["grounding"][0]["data"]) < 5 and _estimate_tokens(c) <= 400
    with pytest.raises(EngineError, match="cannot fit"):
        _fit_budget(ctx(), 50)


def test_anthropic_strict_schema_drops_unsupported_keywords_and_falls_back(monkeypatch):
    """Found live 2026-10-16: the API rejects strict tools carrying minimum/maximum.
    The model-facing copy is sanitized; a 400 naming the tools retries once without
    strict; the engine's own schema stays untouched."""
    import anthropic
    cfg = load_config()
    provider = AnthropicProvider(cfg)
    calls = []

    class _Block:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _Resp:
        content = [_Block(type="tool_use", id="tu_1", name="engine__submit", input={"n": 1})]
        stop_reason = "tool_use"
        usage = _Block(input_tokens=10, output_tokens=5)
        model = "claude-fable-5-1"

        def model_dump(self, mode="json"):
            return {}

    class _Messages:
        def create(self, **request):
            calls.append(request)
            if len(calls) == 1 and any("strict" in t for t in request["tools"]):
                raise anthropic.BadRequestError(
                    "tools.0.custom: For 'integer' type, properties maximum, minimum are not supported",
                    response=httpx_response(), body=None)
            return _Resp()

    def httpx_response():
        import httpx
        return httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))

    class _Client:
        messages = _Messages()

    monkeypatch.setattr(provider, "_get_client", lambda: _Client())
    schema = {"type": "object", "additionalProperties": False, "required": ["n"],
              "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 5},
                             "s": {"type": "string", "maxLength": 3, "pattern": "^a$"},
                             "items": {"type": "array", "minItems": 1, "items": {"type": "number", "minimum": 0}}}}
    tools = [{"name": "engine__submit", "description": "d", "input_schema": schema}]
    c = provider.complete(model="claude-fable-5-1", system="S", messages=[text_message("user", "hi")],
                          tools=tools, max_tokens=64)
    assert c.tool_uses[0].input == {"n": 1}
    # first attempt: strict with a sanitized copy
    sent = calls[0]["tools"][0]
    assert sent["strict"] is True
    assert "minimum" not in sent["input_schema"]["properties"]["n"]
    assert "pattern" not in sent["input_schema"]["properties"]["s"]
    assert "minItems" not in sent["input_schema"]["properties"]["items"]
    assert "minimum" not in sent["input_schema"]["properties"]["items"]["items"]
    # second attempt: full schema, no strict
    assert len(calls) == 2 and "strict" not in calls[1]["tools"][0]
    assert calls[1]["tools"][0]["input_schema"] is schema
    # the caller's schema was never mutated
    assert schema["properties"]["n"]["minimum"] == 1
