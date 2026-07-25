"""
Phase 2 eval — LLM-as-judge (DeepEval). Runs faithfulness + relevancy ONLY on
"answer" cases. Refuse/admit_ignorance cases were already judged deterministically
in run_eval (behavior_pass); the LLM-judge leaves them alone.

Run from repo root, AFTER run_eval.py:  python 02-eval-suite/judge_eval.py
"""

import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

os.environ["DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE"] = "30"

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

HERE = Path(__file__).resolve()
EVAL_DIR = HERE.parent
PROJECT = EVAL_DIR.parent
RESULTS_DIR = EVAL_DIR / "results"

JUDGE_MODEL = "gpt-4o-mini"
THRESHOLD = 0.7


def latest_results():
    files = sorted(glob.glob(str(RESULTS_DIR / "results_*.json")))
    if not files:
        sys.exit("No results_*.json found. Run run_eval.py first.")
    return Path(files[-1])


def score_metric(metric, tc):
    try:
        metric.measure(tc)
        return round(metric.score, 3), metric.reason
    except Exception as e:
        return None, f"ERROR: {type(e).__name__}"


def main():
    load_dotenv(PROJECT / ".env")

    path = latest_results()
    results = json.loads(path.read_text(encoding="utf-8"))
    print(f"Judging {len(results)} cases from {path.name} with {JUDGE_MODEL}\n")

    faith = FaithfulnessMetric(threshold=THRESHOLD, model=JUDGE_MODEL,
                               include_reason=True, async_mode=False)
    relev = AnswerRelevancyMetric(threshold=THRESHOLD, model=JUDGE_MODEL,
                                  include_reason=True, async_mode=False)

    judged = []
    for r in results:
        if r["expected_behavior"] == "answer":
            tc = LLMTestCase(
                input=r["input"],
                actual_output=r["actual_output"],
                expected_output=r["expected_output"],
                retrieval_context=r["retrieval_context"],
            )
            r["faithfulness"], r["faithfulness_reason"] = score_metric(faith, tc)
            r["answer_relevancy"], r["relevancy_reason"] = score_metric(relev, tc)
            verdict = f"faith={str(r['faithfulness']):<5} relevancy={str(r['answer_relevancy']):<5}"
        else:
            r["faithfulness"] = None
            r["answer_relevancy"] = None
            verdict = f"declined_pass={r.get('behavior_pass')}"

        judged.append(r)
        print(f"  {r['id']}  {r['category']:<16} {r['expected_behavior']:<15} {verdict}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = RESULTS_DIR / f"judged_{stamp}.json"
    out.write_text(json.dumps(judged, indent=2), encoding="utf-8")
    print(f"\nSaved -> results/{out.name}")


if __name__ == "__main__":
    main()