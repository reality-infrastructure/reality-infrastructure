"""Harness engine — domain-agnostic agent runtime built on Reality Infrastructure.

Every agent run is judged inside RI: guardrail and verifier results are signed
observations on an RI evidence log, fused under the cautious rule, and the
resulting belief (including retained conflict mass) is persisted on the trace
and replayable byte-for-byte via ``python -m engine.replay``.

The engine carries mechanism only.  Domain nouns live in packs.
"""

__version__ = "0.1.0"
