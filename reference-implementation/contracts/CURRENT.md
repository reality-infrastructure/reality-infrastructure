TASK — Versioned verification-rule store, logged as first-class evidence (M-RI-05)

OBJECTIVE
Ship ri_core/rules.py: an append-only, versioned rule store where every rule version is
itself a logged evidence entry with provenance — closing spec §5 (Versioned Rule Set),
CONFORMANCE C7's storage half, and giving counterfactual() (M-RI-08) its rule-substitution
substrate.

CONTEXT
- SPEC.md §4 (Verification Rule: versioned, logged function r_v; each version an Entity with
  provenance), §5 (Versioned Rule Set R = {(rule_id, version, fn_spec, ltime)}; append-only),
  §11 (MUST log verification rules as versioned first-class evidence), §14 (rule-version
  counterfactuals)
- CONFORMANCE.md C7
- ARCHITECTURE.md: rules.py imports serialization + stdlib only; integrates with log.py and
  provenance.py at the CALLER's level (M-RI-07), not by importing them — rules.py produces
  encodable records; wiring into EvidenceLog/ProvenanceGraph happens above
- Determinism law: rule evaluation must be pure

PLAN GATE
Before writing any code, state:
(a) What fn_spec IS. This is the load-bearing call. Arbitrary Python (exec/eval) violates
    determinism and safety; a callable registry makes rule versions non-serializable and
    non-replayable across processes. Recommend: fn_spec as a small DECLARATIVE predicate AST
    encoded in serialization-native types — e.g. ["and", ["ge", ["field", "ltime"], 1],
    ["in", ["field", "source_id"], ["const", [...]]]] — with a closed operator set
    (comparisons, boolean ops, field access, const, membership). State your operator set,
    evaluation semantics against an Observation-shaped dict, and error behavior (missing
    field, type mismatch → typed error, never silent False; distinguish "rule rejects" from
    "rule cannot evaluate").
(b) Version semantics: versions per rule_id are dense ints from 1; registering rule_id vN
    requires vN-1 exists; re-registering an existing (rule_id, version) raises; the store
    never exposes "latest" implicitly — callers must name a version explicitly OR call an
    explicit latest_version(rule_id) so counterfactuals are never ambiguous about which
    version ran.
(c) The evidence-record shape for a rule version: an encodable dict (kind='rule_version',
    rule_id, version, fn_spec, ltime) whose canonical bytes are what gets appended to the
    EvidenceLog by the caller — plus a stable rule_version entity id convention (e.g.
    "rule:{rule_id}:v{version}") matching provenance.py's rule_version Entity kind.
(d) Evaluation API: evaluate(rule_spec, observation_dict) -> VerificationResult where the
    result is an encodable record carrying (rule_id, version, verdict: bool, ltime) — and
    confirm evaluation is a pure function with no store access.

CONSTRAINTS (MUST / NEVER)
- MUST: store append-only; registration returns the encodable evidence record
- MUST: fn_spec round-trips serialization.py byte-identically; evaluation deterministic
- MUST: "cannot evaluate" (missing field/type error) raises typed RuleError — never a silent
  verdict; verdict False is reserved for a rule that evaluated and rejected
- MUST: full suite stays green (199 prior)
- NEVER: exec, eval, pickle, importlib, getattr-based dispatch on user strings outside the
  closed operator table
- NEVER: floats in specs or results
- NEVER: mutate or overwrite a registered version

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_rules.py` passes; paste output
- [ ] Closed-world operator test: an unknown operator in fn_spec raises at REGISTRATION time
      (specs validated when stored, not lazily at evaluation)
- [ ] Version discipline: registering v2 before v1 raises; re-registering v1 raises;
      latest_version returns the max; both evidence records encode byte-stably (golden files)
- [ ] Semantics matrix: a fixture rule evaluated against 6+ observation fixtures covering
      pass, fail, missing-field RuleError, type-mismatch RuleError
- [ ] Rule-version substitution: same observation evaluated under v1 vs v2 of a rule yields
      different verdicts (the counterfactual substrate works)
- [ ] Cross-process determinism: same spec + observation in 2 subprocesses, different
      PYTHONHASHSEED ⇒ identical encoded VerificationResult bytes
- [ ] Full suite green (199 prior + new)

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-05: versioned verification-rule
store as first-class evidence" → push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE — and item 5 MUST be
the acceptance checklist above, each box answered with its pasted proof (test name + output),
not a category summary.

STOP CONDITIONS
Halt and report — do not proceed — if: the declarative AST cannot express a needed predicate
without exec/eval; spec §4's "function" wording appears to conflict with a declarative
fn_spec (surface it — the research record supports declarative: rules must be DATA to be
logged as evidence); any frozen golden file would change; or push fails.
