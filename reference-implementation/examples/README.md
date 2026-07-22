# Reality Infrastructure -- Title-Belief Dossier Example

## What This Shows

Builds a complete title-belief dossier for a fictional distressed parcel
(PIN 99-00-000-000-0000), demonstrating every Reality Infrastructure
system capability:

- **Evidence intake** from five sources with conflicting claims
- **Verification rules** that exclude stale records (citing rule id and version)
- **Provenance-class partitioning** collapsing two data brokers (same upstream
  aggregator) into a single evidence class -- Sybil deduplication in action
- **Belief fusion** via the cautious conjunctive rule, with explicit
  contradiction (mass on the empty set) when sources disagree
- **Counterfactual analysis** showing how belief shifts if a quitclaim deed
  is removed from the evidence log
- **Byte-identical replay** with Merkle root attestation proving the dossier
  is reproducible from the evidence log alone

## Prerequisites

Python 3.11+. No dependencies beyond `ri_core` (stdlib only).

## How to Run

From the repository root:

    python examples/title_dossier.py

## Sample Output (Provenance Classes)

This is the system's differentiator -- no other title-search tool shows you
WHY it trusts certain sources and HOW duplication was detected:

```
  Proposition: owner
  Number of independent evidence classes: 4

    Class [county_assessor]:
      Members: county_assessor

    Class [data_broker_alpha]:
      Members: data_broker_alpha, data_broker_beta
      NOTE: These sources share provenance (same upstream
      data aggregator). The system treats them as a single
      evidence class -- repetition does not increase
      confidence.

    Class [recorder_of_deeds]:
      Members: recorder_of_deeds

    Class [tax_sale_authority]:
      Members: tax_sale_authority

  How-provenance polynomial: HowProvenance(county_assessor + data_broker_alpha*data_broker_beta + recorder_of_deeds + tax_sale_authority)

  Reading: This belief was derived from 4 independent
  evidence paths. The two data brokers are jointly represented
  as a single monomial (their product in the polynomial) because
  they share a common upstream data source.
```

The polynomial `county_assessor + data_broker_alpha*data_broker_beta +
recorder_of_deeds + tax_sale_authority` is a machine-readable audit trail:
four independent derivation paths, with the two brokers appearing as a
single product term because they share provenance.

## What Each Section Means

| Section | What it shows |
|---------|--------------|
| **Evidence Intake** | All observations ingested, with source, logical time, and claim |
| **Verification Results** | Which records passed the freshness rule and which were excluded (with rule id + version) |
| **Provenance Classes** | How sources are grouped by shared provenance; the how-provenance polynomial |
| **Fused Belief** | The system's belief per proposition; m(emptyset) = contradiction requiring curative work |
| **Sybil Demonstration** | ILLUSTRATION showing that naive source-counting inflates confidence; the system is immune |
| **Counterfactual** | What the dossier would say if a specific record were successfully challenged |
| **Replay Attestation** | Merkle root proving the dossier can be reproduced from the evidence log alone |
