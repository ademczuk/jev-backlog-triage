# jev inside an agent harness: calibration card, 2026-09-25

Protocol: research/PROTOCOL-HARNESS.md, SHA-256 35d1f27532ebc608af8fdf4bd2edee3461c59c48599af5c4b56a1a7eada7f154,
frozen 2026-09-25T20:03:47Z and sent (msg/1790366639750-tide-jev-harness-protocol-frozen) before any
jev call on these sets. Re-verified unchanged before scoring. Model typesafe-ai/jev through Vercel AI
Gateway, fleet-team key, zero data retention, serial calls. Public data only. Spend about 12 cents.

## Verdict: all three FAIL their frozen lines, and they fail in the same way.

jev ranks well on all three. On every one, the number a harness would act on at a fixed threshold
is where it falls short. Picking a better threshold takes labelled data, and wherever labels exist a
free baseline matches or beats jev. The exception is choosing among many tools with no labels, where
jev is clearly the best thing tested and misses its line by a hair.

| test | what a harness uses it for | frozen lines | result |
|---|---|---|---|
| T1 routing | send easy prompts to the cheap model | AUC 0.65; +3 pts over random at 50/50; within 0.02 of best baseline | FAIL (R2) |
| T2 tool selection | pick one of 199 tools | top-1 0.70; half auto-routable at 5% error; beat zero-shot TF-IDF | FAIL (S2, narrowly) |
| T3 injection gate | block text that tries to redirect the agent | at most 6 of 60 missed and 6 of 56 false alarms at p 0.5; AUC within 0.02 of baseline | FAIL (G1) |

## T1. Model routing, RouterBench, 499 prompts (1 call failed)

Cheap gpt-3.5-turbo-1106 was right on 66.5%, strong gpt-4-1106-preview on 85.6%.

| router | AUC | accuracy with 50% sent cheap | cost of 499 prompts |
|---|---|---|---|
| random (expected) | 0.500 | 0.761 | |
| B1: route by task family, from 26k labelled rows | 0.615 | **0.787** | $0.369 |
| B2: TF-IDF + logistic regression, same rows | 0.657 | 0.781 | $0.386 |
| jev, zero-shot | **0.679** | 0.778 | $0.421 |
| always strong | | 0.856 | $0.630 |
| oracle | | 0.898 | $0.269 |

- R1 PASS (0.679), R3 PASS (0.679 against 0.657), **R2 FAIL**: 0.778 against the 0.791 line, +1.7
  points over random. The router that just knows the task family does better at the 50/50 split,
  cheaper.
- jev ranks difficulty slightly better than either baseline (best AUC in the table) and is best at
  75% sent cheap (0.735 against 0.723 for B1). The gain it buys is small at any split.
- Its probabilities are optimistic: mean P(small model is enough) 0.827 against a true 0.665, ECE_sweep
  0.162, Brier skill -0.050. A threshold like "route cheap above 0.8" would send most prompts cheap.
- By family, AUC: ARC 0.70, MMLU 0.67, Winogrande 0.63, **HellaSwag 0.53** (chance).
- Limit, stated in the protocol: these are 2023 models, and RouterBench's zero-shot parse is broken
  for several of them. The result says jev does not know which prompts a weaker model will miss; it
  does not measure a Haiku to Opus routing directly.

## T2. Tool selection, MetaTool, 389 queries over 199 tools (9 calls failed)

| selector | top-1 | top-3 |
|---|---|---|
| Z1: TF-IDF cosine against tool descriptions, zero-shot | 0.468 | |
| Z1': same with the tool name added (descriptive) | 0.512 | |
| Z2: TF-IDF + logistic regression trained on 20,152 labelled queries (descriptive) | 0.620 | |
| jev, zero-shot | **0.743** | **0.887** |

- S1 PASS, S3 PASS, **S2 FAIL**: accepting answers in descending confidence, 48.8% of queries can be
  auto-routed at 5% error or less, against a line of 50%.
- Confidence is informative here: accuracy 0.27 below 0.5 confidence (n 48), 0.57 at 0.5 to 0.8
  (72), 0.67 at 0.8 to 0.95 (70), **0.94 at 0.95 and up (199)**. So "accept at 0.95, escalate the rest"
  handles half the traffic at about 6% error.
- jev beats even the baseline trained on 20,000 labelled queries. This is the one place in either
  card where jev clearly wins against everything free.
- Reliability cost: each call carries about 6,700 input tokens (199 descriptions), and **64 of 398
  calls (16%) failed on the first pass**, 9 still failing after a retry, against 5% on the short
  routing calls. A harness calling this per turn needs a fallback.
- This is not the operator's own skill list; MetaTool's queries were generated per tool by an LLM,
  so they are cleaner than real requests.

## T3. Prompt-injection gate, deepset test split, 115 rows (1 call failed)

| gate | AUC | missed injections at p 0.5 | false alarms at p 0.5 | missed at 3 false alarms |
|---|---|---|---|---|
| G-B: char n-gram TF-IDF + LR on 546 labelled rows | 0.975 | 23 of 60 | 0 of 55 | 8 of 60 |
| jev, zero-shot | 0.966 | **26 of 60** | 0 of 55 | 6 of 60 |

- G2 PASS, **G1 FAIL**: at the natural threshold jev misses 43% of injections. It never raises a false
  alarm, so the whole error is on the side a gate cannot afford.
- Moving the threshold fixes most of it (6 misses at 3 false alarms), but choosing that threshold
  needs labelled data, and the baseline trained on that same small set is as good.
- German rows (heuristic split, 44): AUC 0.988, 10 of 23 missed. Other rows (71): AUC 0.952, 16 of
  37 missed. Language is not the problem; the threshold is.
- Read with the tabular card: there, one injected sentence flipped 12 of jev's 35 churn calls. jev
  both under-detects injections at 0.5 and can be steered by one.

## What this licenses

- It licenses: "zero-shot, jev is a better ranker than the free baselines we tried for routing and
  tool choice, and its confidence is informative for tool choice. At a fixed threshold, as the
  escalate-below-confidence design uses it, it failed all three tests, and the gate misses 43% of
  injections at 0.5."
- If one of these goes forward, it is **tool or skill selection**, accepting at confidence 0.95 and
  escalating the rest, with a fallback for failed calls, measured first on the operator's real skill
  list. That measurement needs internal data, so whether to run it is the operator's call.
- It does NOT license jev as a security gate, or as a model router on the strength of cost savings
  alone: the savings in the videos were never paired with the accuracy they cost, and here the
  accuracy cost at the 50/50 split is 7.8 points against always-strong, more than routing by task
  family (6.9).

## Method notes

- Ties in P(true) are frequent (two decimals). Routed accuracy splits tied rows across the cut in
  expectation, so coarse scores are not favored or penalized by tie order.
- Coverage at 5% error takes whole tie groups only.
- Code: research/prep_harness.py (sampling; RouterBench prompts are not committed, its license is
  unstated), research/calibrate.ts (sets routing, tools, injection), research/analyze_harness.py.
