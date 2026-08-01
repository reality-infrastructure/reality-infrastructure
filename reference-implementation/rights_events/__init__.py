"""rights_events — domain layer feeding rights events through the RI engine.

Contract 1 (the event layer).  The engine (ri_core) is consumed read-only:
serialization, EP typing validation, Denoeux cautious fusion, Merkle
logging, inclusion proofs.  This package owns the event schema, evidence
adapters, the fusion pipeline, belief-object construction, and the replay
CLI.
"""

from rights_events.schema import EPType, EventType, RightsEvent, SchemaError

__all__ = ["EPType", "EventType", "RightsEvent", "SchemaError"]
