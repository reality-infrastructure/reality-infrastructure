"""Adapter skeleton: <evidence format> -> <ep_type> rights events.

GENERATED SKELETON — this module is the exact interface a new domain must
implement to run on the engine unchanged. It was derived by diffing the two
shipped domains (forge/INVENTORY.md §8): everything common to
rights_events/adapters/pro_conflict.py and rights_events/adapters/
cook_parcels.py is engine contract and appears below as code; everything
that differed is domain surface and appears below as a decision the new
domain must declare.

THE ENGINE CONTRACT (do not vary — both shipped domains satisfy all of it):

- Adapters are pure functions: evidence-format text in, list[RightsEvent]
  out (adapters/common.py:1-7). No network, no clock, no randomness.
- Errors raise AdapterError (adapters/common.py:12).
- Output order is deterministic — sort by (observed_date, event_id)
  (pro_conflict.py:22-24).
- Every event carries a real source_url + observed_date, or the event does
  not exist (schema.py:175-176; C2-second-domain.md:91-93). NULL stays NULL.
- No floats anywhere in claim payloads — Decimal or int (schema.py:71-102).
- The schema is closed: six EventTypes, four EPTypes, nine fields
  (schema.py:45-60, :129-147). If this domain seems to need a seventh event
  type or a tenth field, STOP — that is a kill-criterion finding, not an
  adapter decision (C2-second-domain.md:132-135).

THE DOMAIN SURFACE (each shipped domain declared these in its module
docstring; declare yours the same way, then delete this instruction):

1. EVIDENCE FORMATS: what documents this adapter parses, and where their
   provenance MANIFEST lives (cook_parcels.py:7-21).
2. EP-TYPE MAPPING: which EPType each source maps to, and why that is
   honest (pro_conflict.py:8-10 argues the choice, not just states it).
3. CLAIMANT CONVENTIONS: module constants naming each claimant; a routing
   claimant never erases real actors — recorded parties stay verbatim in
   payloads (cook_parcels.py:78-81, :23-32).
4. SUBJECT-ID SCHEME: one prefix, stated (song_x.py:47 'work:...';
   parcels.py:74 'parcel:...').
5. ENTITY RESOLUTION: mechanical, deterministic, declared — or explicitly
   none (cook_parcels.py:34-54).
6. DISPUTE RULE: when conflicting claims emit a dispute event, and what
   claimant names the detector (pro_conflict.py:14-18, :35).
"""

from __future__ import annotations

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

# --- Domain surface item 4: subject-id scheme ---------------------------
SUBJECT_PREFIX = "new_domain:"

# --- Domain surface item 3: claimant conventions ------------------------
# e.g. DETECTOR_CLAIMANT = "records-conflict-check" (cook_parcels.py:81)

# --- The contested question this domain commits beliefs for -------------
# (both shipped domains used "ownership_shares": song_x.py:48, parcels.py:44)
QUESTION = "ownership_shares"


def parse_events(document_text: str) -> list[RightsEvent]:
    """Parse one evidence document into schema events.

    The engine contract for this function (INVENTORY.md §8, common surface
    item 1): pure function of its input; returns a deterministically
    ordered list[RightsEvent]; raises AdapterError on malformed input.

    Split into several parse_* functions plus a parse_all composition if
    the domain has several evidence formats (cook_parcels.py:218-319).
    """
    raise NotImplementedError(
        "adapter not implemented: parse_events() is the scaffold skeleton. "
        "Implement the six domain-surface declarations in this module's "
        "docstring, then replace the generated smoke suite with real gate "
        "tests.")
