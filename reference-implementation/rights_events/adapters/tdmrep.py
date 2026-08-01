"""Adapter (c): TDMRep / robots.txt / ai.txt opt-out signals -> opt_out events.

Two input forms, both self-published by the site operator, hence
EP type self_asserted:

- robots.txt / ai.txt (identical directive syntax): a User-agent group
  naming a known AI/TDM crawler with a full-site "Disallow: /" is read
  as an opt-out assertion by the operator.  Partial disallows are not
  read as opt-outs (a scoping decision, recorded in the claim only when
  the block is total).
- /.well-known/tdmrep.json (W3C TDM Reservation Protocol, Final CG
  Report 2024-02-02): every entry with "tdm-reservation": 1 is an
  opt-out assertion for its location; entries with 0 assert no
  reservation and produce no event.

The claimant is the site operator (identified by host); the subject is
the web origin.  Events record what the operator PUBLISHED — whether
crawlers honor it is outside this layer.  Pure functions; the checked-in
fixtures carry their capture provenance in MANIFEST.json.
"""

from __future__ import annotations

import json
from decimal import Decimal

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

# Known AI/TDM crawler user-agents (matched case-insensitively).  A
# declared, inspectable list: extending it is a policy-neutral adapter
# change (it widens which published blocks are read as opt-outs, never
# how they fuse).
AI_AGENTS = frozenset({
    "gptbot",
    "claudebot",
    "claude-web",
    "anthropic-ai",
    "ccbot",
    "google-extended",
    "applebot-extended",
    "perplexitybot",
    "bytespider",
    "cohere-ai",
    "meta-externalagent",
    "ai2bot",
    "omgilibot",
    "timpibot",
    "youbot",
})


def _parse_groups(text: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    """Parse robots.txt into (user_agents, rules) groups.

    A group is one or more consecutive User-agent lines followed by its
    rules.  Comments (# to end of line) and blank lines are ignored;
    blank lines do not terminate a group (per RFC 9309, groups end at
    the next User-agent line that follows at least one rule).
    """
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    in_agents = False

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            if in_agents:
                agents.append(value)
            else:
                if agents:
                    groups.append((agents, rules))
                agents = [value]
                rules = []
                in_agents = True
        elif field in ("allow", "disallow"):
            if agents:
                rules.append((field, value))
                in_agents = False
        # Other fields (sitemap, crawl-delay, ...) are not rules we read.

    if agents:
        groups.append((agents, rules))
    return groups


def parse_robots_txt(
    text: str,
    *,
    site_host: str,
    source_url: str,
    observed_date: str,
    agents: frozenset[str] = AI_AGENTS,
) -> list[RightsEvent]:
    """Transform robots.txt/ai.txt content into opt_out events.

    One event per known AI agent whose group contains a full-site
    "Disallow: /".  Case-variant duplicate agent lines within a group
    (seen in real files) collapse to one event.  Output sorted by
    event_id.
    """
    if not site_host:
        raise AdapterError("site_host is required")

    seen: dict[str, RightsEvent] = {}
    for group_agents, rules in _parse_groups(text):
        disallows = sorted({v for f, v in rules if f == "disallow" and v})
        if "/" not in disallows:
            continue
        for agent in group_agents:
            agent_key = agent.lower()
            if agent_key not in agents or agent_key in seen:
                continue
            seen[agent_key] = RightsEvent(
                event_id=f"tdmrep:robots:{site_host}:{agent_key}",
                event_type=EventType.OPT_OUT,
                subject_ids=(f"web:{site_host}",),
                claimant=site_host,
                claim={
                    "mechanism": "robots.txt",
                    "agent": agent,
                    "disallow": disallows,
                },
                ep_type=EPType.SELF_ASSERTED,
                source_url=source_url,
                observed_date=observed_date,
            )
    return [seen[k] for k in sorted(seen)]


def parse_tdmrep_json(
    text: str,
    *,
    site_host: str,
    source_url: str,
    observed_date: str,
) -> list[RightsEvent]:
    """Transform a /.well-known/tdmrep.json document into opt_out events.

    One event per entry with "tdm-reservation": 1; the claim preserves
    the entry's own field names (location, tdm-reservation, tdm-policy).
    Output order follows the document (the spec's arrays are ordered).
    """
    if not site_host:
        raise AdapterError("site_host is required")
    try:
        entries = json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"tdmrep.json is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise AdapterError("tdmrep.json must be a JSON array of entries")

    events: list[RightsEvent] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise AdapterError(f"tdmrep.json entry {i} must be an object")
        if entry.get("tdm-reservation") != 1:
            continue
        location = entry.get("location")
        if not isinstance(location, str) or not location:
            raise AdapterError(f"tdmrep.json entry {i} has no location")
        claim: dict = {
            "mechanism": "tdmrep.json",
            "location": location,
            "tdm-reservation": 1,
        }
        if "tdm-policy" in entry:
            claim["tdm-policy"] = entry["tdm-policy"]
        events.append(RightsEvent(
            event_id=f"tdmrep:wellknown:{site_host}:{location}",
            event_type=EventType.OPT_OUT,
            subject_ids=(f"web:{site_host}",),
            claimant=site_host,
            claim=claim,
            ep_type=EPType.SELF_ASSERTED,
            source_url=source_url,
            observed_date=observed_date,
        ))
    return events
