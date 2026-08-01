"""Adapter (a): BWARM-style works-registration sample -> statutory_registry events.

Input format: a column subset of the DDEX BWARM (Bulk Communication of
Work and Recording Metadata) flat-file feed — a works TSV
(FeedProvidersWorkId, ISWC, WorkTitle) and a work-right-shares TSV
(FeedProvidersWorkId, FeedProvidersWorkRightShareId, InterestedPartyName,
RightSharePercentage, RightsType).  BWARM is the format the US statutory
mechanical-licensing registry publishes bulk works data in; hence
EP type statutory_registry.

One chain_assertion event per work row: the registry operator asserts
the work's registered shares.  Share percentages become Decimal (never
float).  Output order follows the works file; shares within a claim are
ordered by share id.  Pure function of its inputs.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

_WORKS_COLUMNS = ("FeedProvidersWorkId", "ISWC", "WorkTitle")
_SHARES_COLUMNS = (
    "FeedProvidersWorkId", "FeedProvidersWorkRightShareId",
    "InterestedPartyName", "RightSharePercentage", "RightsType",
)


def _read_tsv(text: str, required: tuple[str, ...], name: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    fieldnames = reader.fieldnames or []
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise AdapterError(f"{name} is missing columns: {missing}")
    return list(reader)


def parse_works_registration(
    works_tsv: str,
    shares_tsv: str,
    *,
    registry_operator: str,
    source_url: str,
    observed_date: str,
) -> list[RightsEvent]:
    """Transform a works + shares TSV pair into rights events.

    registry_operator is the claimant: the registry publishing the
    records.  source_url and observed_date come from the fixture
    manifest (the capture, or for SYNTHETIC samples the format
    documentation), never from a clock.
    """
    works = _read_tsv(works_tsv, _WORKS_COLUMNS, "works TSV")
    shares = _read_tsv(shares_tsv, _SHARES_COLUMNS, "shares TSV")

    shares_by_work: dict[str, list[dict]] = {}
    for row in shares:
        work_id = row["FeedProvidersWorkId"]
        try:
            percentage = Decimal(row["RightSharePercentage"])
        except InvalidOperation as exc:
            raise AdapterError(
                f"Share {row['FeedProvidersWorkRightShareId']!r} has "
                f"non-numeric percentage "
                f"{row['RightSharePercentage']!r}") from exc
        shares_by_work.setdefault(work_id, []).append({
            "share_id": row["FeedProvidersWorkRightShareId"],
            "party": row["InterestedPartyName"],
            "percentage": percentage,
            "rights_type": row["RightsType"],
        })

    events: list[RightsEvent] = []
    for row in works:
        work_id = row["FeedProvidersWorkId"]
        iswc = row["ISWC"].strip()
        subject = f"work:iswc:{iswc}" if iswc else f"work:feed:{work_id}"
        work_shares = sorted(
            shares_by_work.get(work_id, []), key=lambda s: s["share_id"])
        share_claims: dict[str, Decimal] = {}
        for share in work_shares:
            if share["party"] in share_claims:
                raise AdapterError(
                    f"Work {work_id!r} lists party {share['party']!r} "
                    f"twice; cannot form a share table")
            share_claims[share["party"]] = share["percentage"]
        events.append(RightsEvent(
            event_id=f"bwarm:{work_id}",
            event_type=EventType.CHAIN_ASSERTION,
            subject_ids=(subject,),
            claimant=registry_operator,
            claim={
                "title": row["WorkTitle"],
                "share_claims": share_claims,
                "share_details": work_shares,
            },
            ep_type=EPType.STATUTORY_REGISTRY,
            source_url=source_url,
            observed_date=observed_date,
        ))
    return events
