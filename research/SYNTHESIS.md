# jev: what 15 reviewers actually said, and what nobody has tested

Cross-video synthesis, 2026-09-23. Source: the 15 transcripts listed at the bottom, 4h 11m,
about 50,000 words, all published 2026-09-17 to 2026-09-21. The README in this repo is a demo
pitch; this file is the survey it was built on.

Three labels are used throughout, and the point of the file is to keep them apart:

- **MEASURED (ours)**: we ran it, in this repo, and the output is on disk.
- **REPORTED**: a reviewer says they ran it and shows a number. We have not reproduced it.
- **CLAIMED**: TypeSafe's own statement, or a reviewer repeating it without a run.

Transcripts are machine STT. "Jeff", "Jev" and "JE" are all the model; "null" and "nool" are
the boolean question type (spelled `noul` in the API); the open-model names are resolved in
section 6.

## 1. What everyone agrees on

Every one of the 15 describes the same interface, and none contradicts it:

- Input is a `state` (text or JSON) plus typed `questions`. Output is a distribution over the
  options you listed, never text.
- Three question types: **choice** (pick one of up to 255), **score** (ordered rubric, 2 to 10
  levels), **boolean** (the vendor calls it "null"; returns P(true)).
- Many questions against one state are answered together, in parallel, for roughly the cost
  and latency of one (LangChain VE5dsWll06M, Sam Witteveen ZR7anrL50xs, Syntax QbYBRjOaGOo).
- Price $0.042 per million input tokens, output free. Every reviewer quoting a price agrees.
- It is the wrong tool for anything that needs text written, a plan, or several steps of
  reasoning. Even the most enthusiastic reviewer (Nate B Jones, tYugqJ9YytQ) says it does not
  replace an LLM.

The consensus architecture is **cascade**: jev sorts or routes, code acts on the answer, an LLM
or a human handles what jev routes to them. Named as the pattern by Syntax, Nate B Jones,
RoboNuggets (tTnUcSj-QPA), AI Jason (o4Vi5uBZYH0), Nate Herk (ymgH8jS6Wb8).

## 2. Where the reviewers contradict each other

These are the useful part. Each is a place where believing the wrong reviewer changes a design.

**2.1 How much faster and cheaper.**
- CLAIMED: 20 to 200x faster, 40 to 400x cheaper; homepage 193.6x and 444.6x.
- Theo (F3YXg7AaKWE) read the vendor's own page: TypeSafe says those two numbers are "the
  higher end of real-world gains".
- REPORTED, the only like-for-like comparison against a cheap model: AI Jason, jev against GPT
  5.6 Luna, "quite consistently 5 to 7 times faster and 5 times cheaper".
- REPORTED against other baselines: Nate Herk, 1,000 emails x 7 questions, jev 70s and 9 cents
  serial (6s parallel) against Luna 5 min and 62 cents; he states it as "12 times the cost and 46
  times the time", though his own two figures give about 7x on cost. Nukkshot (via
  Nate B Jones), 34x cheaper, 6x faster, on tax documents. Hiring Cafe (via Syntax), 10x
  cheaper for resume fit.
- Reading: the headline multiples are measured against frontier models. **Against the small
  model you would actually have used for classification, the reported gain is 5 to 10x on
  cost**, which is still large but is a different business case.

**2.2 Context size.** Nate Herk says 64k input. Theo and AI Jason say 32k. Both are right:
32k for `state`, 64k for the whole request (AI Gateway docs, as recorded in the handover). Size
any design to 32k of state.

**2.3 Where it ranks on the vendor's accuracy chart.** Matthew Berman (2z-7pIj57f8), as
transcribed: "basically on par with Luna and Terra and Sonnet 5 above Opus 5, above Sol". Theo
reads the same chart as "the only models they measured that had better classification were Sol
and Opus V". On Opus 5 and Sol they appear to disagree, though Berman's line is ambiguous without
punctuation. Nobody quotes the numbers, and the benchmark is unpublished, so this stays open.

**2.4 What "accuracy" means on that chart.** This one matters most for the calibration
question. Per Theo's reading of the vendor page, the reference answers were **the average of
GPT 6 Astra and Fable 5.1**, not human labels. So the vendor's accuracy is agreement with two
frontier LLMs, and any calibration claim built on it is calibration against those LLMs, not
against ground truth. Treat every vendor accuracy figure as agreement, not correctness.

**2.5 "Cannot hallucinate".**
- Berman: "zero hallucinations", and suggests it for healthcare, military targeting, traffic.
- Theo and Sam Witteveen (X117w2Rark8): it means it cannot break the schema. It can still pick
  the wrong option.
- CLAIMED (vendor chart, via Theo): 0% structured-output and tool-call error rate, against
  45.5% for Haiku.
