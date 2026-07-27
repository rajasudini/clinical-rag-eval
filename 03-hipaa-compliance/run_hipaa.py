"""Apply the HIPAA compliance metric across the latest eval results."""

import glob
import json
import sys
from pathlib import Path

from deepeval.test_case import LLMTestCase

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hipaa_metric import HIPAAComplianceMetric

RESULTS = Path(__file__).resolve().parents[1] / "02-eval-suite" / "results"


def latest():
    files = sorted(glob.glob(str(RESULTS / "results_*.json")))
    if not files:
        sys.exit("No results_*.json — run run_eval.py first.")
    return Path(files[-1])


def main():
    path = latest()
    cases = json.loads(path.read_text(encoding="utf-8"))
    metric = HIPAAComplianceMetric()

    flagged = []
    for c in cases:
        tc = LLMTestCase(input=c["input"], actual_output=c["actual_output"])
        metric.measure(tc)
        if not metric.is_successful():
            flagged.append((c["id"], round(metric.score, 2), metric.reason))

    print(f"HIPAA compliance over {len(cases)} responses ({path.name}):")
    print(f"  compliant: {len(cases) - len(flagged)}/{len(cases)}\n")
    for cid, score, reason in flagged:
        print(f"  FLAG {cid}  score={score}  {reason}")


if __name__ == "__main__":
    main()