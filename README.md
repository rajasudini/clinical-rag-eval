# clinical-rag-eval

A diabetes question-answering system (RAG over official `.gov` health sources),
wrapped in a multi-layer evaluation framework. The retrieval-and-answer part is
fairly standard; the focus is everything around it — checking whether the answers
are faithful and correct, scanning for HIPAA/PHI problems, and trying to break it
with adversarial prompts.

To be clear on scope: it's **single-turn** — one question in, one grounded answer
out. No chat UI or conversation memory. That's intentional: keeping each answer
independent makes it cleanly measurable, so the depth went into the evaluation
rather than a chat interface. (Multi-turn is a natural extension — and it makes
evaluation meaningfully harder, which is a project of its own.)

## What the numbers look like

| Layer | Result |
|---|---|
| Answer correctness (GEval vs. a reference answer) | 23/30 answer cases |
| Answer relevancy (DeepEval) | 26/30 |
| Correct refusals (boundary / injection / out-of-scope) | 20/20 |
| HIPAA — no PHI, no clinical-boundary violations | 50/50 responses |
| Adversarial red-team (jailbreaks, injection, PHI extraction, …) | 20/20 attacks defended |

There's a small Streamlit dashboard that shows all of it:
`streamlit run 06-dashboard/app.py`.

## How it's laid out

- **`01-rag-chatbot/`** — the actual pipeline: load → chunk → embed → store →
  retrieve → generate. LlamaIndex + Chroma + local BGE embeddings + `gpt-4o-mini`.
  I split the one-time index build (`ingest.py`) from the query path
  (`rag_pipeline.py`) and kept shared settings in `config.py`.
- **`02-eval-suite/`** — a 50-case golden dataset and the evaluator. It runs in two
  layers: cheap deterministic checks (safety, routing, refusal) in `run_eval.py`,
  and LLM-as-judge metrics (faithfulness, relevancy, and a custom correctness
  metric) in `judge_eval.py`.
- **`03-hipaa-compliance/`** — a custom HIPAA metric that combines PHI detection
  (Microsoft Presidio) with a rule-based check for diagnosis/prescription language.
- **`04-safety/`** — 20 adversarial attacks and a runner that scores how the
  assistant defends against them.
- **`06-dashboard/`** — the Streamlit dashboard.

## Failures worth writing down

Most of the real work was finding failures and figuring them out:

- A fact that was definitely in the sources wasn't showing up in retrieval. My
  first guess at the cause was wrong (I'd blamed messy text; it was actually how
  the chunk was composed). I tried three fixes and measured each — smaller chunks
  helped the target case but hurt another one, and switching the embedding model
  turned out to be the clean fix.
- I didn't take the tools at face value. Presidio's default setup quietly missed
  standard-format SSNs, so I added my own recognizer. It also kept flagging dates
  and public phone numbers as "PHI" in normal answers, so I narrowed what it looks
  for.
- Re-extracting a badly-parsed FDA label made the answer visibly better, but the
  metric score barely moved — which pointed back at the evaluation itself: the
  correctness metric was punishing long answers, and the reference answers were
  too strict.

These are written up in [`findings.md`](findings.md) (8 of them, including a couple
that turned out to be wrong on first pass and were corrected) and in
[`01-rag-chatbot/EXPERIMENTS.md`](01-rag-chatbot/EXPERIMENTS.md) with the actual
before/after numbers.

## Sources (official `.gov` only — no patient data)

CDC, CMS/Medicare, FDA, USPSTF, and NIDDK/NIH documents on diabetes. There's a
rundown of what each one covers in
[`01-rag-chatbot/CORPUS_MAP.md`](01-rag-chatbot/CORPUS_MAP.md).

## Running it

Run these in order (each step past the first assumes the index is built, and the
HIPAA scan reads whatever `run_eval` produced last):

```bash
python 01-rag-chatbot/src/ingest.py --rebuild   # 1. build the vector index (once)
pytest 02-eval-suite/test_metadata.py           # 2. metadata integrity checks (offline)
python 02-eval-suite/run_eval.py                # 3. answers + deterministic checks
python 02-eval-suite/judge_eval.py              # 4. LLM-judge metrics (slow; needs an OpenAI key)
python 03-hipaa-compliance/run_hipaa.py         # 5. HIPAA scan (reads step 3's output)
python 04-safety/run_redteam.py                 # 6. adversarial red-team
streamlit run 06-dashboard/app.py               # 7. dashboard
```

You'll need an `OPENAI_API_KEY` in a `.env` file (see `.env.example`) for the
generation and LLM-judge steps. Dependencies are in the per-folder
`requirements.txt` files.

## Stack

LlamaIndex, Chroma, BGE-base embeddings (local), OpenAI `gpt-4o-mini`, DeepEval,
Microsoft Presidio, Streamlit.

## Where it's at

The RAG pipeline, evaluation suite, HIPAA compliance layer, and red-teaming are
done. Things I still want to add: a second eval framework (Ragas) to cross-check
my numbers, some drift monitoring, and CI so the eval runs on every push.
