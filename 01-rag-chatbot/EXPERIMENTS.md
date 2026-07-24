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

## Open experiments to run (once Phase 2 eval is live)

- **Chunk size:** 256 vs 512 (current) vs 1024 — compare faithfulness/precision.
- **Embedding model:** MiniLM (current) vs BGE-small/large vs OpenAI — quality
  vs cost vs privacy.
- **`similarity_top_k`:** how many chunks to retrieve per question (3 vs 4 vs 6).
