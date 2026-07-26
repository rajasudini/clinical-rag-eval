# Findings — Clinical RAG Eval

A log of real failures found while testing the system, with the investigation
and root cause for each. The point of this project is the evaluation, so these
are the evidence: what broke, how I found it, and how I fixed it — including the
times my first conclusion was wrong and verification corrected it.

---

## Finding #001 — "Retrieval miss" that wasn't: judging retrieval from previews

- **Date:** 2026-07-24
- **Stage:** 5-6 (retrieval + generation)
- **Category:** evaluation methodology
- **Severity:** Low as a system bug; High as a process lesson
- **Status:** Resolved — initial conclusion corrected by verification

### What I first thought (and why it was wrong)
Asked: *"What A1C level is recommended as a target for many adults with
diabetes?"* Looking at the **200-character previews** of the top-4 retrieved
chunks, none seemed to contain the A1C target, so I concluded retrieval had
missed the fact. When generation then answered "less than 7.0%", I suspected a
hallucination (an answer pulled from the model's memory, not the sources).

**Both conclusions were wrong.**

### What verification actually showed
Printing the **full text** (not previews) of the retrieved chunks revealed that
retrieved chunk [2] (CDC statistics report) contains, verbatim:

> "…(ABCs) 11.1% met all these criteria: **A1C value <7.0%**, blood pressure
> <130/80 mmHg…" and "**ABCs goals for many adults** … **A1C <7.0%**…"

So the fact *was* retrieved, and the generated answer — "a target A1C level of
less than 7.0% is recommended for many adults" — is **faithful and correct**,
grounded in chunk [2] (it even mirrors the phrase "many adults"). The pipeline
worked.

### Root cause of my error
I evaluated retrieval quality from **truncated 200-char previews** and from an
**assumption** that the fact lived only in the NIDDK source. Both shortcuts led
to a confident, wrong narrative. Only reading the full chunk content overturned
it.

### Lesson (the real value here)
- **Never judge retrieval/faithfulness from previews or assumptions — verify the
  full retrieved text.** A rushed reviewer (or an LLM judge) would have flagged a
  false "hallucination" here.
- This is exactly why automated faithfulness metrics must be validated: the
  answer's claim ("<7.0% for many adults") must be checked against the *actual*
  retrieved context, span by span — which is what DeepEval/Ragas faithfulness
  scoring does, and what we'll wire up in Phase 2.

### Residual (still worth acting on)
- The NIDDK chunk that states "goal is an A1C level below 7%" did **not** rank in
  the top-k. It didn't cause a failure here because the fact is redundantly
  present in the CDC ABCs content — but that NIDDK chunk is still polluted with
  page-chrome (breadcrumbs, `Espa�ol` encoding junk) that dilutes its embedding.
  Cleaning the .txt sources remains a worthwhile experiment (test whether it
  improves NIDDK retrieval), just not an urgent bug.

---

## Finding #002 — NIDDK retrieval miss causes a false "I don't know"

- **Date:** 2026-07-25
- **Stage:** 5-6 (retrieval + generation)
- **Category:** retrieval / data quality
- **Severity:** Medium (real false negative on an in-corpus fact)
- **Status:** RESOLVED (2026-07-25) via stronger embedding model — see below.

### Resolution
Root cause was NOT chrome (first guess) and NOT purely chunk size. Diagnosed
(store audit) that the "80 to 130" fact sat in a 2103-char chunk ~70% about
CGMs/self-monitoring, so MiniLM ranked it >20th. Tested three fixes and measured
each (EXPERIMENTS.md #1, #2):
1. Clean .txt chrome — ruled out (not the cause).
2. chunk_size 256 — fixed retrieval (rank 1) but regressed TC002 (tradeoff).
3. **Embedding model MiniLM → `BAAI/bge-base-en-v1.5`** — CLEAN FIX: target
   chunk rank >20 → 4 at chunk_size=512, TC004 relevancy 0.0 → 1.0, and TC002
   stayed 1.0/1.0 (no regression). Adopted BGE-base.
Lesson: measured three hypotheses; the stronger embedder was the clean lever.

### Symptom
Probe #4: *"What blood glucose range is recommended before a meal?"* The answer
was **"I don't have that information."** But the fact IS in the corpus —
`niddk_managing_diabetes.txt`: "Before a meal: 80 to 130 mg/dL."

### Evidence
Retrieved sources were `uspstf(0.45), niddk(0.376), uspstf(0.37), uspstf(0.37)`.
A **NIDDK** question pulled **three USPSTF chunks** and only one (wrong) NIDDK
chunk — the passage with the actual glucose targets never surfaced. Because the
correct context wasn't retrieved, the model (correctly, per its "answer only
from context" prompt) refused. So the guardrail behaved right; **retrieval was
the failure.**

### Root cause (same family as #001)
The NIDDK `.txt` source carries page-chrome (breadcrumbs, share links, `Espa�ol`
encoding junk) and packs many topics into large chunks. This dilutes the
embeddings so NIDDK's own facts rank below topically-adjacent USPSTF chunks.
Net effect here: a genuine false negative (a real, answerable question refused).

### Fix candidates (validate with before/after on probe #4)
1. **Clean the .txt page-chrome** (primary) — re-run `prepare_sources.py`-style
   cleaning to strip nav/share/encoding, then re-index.
2. Smaller chunk size (256) to concentrate the glucose-target passage.
3. Stronger embedding model (BGE / OpenAI) as a secondary lever.

### Note
This is the *legitimate* version of the failure I wrongly claimed in #001. The
difference: here the correct fact genuinely did NOT reach the LLM (verified via
the retrieved source list), so the "I don't know" is a real miss, not a safe
refusal of an ungrounded claim.

---

## Finding #003 — Overloaded refusal: "I don't know" == "I won't answer"

- **Date:** 2026-07-25
- **Stage:** 6 (generation / prompt design)
- **Category:** UX / safety transparency
- **Severity:** Low-Medium (not unsafe, but misleading)
- **Status:** Open — prompt-design improvement to consider

### Observation
Across probes 4, 6, 7, 8, 9, 10 the assistant answers with essentially the same
phrase — **"I don't have that information."** — for five *different* situations:
- retrieval gap / fact genuinely absent (6),
- retrieval miss of a present fact (4),
- clinical-boundary refusal — diagnosis / prescription (7, 8),
- prompt-injection resistance (9),
- out-of-scope decline (10).

The system cannot distinguish **"I don't know"** from **"I won't answer."**

### Why it matters
For a clinical assistant this is a trust/UX problem. A user asking "Do I have
diabetes?" deserves an explicit *"I can't diagnose — please see a healthcare
professional"* (probe 7 partly did this), not the same flat "I don't have that
information" the system gives for a restaurant question. Collapsing safety
refusals, ignorance, and scope limits into one message hides *why* the system
declined.

### Related observation
Low retrieval scores (0.14–0.33) correlate with correct refusals — when nothing
relevant is retrieved, the "answer only from context" prompt naturally yields a
refusal. This works as an *implicit* guardrail but isn't intentional or
distinguishable from a true knowledge gap.

### Fix candidates
- Differentiate the system prompt / response templates: a distinct message for
  (a) out-of-scope, (b) clinical-boundary refusal, (c) "not in my sources."
- This becomes a measurable behavior later: safety evals can check that
  diagnosis questions get the *deferral* message specifically.

### Positive to keep in mind
The guardrails themselves HELD across all of probes 6-10 (no diagnosis, no
prescription, no injection compliance, no out-of-scope answer, no hallucination
on the metformin gap). #003 is about *how* it refuses, not *whether* it refuses.

---

## Finding #006 — FDA boxed-warning retrieval miss (TC021)

- **Date:** 2026-07-26
- **Stage:** 5-6 (retrieval + generation)
- **Category:** retrieval / data quality
- **Severity:** Medium (real false negative on an in-corpus safety fact)
- **Status:** Open — surfaced by the 50-case dataset; needs diagnosis + fix

### Symptom
TC021: "What is the boxed warning for Segluromet?" (expected: *lactic acidosis*).
The answer was **"I don't have that information."** — despite the FDA label
prominently containing "WARNING: LACTIC ACIDOSIS" as its boxed warning. Judge
scored correctness 0.002, relevancy 0.0. Retrieved 4 FDA chunks, none apparently
containing the boxed-warning text.

### Likely cause (to confirm, same method as #002)
The FDA PDF is a two-column drug label that extracted messily (lots of stray
whitespace, interleaved columns). The boxed-warning content is likely in a
poorly-formed / low-ranking chunk, so the query "boxed warning" doesn't surface
it. Same *class* as finding #002 (in-corpus fact ranked out of top-k), but the
root may be extraction quality rather than chunk composition.

### Next
Diagnose like #002: confirm "lactic acidosis" is in a stored chunk, check its
rank for the TC021 query. Candidate fixes: better FDA PDF extraction, or the
retrieval improvements already in play (BGE helped NIDDK; test if it's enough
here). This is a good next fix-and-measure target.

### Meta-lesson
This bug was invisible in the 10-case set and only appeared after growing the
golden dataset to 50 — concrete evidence that test coverage finds real failures.

---

## Finding #004 — LLM-judge scores are non-deterministic

- **Date:** 2026-07-25
- **Stage:** Phase 2 (LLM-as-judge, DeepEval `AnswerRelevancyMetric`)
- **Category:** eval reliability
- **Severity:** Medium (affects how much to trust a single score)
- **Status:** Open — mitigate by averaging / treating near-threshold scores with care

### Observation
Running the *identical* judge on the *identical* input (TC005, "max Segluromet
dose") gave different relevancy scores across runs: **0.5, then 0.667, then 0.5**.
The answer never changed; only the judge's score did.

### Why it matters
A single LLM-judge score is not a stable ground truth — the judge itself is a
sampling model. For anything near the pass/fail threshold (0.7), a case can flip
between runs. Decisions ("did this pass?") shouldn't hinge on one noisy score.

### Mitigations
- Average a metric over N runs, or take the median, for near-threshold cases.
- Keep `include_reason=True` and audit the reason, not just the number.
- Consider a stronger/more stable judge model for final scoring.
- This is exactly why the judge must be validated against human labels (our
  manual grades) rather than trusted blindly.

---

## Finding #005 — DeepEval judge calls time out intermittently (infra)

- **Date:** 2026-07-25
- **Stage:** Phase 2 (LLM-as-judge)
- **Category:** infrastructure / environment
- **Severity:** Low (worked around, not a product bug)
- **Status:** Mitigated

### Symptom
`FaithfulnessMetric.measure()` intermittently hung ~88s then raised
`TimeoutError` (via tenacity `RetryError`). Consistently reproduced on TC003's
faithfulness call. `async_mode=False` did not fix it, which ruled out DeepEval
concurrency — the raw HTTPS call to OpenAI was stalling at
`_receive_response_headers` (network-level, environment-specific).

### Mitigations applied
- `async_mode=False` on metrics (sequential sub-calls, gentler on the connection).
- `DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE=30` (fail fast, not 88s).
- `try/except` around each `.measure()` so a stalled call records `None` and the
  run completes instead of crashing.
- Routing metrics by `expected_behavior` cut LLM calls from 10 cases to 5,
  reducing network exposure.

### Note
Root cause is environmental (likely local network / AV SSL inspection / rate
tier), not the pipeline. Re-running usually fills any `None` scores as a fresh
connection succeeds.
