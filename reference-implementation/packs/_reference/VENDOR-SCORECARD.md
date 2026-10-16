# VENDOR SCORECARD — slot: records_feed (fixture vendors)

| Criterion | Requirement | mock_a | mock_b | Evidence |
|---|---|---|---|---|
| Event latency | every record lands in `events` within 3600 s | yes | yes | tests/test_engine_c3.py |
| Suppression enforcement | checked before every outbound command | yes (config list) | yes (config list) | tests/test_engine_c3.py |
| Disclosure / opt-out flags | `disclosure` required on every command | enforced by gateway | enforced by gateway | adapters.yaml `required_flags` |
| Export rights | `export_all` returns every record + command | yes | yes | tests/test_engine_c3.py |
| Swap cost | binding change only | one line | one line | tests/test_engine_c3.py |
| Price | n/a (fixture) | 0 | 0 | |

Decision: fixture only — both vendors are synthetic stand-ins for the slot.
