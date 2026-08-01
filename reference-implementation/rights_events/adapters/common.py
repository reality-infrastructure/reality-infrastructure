"""Shared adapter error type.

Adapters are pure functions: evidence-format text in, schema events out.
They never fetch anything (Contract 1 OUT: no network fetching of live
data); real-format samples are checked-in captures whose source_url and
observed_date live in the fixture MANIFEST.json.
"""

from __future__ import annotations


class AdapterError(Exception):
    """Error transforming an evidence format into rights events.

    Raised for: missing required columns or fields, malformed input
    documents, and values that cannot be represented deterministically.
    """
