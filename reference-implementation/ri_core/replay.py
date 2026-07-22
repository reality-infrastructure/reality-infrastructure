"""Replay and counterfactual engine over serialized evidence logs.

Provides:
- export_log(): extract canonical entry bytes from an EvidenceLog
- replay(): reconstruct a byte-identical BeliefState from exported entries
- counterfactual(): replay over a modified log (evidence delta / rule
  substitution)

This is the top layer of the ri_core stack: it imports everything.

Trust model (v0.1 limitation, documented):
    Replay takes the LocalAuthority as input — the same trust root used by
    projection.  HMAC requires the anchor's key store for sig verification;
    a replayer without the original authority cannot re-verify.  The Merkle
    root check covers log integrity independently of signatures.

    Shared-provenance (link state) lives in the authority, not in the log.
    Replay with a different link-state yields a different justification
    structure (same belief, per idempotence of cautious fusion).  Link
    events as logged evidence are flagged for SPEC v0.2.
"""

from __future__ import annotations

from ri_core.log import EvidenceLog
from ri_core.identity import LocalAuthority
from ri_core.project import ProjectionError, project, submit
from ri_core.provenance import ProvenanceGraph
from ri_core.rules import RuleError, RuleStore
from ri_core.serialization import SerializationError
from ri_core.serialization import decode as _decode
from ri_core.serialization import encode as _encode


class ReplayError(Exception):
    """Error in replay or counterfactual operations."""


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_log(log: EvidenceLog) -> dict:
    """Export log entries for replay.

    Returns a dict with kind ``"log_export"`` and entries as canonical
    bytes (the exact bytes stored by ``log.append()``).  Pure function;
    does not mutate *log*.
    """
    entries = [log.entry(i) for i in range(len(log))]
    return {"kind": "log_export", "entries": entries}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _decode_entry(entry_bytes: bytes, index: int) -> dict:
    """Decode a single entry, converting errors to ReplayError."""
    try:
        decoded = _decode(entry_bytes)
    except (SerializationError, Exception) as exc:
        raise ReplayError(
            f"malformed_entry at index {index}: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ReplayError(
            f"malformed_entry at index {index}: expected dict, "
            f"got {type(decoded).__name__}")
    return decoded


def _verify_root(entries: list[bytes], expected_root: bytes) -> None:
    """Rebuild a fresh log from entry bytes and check the Merkle root.

    Raises ReplayError("root_mismatch") on failure, or
    ReplayError("malformed_entry") if any entry cannot be decoded.
    """
    check_log = EvidenceLog()
    for i, entry_bytes in enumerate(entries):
        decoded = _decode_entry(entry_bytes, i)
        check_log.append(decoded)
    rebuilt_root = check_log.root(len(check_log))
    if rebuilt_root != expected_root:
        raise ReplayError("root_mismatch")


def _validate_export(export: dict) -> list[bytes]:
    """Validate export structure.  Returns the entries list."""
    if not isinstance(export, dict):
        raise ReplayError("export must be a dict")
    if export.get("kind") != "log_export":
        raise ReplayError("export kind must be 'log_export'")
    entries = export.get("entries")
    if not isinstance(entries, list):
        raise ReplayError("export entries must be a list")
    for i, e in enumerate(entries):
        if not isinstance(e, bytes):
            raise ReplayError(
                f"export entry at index {i} must be bytes")
    return entries


