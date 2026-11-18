"""The public node, paced (PREREG A48 R227): NOT part of ri_core, NOT a test. The only module of the
Solana arena that touches the network. Every call is logged (method, bytes, seconds, HTTP status).

The node answered HTTP 429 at the seventh call inside about eight seconds (A48, measured), so calls
are spaced (MIN_GAP_S) and a refused call is tried three times with growing gaps, then given up:
the caller records it and grades PARTIAL; no other source is ever tried (SETTLED_SOLANA.md 6d).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
MIN_GAP_S = 1.2
TRIES = 3


class Refused(Exception):
    pass


class Node:
    def __init__(self, url: str = PUBLIC_RPC, min_gap_s: float = MIN_GAP_S):
        self.url, self.min_gap_s = url, min_gap_s
        self.log: list[dict] = []
        self._last = 0.0

    def call(self, method: str, params: list) -> tuple[dict, bytes]:
        """The parsed response and its exact bytes. Raises Refused after TRIES spaced attempts."""
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        last_status = None
        for attempt in range(TRIES):
            wait = self.min_gap_s * (1 + 2 * attempt) - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            t = time.monotonic()
            self._last = t
            try:
                req = urllib.request.Request(self.url, body, {"Content-Type": "application/json",
                                                              "User-Agent": "proof-of-outcome-arena/1"})
                raw = urllib.request.urlopen(req, timeout=90).read()
                status = 200
            except urllib.error.HTTPError as exc:
                raw, status = b"", exc.code
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raw, status = b"", f"net:{type(exc).__name__}"
            self.log.append({"method": method, "bytes": len(raw), "seconds": round(time.monotonic() - t, 3),
                             "status": status, "attempt": attempt + 1})
            last_status = status
            if status == 200:
                doc = json.loads(raw)
                err = doc.get("error")
                if err and err.get("code") in (429, -32005):          # rate or node behind: retry
                    continue
                return doc, raw
        raise Refused(f"{method}: refused after {TRIES} tries (last {last_status})")
