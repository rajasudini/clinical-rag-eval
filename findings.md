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
