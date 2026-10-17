# IMPROVEMENT ORDER — the ladder, enforced as process

Cost order, cheapest first. Every refinement PR states which rung it is on and
why the lower rungs are exhausted. The weekly crank (`python -m engine.crank`)
recommends one rung-1 or rung-2 change with evidence rows; a human turns it
into the next contract, or the closed loop (`python -m engine.autoloop`, since
C7) lets the pack's own agents take the turn: the planner decides the data
(which runs next), the judge decides the verdict (recorded as `agent`-sourced;
a human's outranks it), and the refiner decides the training at rungs 1 and 2
only, as one exact text edit that is kept only if the agent's golden score does
not fall. Rung 3 still needs the parity matrix and rung 4 the export gate; the
loop never touches code, a guardrail, a verifier or a model pin.

The loop's law, on by default (`config/engine.yaml` `autoloop`), is the three
interviews as mechanism: an edit is kept only if a held-out set the loop never
tunes on does not fall (Schulman: redeploy only when the held-out benchmark
holds); an agent whose pass rate collapses is halted until it recovers (Musk:
drastic action when success leaves the set of outcomes); the judge is checked
against the operator and suspended when it is being overridden (Brown: the
grader must not be gamed); golden sets grow only from runs the operator marked
followed, never from the judge's own verdicts (the panel: fold graded traces
into the next environments, without self-labeling).

| Rung | Change | Gate | Where |
|---|---|---|---|
| 1 | Grounding / context: sources, memory queries, tables, onboarding text | none | `manifest.yaml` grounding + memory, `skills.md`, `workflow.md` |
| 2 | Harness: system prompt, tools, guardrails, loop params (`max_iterations`, `search_width`) | none | `prompts/`, `tools/`, `guardrails/`, `manifest.yaml` loop |
| 3 | Model swap | `engine.eval --models` matrix committed as `eval/matrix-<date>.md` showing score ≥ frontier on the same golden set; the manifest validator refuses otherwise. Orchestrators never swap. | `manifest.yaml` model |
| 4 | Post-training (specialist only) | `engine.export` refuses below 500 human-verdicted runs and refuses orchestrators | dataset file only; training is outside the engine |

Rules that hold on every rung:

- Behavior lives in pack files. Zero prompts in Python.
- The model proposes; deterministic code certifies. Never the reverse.
- Every number an orchestrator states is a citation to a certified figure.
- Every run, including failures, is a trace; every real action is an event.
- The RI judgement on each candidate (`agent_runs.judgement`) is replayable:
  `python -m engine.replay <run_id>`. Rising conflict mass m(∅) on an agent
  means the model is confidently wrong more often: fix at rung 1 or 2 before
  touching the model.
