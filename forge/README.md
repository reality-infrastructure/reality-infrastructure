# FORGE — start a new rigorous build from assembly, not invention

You are (probably) a fresh session opening a new domain build. This file is
self-contained: everything you need is in this directory or cited from it.

## What this repo already proved

The engine (`reference-implementation/ri_core/`) is frozen and proven: RFC
9162 Merkle evidence log, Denœux cautious combination, PROV-DM provenance,
declarative rules, byte-identical replay. Two domains run on it with the
domain layer byte-identical between them — a music split-sheet conflict
(`rights_events/song_x.py`) and real Cook County parcels
(`rights_events/parcels.py`); the wall proof is an empty `git diff` recorded
at `contracts/completed/C2-second-domain.md:163-173`. You do not modify the
engine or the frozen domain-layer modules (`rights_events/schema.py`,
`policy.py`, `pipeline.py`, `replay.py`). Ever. A build that seems to need
that has found a kill-criterion finding — report it; do not code around it.

## Start a new build (one command)

From the repo root:

    python forge/scaffold.py <domain_name>

This generates, into the existing `reference-implementation/` structure:

    contracts/<domain>/CONTRACT.md     closed-contract skeleton (validated)
    contracts/<domain>/PREREG.md       pre-registration skeleton
    contracts/<domain>/SCOREBOARD.md   named gates + evidence slots
    rights_events/adapters/<domain>.py the adapter interface, with the six
                                       domain decisions you must declare
    tests/test_<domain>_gates.py       smoke suite: 1 test passes (engine
                                       wired), 1 fails until the adapter is
                                       real

It is idempotent (refuses to overwrite an existing domain) and stdlib-only.

## Where things live (read before pointing --dest anywhere)

`forge/` sits at the REPO ROOT. Everything it generates lands one level down,
under `reference-implementation/` — the tree where contracts/, audit/, tests/,
and the engine already live. There is exactly ONE contracts/ tree in this
repo and it is `reference-implementation/contracts/`; nothing belongs in a
root-level contracts/, adapters/, or tests/ directory, and scaffold.py will
refuse to create one (it rejects any `--dest` that is not a
reference-implementation-shaped tree containing ri_core/,
rights_events/adapters/, tests/, and contracts/). You should almost never
need `--dest`: the default resolves to the reference-implementation beside
this forge/. If you pass it anyway, point it at such a tree — never at a
repo root.

## The sequence, timed (Gate 4 — honest numbers)

Measured on this machine 2026-08-03 (mechanical steps timed for real;
authoring steps are estimates for a session that already knows its domain):

| # | Step | Time |
|---|------|------|
| 1 | `python forge/scaffold.py <domain>` | 0.2s (measured) |
| 2 | Fill CONTRACT.md — every `{{...}}`: context, non-goals, deliverables, the contract's named risk as a kill criterion | ~5 min |
| 3 | Fill PREREG.md §§1-6 and COMMIT IT before touching data — §2 requires measuring the input source (bytes, sha256, counts) from disk | ~6 min |
| 4 | `pytest tests/test_<domain>_gates.py -q` — confirm 1 passed (engine wired) / 1 failed (adapter awaits) | 4s (measured 3.1s) |
| 5 | Open `rights_events/adapters/<domain>.py` — you are now ready to write domain logic | — |

**Honest total: ~11-12 minutes** from invocation to "ready to write domain
logic", UNDER TWO CONDITIONS: the domain's source data is already on disk
(PREREG §2 measures it; fetching or negotiating access is not in this
budget and alone can exceed 15 minutes), and the author arrives knowing the
domain well enough to fill the contract without research. First-ever runs
that also read PATTERNS.md and a prior contract for orientation land nearer
~20 minutes. The 15-minute target holds for the data-on-disk, known-domain
case and is not claimed beyond it.

## What's in this directory

    INVENTORY.md          every pattern in this library, cited file:line to
                          where it shipped (incl. §8, the two-domain diff
                          that defines the adapter interface, and §9,
                          mid-contract amendments)
    PATTERNS.md           the five extracted moves, one page each
    templates/            CONTRACT / PREREG / SCOREBOARD skeletons
    schemas/ep.schema.json  the domain-neutral rights-event schema (JSON
                          Schema), both proven domains cited in $comment
    adapters/new_domain.py  the adapter skeleton scaffold.py instantiates
    scaffold.py           the one command
    fixtures/demo_fixture/  Gate 3 validation output, clearly labeled — not
                          a domain
    SCOREBOARD.md         this contract's own four gates, with evidence

## The rules the scaffold carries (read PATTERNS.md before your plan gate)

1. Closed contract: scope OUT is a wall; gates are deterministic.
2. Pre-registration: metric before data; the commit ordering is the proof.
3. Tests are the finish line: DONE = named gates green, evidence pasted.
4. Adversarial pass: tamper tests, known-answer commitments — watch every
   proof mechanism fail before trusting it.
5. No fabrication: source_url + observed_date or the event does not exist;
   NULL stays NULL; absence is "no record found", never a claim about the
   world.
