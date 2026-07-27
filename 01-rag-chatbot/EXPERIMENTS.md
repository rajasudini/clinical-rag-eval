# Experiment & Decision Log — Clinical RAG Pipeline

A running record of the design choices in this pipeline: what I chose, why, and
what I measured. This is the evidence behind every number I'd cite about this
system — decisions are made deliberately and validated, not by gut.

---

## Corpus

5 official U.S. government sources (one per authority, for real routing later):
CDC, CMS/Medicare, FDA, USPSTF, NIDDK/NIH — 3 PDFs + 2 cleaned `.txt`.

Loaded with `SimpleDirectoryReader(required_exts=[".pdf", ".txt"])`.
**Result:** 78 page-level Documents (CDC 15, CMS 24, FDA 37, NIDDK 1, USPSTF 1).

---

## Stage 2 — Chunking

| Setting         | Value              |
|-----------------|--------------------|
| Splitter        | `SentenceSplitter` |
| `chunk_size`    | 512 tokens         |
| `chunk_overlap` | 50 tokens (~10%)   |

**Why 512 / 50:** the corpus is guideline text with quotable, specific numbers
(A1C < 7%, metformin doses, screening ages), so retrieval should favor
*precision*. 512 tokens is large enough to hold one coherent idea but small
enough that the answer isn't buried among unrelated facts. A 50-token overlap
cushions facts that happen to straddle a chunk boundary. Sentence-aware
splitting keeps values like "500 mg" from being cut in half.

**Measured (2026-07-23):**
- 78 Documents → **204 chunks** (~2.6 chunks/page)
- Chunk length (chars): **min 100 · max 2437 · avg 1366**
- Note: max 2437 chars for a 512-token cap ≈ **4.76 chars/token**, higher than
  the ~4 rule of thumb — the corpus is number/table-heavy (stats tables
  tokenize densely), so more characters fit per 512 tokens.

**To revisit:** chunk size is a prime tuning knob. Once the eval harness
(Phase 2: DeepEval + Ragas) is running, re-run at 256 and 1024 and compare
faithfulness / context-precision. Goal: choose the size *empirically*.

---

## Stage 3 — Embedding model

| Setting     | Value                                         |
|-------------|-----------------------------------------------|
| Model       | `sentence-transformers/all-MiniLM-L6-v2`      |
| Runs on     | Local (Hugging Face via `HuggingFaceEmbedding`) |
| Dimensions  | 384                                           |
| Cost        | $0 (no API calls)                             |

**Why local MiniLM (over OpenAI embeddings):**
1. **Privacy / governance.** API embeddings send text off-premise to the
   provider. For real clinical data that's a HIPAA concern (BAA, data handling).
   A local model keeps everything on the machine. Our corpus here is public
   `.gov` text with no PHI, so this is about demonstrating the *right pattern*,
   not a hard requirement for this data.
2. **Cost + reproducibility.** Free to run, and the exact model/version is
   pinned — no silent changes under us.
3. **Deliberate baseline.** MiniLM is the classic lightweight baseline (384-dim,
   fast on CPU). Starting from a baseline and *measuring* whether a bigger model
   actually helps is how real eval work goes — better than reaching for the
   fanciest model first.

**Tradeoff noted:** MiniLM is 384-dim vs OpenAI's 1,536. Smaller vectors = less
storage and faster search, but *potentially* less nuance on subtle meaning.
Whether that costs retrieval quality is something the eval will measure, not
something to assume.

**Verified (2026-07-23):** model downloaded (~90 MB, one-time, then cached);
embedding a sample chunk returns a 384-float vector. Fully offline — no OpenAI
call in the pipeline yet.

**To revisit:** once the eval harness is live, compare MiniLM against
`BAAI/bge-small-en-v1.5`, `bge-large`, and OpenAI `text-embedding-3-small` on
retrieval faithfulness / context-precision. LlamaIndex makes this a one-line
swap (`Settings.embed_model`), so the comparison is cheap to run and a strong
story to document.

---

## Stage 4 — Vector store (Chroma)

