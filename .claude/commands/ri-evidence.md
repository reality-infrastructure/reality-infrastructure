---
description: Gather evidence on one claim without concluding anything — each item is a verbatim excerpt from a source actually opened, typed by how it knows what it says, and recorded on the ledger. The agent submits evidence; the engine issues the verdict.
---

The claim: **$ARGUMENTS** (a claim id and its candidate hypotheses. None given: ask for them and stop.)

Why this command exists: a model that is rewarded for an answer will produce the
answer, with or without the work. It will report a test as passing after removing
the test. So the agent is not asked for an answer. It is asked for the record
that says it, and a rule it does not control turns records into a belief.

## The one rule

**An agent produces evidence. The engine produces verdicts.** In this command you
never write "therefore", "this confirms", "probably", a percentage or a
conclusion. If you believe something, find the record that says it and submit the
record. If no record exists, record that you looked, where, and what came back.
The claim then stays unresolved, and unresolved is a valid result.

## Before the first fetch

The hypotheses for the claim are fixed before any source is opened. If they are
not written down yet, write them, show them, and stop for confirmation. A
hypothesis added after a source was read is a method changed after its result
was seen.

## For every source you try to open

Log the attempt, whatever came back, from the directory `$RI_HOME`:

```bash
python -m packs.ri_operator.record append fetch_logged --entity-type claim --entity-id "<claim_id>" --payload '{"claim_id": "<claim_id>", "url": "<url>", "outcome": "ok|refused|timeout|unparsed|not-found|error"}' --source agent:ri-evidence
```

**An error is not an empty result.** A refused or timed-out source was not read.
It says nothing about what the source contains.

## For every excerpt that bears on a hypothesis

One item per excerpt, written to a file:

| Field | Rule |
|---|---|
| `claim_id` | the id given. Never invented. |
| `hypothesis` | exactly one of the claim's fixed hypotheses |
| `source_url` | the address actually opened this session, to the specific document. A search page, a summary or an address you did not open is not a source. |
| `source_tier` | `PRIMARY` (the issuing body's own record), `SECONDARY` (a report of it), `TERTIARY` (a report of a report) |
| `ep_type` | how the source knows: `statutory_registry`, `third_party_attested`, `self_asserted`, `cryptographically_signed` |
| `quote` | the verbatim excerpt that carries the point, 60 words at most. No paraphrase. |
| `observed_date` | the date you opened it, `YYYY-MM-DD` |
| `published_date` | as stated on the document, or null |
| `derived_from` | if this source restates another document, that document's address; else null |
| `source_id` | a stable short name for the issuing body |
| `note` | what the excerpt shows within the source's own scope. Not broadened. |

```bash
python -m packs.ri_operator.record append evidence_submitted --entity-type claim --entity-id "<claim_id>" --payload @<file> --source agent:ri-evidence
```

Rules that decide what an item is worth later, so they are recorded now and not
argued:

- **A party describing itself is `self_asserted`**, however official the page
  looks.
- **Two sources that trace to one document are one witness.** Fill
  `derived_from` so they are not counted twice.
- **Evidence against is submitted exactly as evidence for.** Look for the
  excerpt that would disprove the hypothesis you expect to win, and log the
  search even if it finds nothing.
- **Absence is worded as absence:** "no record found in the sources queried",
  never "it did not happen".
- **A value that is missing stays missing.** It is not filled from context.

## The verdict is not yours

Combining the items into a belief is done by the engine's fusion rule over the
ledger, under masses declared before the data was seen. For a new domain that has
no adapter yet, the starting point is `python forge/scaffold.py <domain>` from the
repository root, which generates the contract, the pre-registration and the
adapter stub. This command stops at the evidence.

## Output

```
CLAIM            : <claim_id>
HYPOTHESES       : <the fixed list>
SOURCES TRIED    : <n>   ok <n>   not read <n>
ITEMS SUBMITTED  : <n>   by hypothesis: <h1> <n>, <h2> <n>
AGAINST THE EXPECTED ANSWER: <n items, or "searched <where>, none found">
NOT READ         : <each address and its outcome>
EVENTS           : <event_ids>
```

No sentence in the report says which hypothesis is true.
