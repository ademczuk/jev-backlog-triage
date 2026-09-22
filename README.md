# Backlog triage with jev, on Vercel

Distilled 2026-09-22 from 15 videos (4h 11m of runtime), the Vercel AI Gateway
docs, and the treg recipe pages. Sponsor reads and channel plugs were stripped
before reading: 18 sentences out of 3241, each one listed in the audit file
rather than silently dropped.

## What jev is, in one paragraph

TypeSafe AI's "System One" model. It does not generate. You hand it a `state`
and a set of typed `questions`, and it returns a probability distribution over
options you defined, plus a calibrated confidence. Three question types: choice
(pick one of up to 255), score (an ordered rubric of 2 to 10 levels), and
boolean (probability a statement is true). It was trained with reinforcement
learning for calibrated decisions rather than RLHF, and the pitch is that the
confidence tracks accuracy, so code can act above a threshold and route to a
human below it.

## Why this is buildable today with only a Vercel account

jev landed on Vercel AI Gateway as `typesafe-ai/jev` on 16 September 2026. AI
SDK 7 exposes it through `experimental_evaluate`. There is no separate signup
and no waitlist on that route, which is worth knowing because several of the
videos predate it and tell you to join a waitlist. `vercel link` then
`vercel env pull` is the whole setup.

Cost is $0.042 per million input tokens with no output charge. The full open
items table for an engagement of this size is roughly 74k tokens, so one pass
over the entire backlog costs about a third of a cent and finishes in seconds.

## The limits, which matter more than the pitch

- **The context window is small.** 32k tokens for `state`, 64k for the whole
  request. Several reviewers hit this first. Anything longer needs map-reduce.
- **It cannot reason.** One reviewer tested it on judging which of their own
  threads were worth writing about; it called roughly half of them good, which
  is the answer you get from something that cannot do the judgment. Use it where
  the options are known and the call is a classification, not an analysis.
- **"Cannot hallucinate" is a narrower claim than it sounds.** It means jev will
  never break your schema: never a field you did not define, never an option you
  did not list. It does not mean the answer is correct. A well calibrated wrong
  answer is still wrong. Treat the confidence as a routing signal, not a truth
  signal.
- **Probabilities are not free.** Returning distributions is slower and dearer
  than returning a bare decision would be.

## Why this particular demo, for this particular audience

The engagement has a measured reporting defect: the board carries 16 open
decision rows against 37 in the record, no completion has been logged since the
board was seeded, and 15 of the 16 tracked rows have no due date, so nothing on
it can go overdue. Separately, the one number nobody has is agent session-hours
per ticket, and the first milestone's go/no-go depends on it.

So this is not a toy. It takes each row of the real backlog as `state` and asks
three closed questions: who must act next, does this block the milestone, and
how big is one competent pass at it. The third question is the point. It
produces the sampling frame for the session-hours measurement that is currently
blocking a six month commitment, as a side effect of a run that costs a third of
a cent.

It also reconciles the two sources. A row that jev calls milestone-blocking and
that is absent from the board is exactly the item the current reporting hides.

## The architecture this follows

Cascade, do not replace. jev clears the rows it is confident about and every row
below `ESCALATE_BELOW` goes to a person. That is deliberately the same shape the
fleet already validated for cheap-model cascades: schema-gated, escalate
upward, never a silent autonomous decision on a low-confidence call.

## Running it

```
vercel link
vercel env pull
npm install
npm run triage                      # synthetic sample, safe to run anywhere
npm run triage -- path/to/real.json # real rows, see the boundary note
```

## Boundary note, read before pointing this at anything real

`data/items.sample.json` is synthetic. It is written to look like the real thing
without being the real thing, so the demo can be shown without a data decision
being made first.

Sending real client material to a third party model is the operator's call, not
this tool's. `zeroDataRetention: true` is set by default in `src/triage.ts` and
it is not a substitute for that decision. Client repositories are read-only;
this project deliberately lives outside them under a neutral name.
