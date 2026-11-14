# VENDOR SCORECARD

This pack declares no adapter slots (`adapters.yaml` is empty), so there is no vendor
to score. If a slot is ever added, fill one table per slot before any build-or-buy
decision; the engine's adapter tests encode the first four rows as hard requirements.

| Criterion | Requirement | Vendor answer | Evidence |
|---|---|---|---|
| Event latency | every vendor record lands in `events` within `latency_sla_seconds` | | |
| Suppression enforcement | suppression list checked before every outbound command | | |
| Disclosure / opt-out flags | carried on every command the domain requires them for | | |
| Export rights | `export_all` returns everything the vendor holds about our entities | | |
| Swap cost | binding change only; zero orchestrator or specialist code | | |
| Price | per unit, per month, minimums | | |