def _replay_entries(
    entries: list[bytes],
    authority: LocalAuthority,
    rule_bindings: dict[str, tuple[str, int]],
    as_of: int,
) -> dict:
    """Core replay: process entries in order, then project.

    Returns BeliefState dict.
    """
    replay_log = EvidenceLog()
    graph = ProvenanceGraph()
    rule_store = RuleStore()

    for i, entry_bytes in enumerate(entries):
        decoded = _decode_entry(entry_bytes, i)
        kind = decoded.get("kind")

        if kind == "observation":
            try:
                submit(decoded, replay_log, graph, authority)
            except ProjectionError as exc:
                raise ReplayError(
                    f"replay submit failed at index {i}: {exc}") from exc

        elif kind == "rule_version":
            try:
                rule_store.register(
                    decoded["rule_id"],
                    decoded["version"],
                    decoded["fn_spec"],
                    decoded["ltime"],
                )
            except (RuleError, KeyError) as exc:
                raise ReplayError(
                    f"rule registration failed at index {i}: "
                    f"{exc}") from exc
            replay_log.append(decoded)

        else:
            raise ReplayError(
                f"unknown_entry_kind at index {i}: {kind!r}")

    try:
        bs = project(
            replay_log, graph, authority,
            rule_store, rule_bindings, as_of)
    except ProjectionError as exc:
        raise ReplayError(f"projection failed: {exc}") from exc

    return bs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def replay(
    export: dict,
    authority: LocalAuthority,
    rule_bindings: dict[str, tuple[str, int]],
    as_of: int,
    expected_root: bytes,
) -> dict:
    """Replay a log export, producing a byte-identical BeliefState.

    Integrity: rebuilds Merkle root from entries, asserts equality with
    *expected_root* before any replay state is constructed.

    Trust: re-verifies every observation signature via *authority*
    (same trust root as projection — the LocalAuthority model's limit).

    Args:
        export: dict from export_log() — ``{kind, entries}``.
        authority: the trust root for sig verification.
        rule_bindings: proposition -> (rule_id, version).
        as_of: logical-time cutoff for projection.
        expected_root: Merkle root to match after rebuild.

    Returns:
        BeliefState dict (byte-identical to the original project()).

    Raises:
        ReplayError: root_mismatch, malformed_entry, sig failure,
            unknown_entry_kind, rule errors, or projection errors.
    """
    entries = _validate_export(export)

    # Root check FIRST — before any replay state exists.
    _verify_root(entries, expected_root)

    return _replay_entries(entries, authority, rule_bindings, as_of)


def counterfactual(
    export: dict,
    delta: dict,
    authority: LocalAuthority,
    rule_bindings: dict[str, tuple[str, int]],
    as_of: int,
) -> dict:
    """Counterfactual replay with log modifications.

    No *expected_root* — the modified log is new by construction.
    Internal integrity: the modified log is internally consistent
    (valid entries, valid Merkle tree) but makes no claim about
    correspondence to any prior log.

    Empty delta is equivalent to ``replay()`` (byte-identical output).

    Args:
        export: dict from export_log().
        delta: modification spec with optional keys:
            - remove_entry_indices: list[int] — indices into original
            - add_entries: list[bytes] — canonical entry bytes to append
            - rule_bindings_override: dict[str, tuple[str, int]]
        authority: trust root.
        rule_bindings: base bindings (overridable by delta).
        as_of: logical-time cutoff.

    Returns:
        BeliefState dict.

    Raises:
        ReplayError: for validation or construction failures.
    """
    entries = _validate_export(export)

    if not isinstance(delta, dict):
        raise ReplayError("delta must be a dict")

    # -- Extract and validate delta fields --

    remove_indices = delta.get("remove_entry_indices", [])
    if not isinstance(remove_indices, list):
        raise ReplayError("remove_entry_indices must be a list")
    for idx in remove_indices:
        if not isinstance(idx, int) or isinstance(idx, bool):
            raise ReplayError(
                f"remove_entry_indices element must be int, "
                f"got {type(idx).__name__}")
        if idx < 0 or idx >= len(entries):
            raise ReplayError(
                f"remove_index_out_of_range: {idx} "
                f"(log has {len(entries)} entries)")

    add_entries = delta.get("add_entries", [])
    if not isinstance(add_entries, list):
        raise ReplayError("add_entries must be a list")
    for i, ae in enumerate(add_entries):
        if not isinstance(ae, bytes):
            raise ReplayError(
                f"add_entries element at index {i} must be bytes")
        # Validate decodability before any construction.
        _decode_entry(ae, f"add[{i}]")

    bindings_override = delta.get("rule_bindings_override", {})
    if not isinstance(bindings_override, dict):
        raise ReplayError("rule_bindings_override must be a dict")
    for k, v in bindings_override.items():
        if not isinstance(k, str):
            raise ReplayError(
                f"rule_bindings_override key must be str, "
                f"got {type(k).__name__}")
        if (not isinstance(v, (tuple, list)) or len(v) != 2
                or not isinstance(v[0], str)
                or isinstance(v[1], bool)
                or not isinstance(v[1], int)):
            raise ReplayError(
                f"invalid_rule_binding_override for {k!r}: "
                f"expected (str, int), got {v!r}")

    # -- Build modified entry list --
    # Removal first (deduplicate, reverse-sorted for stable indices).
    remove_set = set(remove_indices)
    modified = [e for i, e in enumerate(entries) if i not in remove_set]

    # Addition after removal.
    modified.extend(add_entries)

    # -- Merge rule bindings --
    merged_bindings = dict(rule_bindings)
    for prop, binding in bindings_override.items():
        merged_bindings[prop] = (binding[0], binding[1])

    return _replay_entries(
        modified, authority, merged_bindings, as_of)
