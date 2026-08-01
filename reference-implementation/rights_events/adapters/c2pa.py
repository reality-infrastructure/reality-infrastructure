"""Adapter (b): C2PA manifest store -> cryptographically_signed events.

WHAT IS MEASURED HERE, AND WHAT IS NOT (plan-gate ruling 1, 2026-08-01):
the claim payload of every event this adapter emits is the WHO-SIGNED-WHAT
fact read off the manifest bytes — the signing event.  The truth of what
was signed is untouched: a signature authenticates a signer, never a
claim.  An event saying "issuer I signed a manifest asserting X" is
evidence that I signed X, and no evidence at all that X is true.

Input format: the JSON manifest-store representation of a C2PA manifest
(as produced by c2pa-rs / c2patool from a signed asset).  One
chain_assertion event per signed manifest: claimant is the signer
(signature_info.issuer), the subject is the asset instance, and the
claim records the signer identity, certificate serial, signature time,
claim generator, and the labels of the signed assertions.

This adapter does NOT validate certificate chains (Contract 1 OUT) and
does NOT fetch anything.  Manifests without signature_info produce no
event: with no signer there is no signing event to record.  Floats in
the input are parsed as Decimal so claims stay deterministic.
"""

from __future__ import annotations

import json
from decimal import Decimal

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent


def parse_manifest_store(
    manifest_store_json: str,
    *,
    source_url: str,
    observed_date: str,
) -> list[RightsEvent]:
    """Transform a manifest-store JSON document into rights events.

    observed_date is the date the manifest store was captured (fixture
    manifest), not the signature time — the signature time is part of
    the signed fact and rides inside the claim.
    """
    try:
        store = json.loads(manifest_store_json, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Manifest store is not valid JSON: {exc}") from exc
    if not isinstance(store, dict) or "manifests" not in store:
        raise AdapterError("Manifest store must be a dict with 'manifests'")

    manifests = store["manifests"]
    if not isinstance(manifests, dict):
        raise AdapterError("'manifests' must be a dict of label -> manifest")

    active = store.get("active_manifest")

    events: list[RightsEvent] = []
    for label in sorted(manifests.keys()):
        manifest = manifests[label]
        sig = manifest.get("signature_info")
        if not isinstance(sig, dict) or not sig.get("issuer"):
            # No signer recorded: no signing event to measure.
            continue

        assertions = manifest.get("assertions", [])
        assertion_labels = sorted(
            a["label"] for a in assertions
            if isinstance(a, dict) and isinstance(a.get("label"), str))
        ingredients = sorted(
            ing["instance_id"] for ing in manifest.get("ingredients", [])
            if isinstance(ing, dict) and isinstance(
                ing.get("instance_id"), str))

        instance_id = manifest.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise AdapterError(
                f"Manifest {label!r} has no instance_id; cannot form a "
                f"subject identifier")

        claim: dict = {
            "signed_by": sig["issuer"],
            "claim_generator": manifest.get("claim_generator"),
            "asset_title": manifest.get("title"),
            "asset_format": manifest.get("format"),
            "assertion_labels": assertion_labels,
            "ingredients": ingredients,
            "is_active_manifest": label == active,
        }
        # Optional signature facts: present if the store records them,
        # absent otherwise — NULL stays NULL.
        if sig.get("cert_serial_number") is not None:
            claim["cert_serial_number"] = sig["cert_serial_number"]
        if sig.get("time") is not None:
            claim["signature_time"] = sig["time"]

        events.append(RightsEvent(
            event_id=f"c2pa:{label}",
            event_type=EventType.CHAIN_ASSERTION,
            subject_ids=(f"asset:{instance_id}",),
            claimant=sig["issuer"],
            claim=claim,
            ep_type=EPType.CRYPTOGRAPHICALLY_SIGNED,
            source_url=source_url,
            observed_date=observed_date,
        ))
    return events
