# Case Study: One Parcel, One Wrong Record

**The Registry Signal** — parcel verification for land banks and public land holders

---

## The situation

Land banks act on their inventory records. Acquisition, maintenance, disposition,
reporting to funders — all of it assumes the record is right. When a record is wrong, the
cost surfaces later: a deal that stalls, work ordered on the wrong parcel, a dispute over
who actually holds title. The cost of bad property records industry-wide is a matter of
published research: fraud and forgery claims now average $206,976 per refinance
transaction — nearly seven times all other claim types — and account for over 40% of
refinance-related title-insurer losses (ALTA-commissioned Milliman study, November 2025).

A Cook County land bank shared its parcel inventory with us — roughly 700 records — as
part of a pilot. We selected one residential parcel in the land bank's service area and
asked one question: **does the public record agree with the inventory?**

## What we did

We pulled four sources for that one parcel: the land bank's own inventory record, plus
three public county sources — the published deed and sales records, the assessment roll,
and tax-sale records. Before pulling any data, we fixed in writing how much weight each
kind of source would carry. The data decides *what* the evidence says — never *how much
it counts*.

Every value in the analysis traces to a named field in a frozen copy of its source
record. One source — the tax-sale data — returned nothing for this parcel, so it
contributes nothing: we state that plainly rather than treat silence as an all-clear
(which it is not).

## What we found

The inventory says the parcel was **sold in 2017**.

The county's recorded deed chain — six sale records spanning 2000 to 2017 — tells a
different story. The only conveyance recorded in 2017 came months after the date the
inventory gives, and the seller of record is a private individual, not the land bank.
In fact, the land bank appears in no queried public record for this parcel at all — no
deed, no assessment-roll year — across data running from 1999 through 2026.

Instead of hiding that disagreement, the analysis quantifies it: **40% of the belief
about this parcel's disposition is unresolved conflict**, traced to exactly two records —
the inventory entry and the 2017 recorded deed. Along the way, the same analysis
collapsed 17 different spellings of owner names scattered across the county data into
the 10 real parties behind them.

## Why this is different

A normal data pipeline handles disagreement by averaging, or by picking a winner —
"newest record wins," "the county wins." Either way the disagreement disappears, which
means nobody is told to go fix it.

This system holds the conflict, measures it, and names the two records that produced it.
Then it answers the question an executive actually asks: *what if the inventory entry
were corrected?* Rerun the analysis without that one record and the conflict falls from
40% to zero — confidence that the land bank never conveyed the parcel then rests on the
recorded deed at 0.8, with the remaining 0.2 left honestly uncommitted rather than
invented.

And the entire analysis replays byte-for-byte from its evidence log. Anyone you delegate
can rerun it and get the identical document, verified by checksum.

## What it means for you

Every parcel in your inventory can carry a dossier like this: what the public record
says, where it disagrees with your records, how serious the disagreement is, and which
specific record to fix. That turns "our data is probably fine" into a checkable,
prioritized worklist.

**We can run this against any parcel you name — the first one is how this case study
happened.**

---

> ### How it works, in plain language
>
> **Evidence log.** Every number in the dossier traces back to a named field in a frozen
> copy of a source record. No untraceable claims.
>
> **Pre-registered confidence.** How much weight each kind of source carries is fixed in
> writing *before* any data is pulled — so the answer cannot be tuned after the fact.
>
> **Conflict, kept on the page.** When records disagree, the disagreement is measured
> and reported — never averaged away, never silently resolved.
>
> **Replayable.** Rerunning the analysis reproduces the dossier byte-for-byte, verified
> by checksum.

---

*Informational analysis of public records for demonstration purposes.
NOT a title opinion, title insurance commitment, or legal advice. All figures come from a
reproducible, test-enforced analysis transcript; records as retrieved in July 2026.*
