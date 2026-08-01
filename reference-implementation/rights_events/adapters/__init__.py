"""Evidence adapters: one module per evidence format (Contract 1, P2).

(a) bwarm        works-registration sample -> statutory_registry events
(b) c2pa         C2PA manifest store      -> cryptographically_signed events
(c) tdmrep       robots.txt / tdmrep.json -> self_asserted opt_out events
(d) pro_conflict conflicting registrations -> third_party_attested events

Adapter internals may be format-specific; the events they emit use only
the domain-neutral schema.
"""

from rights_events.adapters.common import AdapterError

__all__ = ["AdapterError"]