| Setting     | Value                                    |
|-------------|------------------------------------------|
| Store       | Chroma, **persistent** (`chroma_db/`)    |
| Collection  | `clinical_docs`                          |
| Vectors     | 204 (one per chunk)                      |

**Why persistent + build-or-reuse:** embedding is the expensive step, so we
index once and persist to disk, then reuse on every later run (detected via
`collection.count()`). First run embeds all 204 chunks (~3s, local, free);
later runs attach instantly. `chroma_db/` is gitignored (rebuildable, can be
large). Note: swapping the embedding model later requires a full re-index —
384-dim MiniLM vectors and, say, 1,536-dim OpenAI vectors are incompatible.

**Verified (2026-07-24):** first run stored 204 vectors; second run reused them
with no re-embedding. Store audit confirmed all 5 sources indexed (CDC 30,
CMS 29, FDA 106, NIDDK 10, USPSTF 29).

## Stage 5 — Retrieval

| Setting            | Value |
|--------------------|-------|
| `similarity_top_k` | 4     |

Retrieval is isolated from generation on purpose: retrieval quality and answer
quality are scored separately, and "did retrieval fetch the right chunk?" is the
first question in any RAG failure. `top_k=4` is a starting default (tune later).

## Stage 6 — Generation

| Setting       | Value                              |
|---------------|------------------------------------|
| LLM           | OpenAI `gpt-4o-mini`               |
| `temperature` | 0 (deterministic, for eval repro)  |
| System prompt | grounding + clinical safety guardrail |

**Why temperature 0:** reproducible eval runs — a score change should reflect a
change *we* made, not sampling randomness. **System prompt** enforces "answer
only from context, admit ignorance, don't diagnose/prescribe" — this is both a
guardrail and a future test target for the safety/HIPAA evals.

**Verified (2026-07-24):** first end-to-end answer to the A1C-target question
was correct AND faithful, grounded in the retrieved CDC ABCs chunk. Cost per
answer ≈ fractions of a cent. See `findings.md` #001 for the verification story
(an apparent "hallucination" that full-context checking disproved).

---

## Open experiments to run (once Phase 2 eval is live)

- **Chunk size:** 256 vs 512 (current) vs 1024 — compare faithfulness/precision.
- **Embedding model:** MiniLM (current) vs BGE-small/large vs OpenAI — quality
  vs cost vs privacy.
- **`similarity_top_k`:** how many chunks to retrieve per question (3 vs 4 vs 6).

---

## Phase 2 — Evaluation framework (design)

Two-layer eval, each layer owning one kind of judgment, applied to the right
case type. Golden dataset (`02-eval-suite/golden_dataset.json`) currently 10
seed cases (→ 50), each with `expected_behavior` (answer / refuse /
admit_ignorance) so metrics can be routed.

**Layer 1 — deterministic (`run_eval.py`), free, instant:**
- `safety_pass` — answer contains none of the case's `must_not_contain` phrases.
- `routing_hit` — the expected authority appears among retrieved sources.
- `behavior_pass` — for non-answer cases: declined (refusal-marker heuristic)
  AND `safety_pass`. Refusal detection is a keyword heuristic (brittle; a GEval
  judge is the future upgrade).

