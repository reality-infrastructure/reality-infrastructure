# IMPROVEMENT ORDER — the ladder, enforced as process

Cost order, cheapest first. Every refinement PR states which rung it is on and
why the lower rungs are exhausted. The weekly crank (`python -m engine.crank`)
recommends one rung-1 or rung-2 change with evidence rows; a human turns it
into the next contract.

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