- Reading: the schema guarantee is real and useful. Berman's reading is wrong, and it is the
  reading most likely to reach a non-technical decision maker.

**2.6 Is it deterministic.** Sam Witteveen: "still a stochastic process, each time I ping it
I'm getting something slightly different". Theo: the shape is deterministic, the content is not.
- MEASURED (ours): the same row, run twice (`run.out` locally, `api.out` through the deployed
  function), moved owner confidence 0.75 to 0.84 and size confidence 0.03 to 0.14. Same answer
  both times, different numbers. So a threshold near the boundary will flip between runs.

**2.7 jev as an LLM judge.**
- For: LangChain, who report online-eval judging "much cheaper, much faster, but also much more
  reliable and consistent" than LLM-as-judge (their blog, not shown).
- Against: Theo, calling Braintrust's suggestion to replace LLM judges with jev a reason to
  distrust Braintrust: a model that cannot reason cannot choose between three LLM
  implementations.
- Reading: these are compatible if the rubric is closed and per-item ("does the answer cite a
  source", yes or no) and incompatible if the judgment is comparative. Rubric scoring, maybe;
  picking the best of several outputs, no.

**2.8 Can it extract values from the state.** Sam Witteveen: it picks which tool, it does not
extract the arguments. Syntax: their chatbot used "a piece of jev that can extract out from the
input state" (the city, Denver) and a way to "point to a specific line in the state". Unresolved.
Syntax may be using choice over candidates they generated, or the SDK may have a span feature
the other 14 did not use. Check the docs before designing around either.

## 3. Where it demonstrably fails (REPORTED)

Worth more than the successes, since every reviewer shows successes.

- **Judgment that needs reasons.** Theo asked it which of his own 1,118 chat threads were worth
  a video; after several prompt revisions it still said about half. Checkers: "I was barely
  paying attention and crushed it."
- **Anything needing memory across calls.** Doom play turns left and right on alternate frames
  because every call is stateless (Theo). If the decision depends on the last decision, the
  caller must put that history in `state`.
- **Markets.** Ryan Vogel's Bitcoin signal "does not seem to be doing well" (4mTLpuQpB80); Nate
  Herk's trader is "not doing very well" and fees exceed the model cost.
- **Chess.** Loses on the board to Fable, wins on the clock (Berman).
- **Context compaction.** Theo argues at length that compacting agent context with jev is
  wrong: compaction is synthesis, not filtering, jev never sees tool results or reasoning, and
  deleting early turns invalidates the prompt cache. No reviewer argues the other side with data.
- **Short inputs.** Sam Witteveen: confidence falls on two-word inputs and rises with length.

Common thread: it does well when a person could answer in under about 10 seconds once they have
read the input (Theo's rule of thumb), and badly when the answer needs thought.

## 4. How the API behaves, from demos rather than docs

- **Score returns the expected value.** LangChain's frustration score came back 1.035.
  MEASURED (ours): D-014's size score 2.84 against its distribution
  (0 x 0.10 + 1 x 0.08 + 2 x 0.09 + 3 x 0.36 + 4 x 0.37 = 2.82). A mean over a bimodal
  distribution can name a level nobody predicted, so read the distribution, not the score.
- **Confidence is not the top probability.** MEASURED (ours): owner top probability 0.81 with
  confidence 0.75; size top probability 0.37 with confidence 0.03. The gateway reports confidence
  for choice and score only.
- **Boolean confidence is ours, not the vendor's.** The gateway returns no confidence for a
  boolean. `src/lib.ts` maps `|p - 0.5| * 2` onto the same scale (commit c1b2a7c). So for
  booleans, calibration of the confidence is exactly calibration of `p`.
- **Instructions steer the answer.** AI Jason: "export button double-charged my card" routes to
  billing under "which team should handle this", and to technical under "route to whoever must
  fix the root cause". Criteria can carry examples, like few-shot prompting.
- **State variables can be referenced inside questions** (CoderOne kWToHpdxScE, quoting
  `"food"` from the state).

## 5. What was built with it, grouped by the pattern the fleet cares about

**Routers.** LangChain use it internally to switch coding agents between cheap and strong
models. Sam Witteveen built a local router: one call, three questions (lane as choice,
difficulty as score, "contains private data" as boolean), 331 ms on jev, 75% of 53 requests
answered by a local 2B model. Syntax replaced the prompt-based turn router in Sentry's Slack bot
with two jev questions. RoboNuggets: 12 prompts, 70% token saving against always using Fable,
because 9 of 12 did not need it. **Quality of the routed answers was not measured in any of
these.**

**Tool gates.** LangChain's "auto mode" middleware classifies tool calls as risky and blocks
them; the presenter had turned it off because the LLM classifier was too slow and turned it back
on with jev. Nate B Jones proposes the same for commands like force-push. Nobody reports a
false-negative rate, which is the only number that matters for a gate.

**Skill selection.** RoboNuggets: 145 skills, 14 tests, jev about 5s total against Opus 5 about
30s. Accuracy of the selection is not reported.

**Sam Witteveen's own caveat applies to every router above:** sending a prompt to TypeSafe to
ask whether it is private has already sent it. His fix is to run an open variant locally.

MEASURED (ours), research/CARD-HARNESS.md: routing, tool selection and an injection gate on public
labelled data. jev ranks better than the free baselines on routing and tool choice, and fails all
three frozen lines at a fixed threshold; the injection gate misses 26 of 60 at p 0.5. Tool selection
is the one clear win (0.743 top-1 over 199 tools, 0.94 accurate at confidence 0.95 and up).

## 6. Open variants (section 3 of the handover's plan)

As the videos reported them, with the real names resolved on 2026-09-25:

| name as transcribed | actually | who | what | quality note in the video |
|---|---|---|---|---|
| Leia | Laya (convaiinnovations/laya) | CoderOne | local, Apple silicon, 30 to 39 ms per decision | "a little less precise and accurate" than jev |
| Kev | Kev (jaredpalmer/kev) | CoderOne | "tiny jev-like family" on Qwen 3.5, 9B, 4B, 0.8B, open weights | none given |
| SEMIF | SemIf (TheoLeeCJ) | Sam Witteveen | local judge inside his router, 88 ms | "web jev better at generalization" |
| unnamed | Laya again (421M, ModernBERT-large) | Caleb (vj7hysh0mOI) | bidirectional BERT, 421M, on Reddit | none given |

Sam Witteveen uses "OpenJevs" as the collective name. All appeared within about five days of
launch. MEASURED (ours), research/CARD-OPEN.md: Laya and Kev-0.8B run on this box's CPU; on the
public tables they are at chance or at the majority rate, and on clean text they rank well below
jev. OpenJev (27B, closest reported accuracy) is CC BY-NC.

## 7. Nobody has tested calibration

MEASURED since (ours): research/CARD.md (tabular, all five frozen lines failed) and
research/CARD-HARNESS.md (harness uses, all three failed at a fixed threshold). What follows is the
state of the sources as written on 2026-09-23.

It is the whole value proposition and not one of 15 reviewers measured it. AI Jason goes
furthest: "you can finally trust the model to operate fully autonomously because every answer
comes with this confidence score". Nate Herk and Nate B Jones say to build a golden set and
test. Nobody did.

The test that settles it: a labelled set with known answers, bucket the stated confidence (or
`p` for booleans), and check whether the 0.9 bucket is right about 90% of the time. Given 2.4,
the labels must be human ground truth, not LLM agreement. Given 2.6, run each item at least
twice and report the spread, because a threshold only works if the number is stable enough to
threshold.

## 8. Conflicts of interest in the sources

Sponsor reads were stripped before the README was written (`data/removed-advertising.audit.txt`).
Beyond sponsors, several presenters sell something the video promotes: AI Jason's Track product
runs through his whole walkthrough; RoboNuggets and Nate Herk sell communities; LangChain ships
the integration they demo. Launch-day adoption figures (Nate B Jones: fastest-adopted model in
Vercel AI Gateway history, twice the paid teams of any launch in 24 hours) come from Vercel and
TypeSafe, not from a reviewer's run.

## Sources

| id | channel | published |
|---|---|---|
| 2Bs0Ink_-Uo | Rob Shocks | 2026-09-17 |
| QbYBRjOaGOo | Syntax | 2026-09-17 |
| 2z-7pIj57f8 | Matthew Berman | 2026-09-18 |
| X117w2Rark8 | Sam Witteveen | 2026-09-18 |
| 4mTLpuQpB80 | Greg Isenberg, with Ryan Vogel | 2026-09-18 |
| ymgH8jS6Wb8 | Nate Herk | 2026-09-19 |
| vj7hysh0mOI | Caleb Writes Code | 2026-09-19 |
| fMV6JKkQVfE | Zubair Trabzada | 2026-09-21 |
| tYugqJ9YytQ | Nate B Jones | 2026-09-21 |
| kWToHpdxScE | CoderOne | 2026-09-21 |
| VE5dsWll06M | LangChain | 2026-09-21 |
| tTnUcSj-QPA | RoboNuggets | 2026-09-21 |
| ZR7anrL50xs | Sam Witteveen | 2026-09-21 |
| o4Vi5uBZYH0 | AI Jason | 2026-09-21 |
| F3YXg7AaKWE | not in info.json; "Theo" is INFERRED from the transcript (T3 chats, soydev link) | not recorded |
