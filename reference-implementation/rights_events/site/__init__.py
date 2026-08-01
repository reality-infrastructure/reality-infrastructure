"""rights_events.site — deterministic static-site generator (Contract 3).

Reads the run artifacts the existing runners produce and emits plain
HTML/CSS into docs/ at the repository root. Stdlib only, zero
JavaScript, no external assets: the output works from file:// on a
machine with no network. The generator READS artifacts (via
RightsPipeline.load, the replay CLI's own path); it never recomputes a
belief. Determinism: no build timestamps, no wall clock, sorted
iteration — the double-build byte-identity test is an acceptance
criterion, not decoration.
"""