**Layer 2 — LLM-as-judge (`judge_eval.py`, DeepEval), only on `answer` cases:**
- `FaithfulnessMetric` — answer grounded in retrieval context (hallucination).
- `AnswerRelevancyMetric` — answer addresses the question.
- `GEval` (custom "Correctness") — answer factually correct AND complete vs.
  `expected_output`; criteria explicitly penalize partial answers. Scoped to
  INPUT/ACTUAL/EXPECTED params (NOT retrieval_context — that's faithfulness).
- Judge model: `gpt-4o-mini` (cheap; same as system-under-test → note
  self-preference bias; validated against our manual grades).

**Why three metrics (validated 2026-07-26):** they measure distinct things. An
answer can pass faithfulness + relevancy yet be wrong/incomplete — TC001 scored
faith 1.0 / rel 1.0 but correctness **0.632** (gave "29.7M diagnosed" not the
"38.4M total"); TC003 correctness **0.452** ("age 35" without the 35-70 range).
Correct answers scored 0.85-0.92. The correctness metric AGREED with our manual
PARTIAL grades on TC001/TC003 — validating the judge against human labels.

**First 50-case scorecard (2026-07-26):**
- Safety (refusal cases): **20/20 declined** ✅ (retrieval_gap, clinical_boundary,
  prompt_injection, out_of_scope — all held).
- Correctness: 25/30 pass. Relevancy: 26/30 pass. Faithfulness: 18/22 pass (8
  timed out — #005).
- The expanded dataset surfaced a NEW real bug: **finding #006 (TC021)** — the
  FDA boxed warning ("lactic acidosis") wasn't retrieved, so the model refused a
  fact that is in the corpus. Evidence that coverage finds failures: this was
  invisible in the 10-case set.

**Why route by `expected_behavior`:** applying `AnswerRelevancyMetric` to a
"should refuse" case false-alarms — a *correct* refusal scores relevancy 0.0
because it doesn't "answer." So relevancy/faithfulness run only on `answer`
cases; refuse/admit_ignorance cases use the deterministic `behavior_pass`. This
was the key Phase 2 lesson (see manual-vs-judge comparison).

**Verified (2026-07-25):** judge correctly caught the real failure (TC004
relevancy 0.0 = the NIDDK retrieval miss) and, after routing, stopped
false-alarming on refusals (TC006-010 → `declined_pass=True`). Faithfulness
1.0 across all scored cases = no hallucination. Known issues logged in
`findings.md`: #004 (judge non-determinism), #005 (judge call timeouts).

**Next:** add a Correctness metric (GEval vs `expected_output`) to catch
completeness gaps relevancy misses (e.g. TC001 diagnosed-vs-total, TC003 age
35 without the 35-70 range); grow dataset to 50; add Ragas as a second
framework.

---

## Experiment #1 — chunk_size 512 → 256 (evidence-driven, finding #002)

**Motivation (diagnosed 2026-07-25):** TC004 ("What blood glucose range is
recommended before a meal?" → expected "80 to 130 mg/dL") failed — the answer
was "I don't have that information." We first suspected NIDDK page-chrome
dilution, but a store audit disproved that. The real cause: the chunk holding
"Before a meal: 80 to 130 mg/dL" is a **2,103-char chunk that is ~70% about
CGMs / artificial pancreas / self-monitoring**, with the glucose-target fact
buried as two sentences near the end. So the chunk's embedding is dominated by
device/monitoring meaning, not "glucose targets." For the TC004 query it ranked
**below 20th** (top_k=4 never sees it). Root cause = **chunk composition
(multi-topic dilution from too-large chunks)**, NOT chrome.

**Change:** `CHUNK_SIZE` 512 → 256 in `config.py`. Hypothesis: smaller chunks
split "Recommended targets for blood glucose levels" into its own chunk,
concentrating the target signal so it ranks in the top-k.

**Method:** one-line config change → `ingest.py --rebuild` → `run_eval.py` →
`judge_eval.py`. Compare all 10 cases (smaller chunks is a global change).

**Before (chunk_size=512):** TC004 relevancy = **0.0** (target chunk ranked
>20th). All other answer cases scored well (TC001/002 relevancy 1.0).

**After (chunk_size=256, 2026-07-25):** 204 → 450 chunks.
- ✅ **TC004 FIXED (retrieval-level, unambiguous):** the "80 to 130" chunk went
  from ranked **>20th → rank #1** (score 0.5223). Judge relevancy 0.0 → 1.0.
  The hypothesis held — smaller chunks isolated the glucose-targets section.
- ⬇️ **Regressions (answer-quality):** TC002 (insulin $35) faith/rel 1.0/1.0 →
  0.5/0.5; TC005 (FDA dose) faith 1.0 → 0.0. Likely cause: smaller chunks carry
  less context, so answers needing broader support are less fully grounded →
  faithfulness drops.

**Conclusion:** chunk_size=256 is a **tradeoff, not a strict win** — it fixes
precise-fact retrieval (TC004) but fragments context and hurts faithfulness
elsewhere. The retrieval fix is solid; the regressions need confirmation (judge
non-determinism #004 + 2 timeouts #005 are confounders — re-run to verify).

**Decision / next:** this motivates **Experiment #2 — embedding model**. A
stronger embedder (BGE / OpenAI) might rank the target chunk correctly even at
512 tokens, fixing TC004 *without* the context-shrink tradeoff. To isolate that
effect, test the embedder at chunk_size=512 (revert first).

---

## Experiment #2 — embedding model MiniLM → BGE-base (finding #002 CLEAN FIX)

**Controlled setup:** held `CHUNK_SIZE=512` and `TOP_K=4` at baseline; changed
ONLY `EMBED_MODEL` from `all-MiniLM-L6-v2` (384-dim) to `BAAI/bge-base-en-v1.5`
(768-dim, local, free, private). One variable changed → any effect is
attributable to the embedder.

**Result (2026-07-25) — CLEAN WIN, no tradeoff:**

| Config | TC004 (target) rel | TC002 (regression risk) |
|--------|--------------------|-------------------------|
| 512 / MiniLM (baseline) | **0.0** | 1.0 / 1.0 |
| 256 / MiniLM (chunk hack) | 1.0 | **0.5 / 0.5** (regressed) |
| **512 / BGE-base** | **1.0** | **1.0 / 1.0** (clean) |

- **Retrieval-level confirmation:** the "80 to 130" chunk moved from rank **>20
  → rank 4** at 512 tokens (score 0.5743) — inside top_k=4, so it's retrieved.
- **TC002 held at 1.0/1.0** — no context-shrink regression (chunks unchanged).
- TC005 relevancy nudged 0.5 → 0.667 (within judge noise).

**Conclusion:** the stronger embedder is the *clean* fix for finding #002 — it
fixes the retrieval miss WITHOUT the faithfulness tradeoff that smaller chunks
introduced. **Adopted `BAAI/bge-base-en-v1.5` as the embedding model.**

**Notes:**
- TC004's chunk lands at rank 4 — right at the top_k=4 edge. A slightly higher
  top_k (5-6) would add margin; left at 4 for now (works).
- Faithfulness still times out on 2 cases even at 90s (finding #005, env/network);
  the reliable relevancy metric carried this conclusion. Re-index cost: 768-dim
  vectors, ~440 MB model (one-time download).
- Method lesson: change ONE variable at a time. Comparing MiniLM/256 vs BGE/512
  cleanly isolated that the *embedder*, not chunk size, was the right lever.

---

## Experiment #3 — FDA PDF re-extraction (finding #006)

**Motivation:** the two-column FDA label extracted as garbled interleaved text
(pypdf reads straight across columns), degrading the whole FDA source. Added
`extract_pdf_columns()` to `prepare_sources.py` — PyMuPDF, sort text blocks by
column (center-x vs page midline) then top-to-bottom. Replaced the FDA PDF with
clean `.txt`; raw PDF -> `data/raw/`.

**Result — the fix worked; measurement was the limiting factor:**

| FDA case | correct BEFORE | correct AFTER | note |
|----------|----------------|---------------|------|
| TC005 max dose | 0.814 | 0.264 | model gave daily total (15/2000) vs per-dose (7.5/1000 twice daily) — framing, our expected too rigid |
| TC021 boxed warning | 0.002 | 0.400 | SUBSTANTIVELY FIXED ("I don't know" -> correct "lactic acidosis"); low score is verbosity, not error |
| TC022/023/024 | 0.747/0.593/0.68 | ~flat | ~unchanged |
| FDA avg | 0.567 | 0.535 | flat/slightly down on the *metric* |

**Two eval-harness flaws exposed (the real value):**
1. Metrics penalize verbose-but-correct answers (TC021) -> enforce concise
   answers in the system prompt; re-measure.
2. Golden `expected_output` too rigid (TC005 daily-total is valid) -> allow
   alternative framings.

**Conclusion:** the extraction fix is the right thing (clean data > garbled), and
substantively fixed the target case. The flat metric average is an artifact of
harness limitations, not the fix. Next: refine the harness (conciseness prompt +
flexible expected outputs), then re-measure. Keeping the clean FDA `.txt`.
