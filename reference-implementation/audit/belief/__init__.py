"""M-RI-17 belief-engine pass over the post-remediation contested set.

Everything discretionary in this package was declared FROZEN in
audit/prereg/M-RI-17-PREREGISTRATION.md, committed strictly before this
package existed (ordering provable from git history). The wall-frozen C2
machinery (rights_events adapter, pipeline, Denoeux cautious fold) is
invoked as-is; nothing in ri_core, the adapter, the fold, or any frozen
audit rule is modified here.

Every contest expressed by this pass is a statement that RECORDS
DISAGREE and requires verification against the underlying instruments;
nothing here characterizes any person or entity (privacy ruling R1).
"""
