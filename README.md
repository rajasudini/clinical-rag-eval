# clinical-rag-eval

> Healthcare AI Quality Evaluation System — a diabetes-guidance RAG assistant
> wrapped in a multi-layer evaluation framework (functional, HIPAA compliance,
> safety red-teaming, monitoring, and agent evaluation).

**Status:** 🚧 Phase 1 — building the RAG chatbot.

## Why this project

Demonstrates production-grade LLM quality engineering: building a retrieval
system over official `.gov` clinical sources and rigorously evaluating it for
faithfulness, clinical-boundary safety, HIPAA/PHI leakage, and adversarial
robustness — with metrics, documented failures, and CI.

## Knowledge base (official sources only, no patient data)

| Authority | Document |
|---|---|
| CDC | National Diabetes Statistics Report |
| NIH / NIDDK | Managing diabetes / Type 2 overview |
| CMS / Medicare | Coverage of Diabetes Supplies, Services & Prevention Programs |
| USPSTF | Screening for Prediabetes & Type 2 Diabetes |
| FDA | Metformin drug-safety / label information |

## Structure

```
01-rag-chatbot/     # RAG pipeline (LlamaIndex + Chroma + OpenAI)
```
_More phases added as they are built._
