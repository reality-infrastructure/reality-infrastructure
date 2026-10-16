# compactor — skills (fixture)

## Mission
Summarize a window of old events in one paragraph so an agent's long-term
memory stays small. Raw events are never replaced; the summary only adds.

## Definition of good output
A `summary` string and one citation per event in the window
(`event:events:<event_id>`). A summary that cites an event outside the window
is rejected by the engine before it is written.
