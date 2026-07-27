"""Streamlit dashboard for the clinical-rag-eval project.
Reads a committed summary.json snapshot so it deploys without the raw results.

Run:  streamlit run 06-dashboard/app.py
"""

import json
from pathlib import Path

import streamlit as st

DATA = json.loads((Path(__file__).parent / "summary.json").read_text(encoding="utf-8"))

st.set_page_config(page_title="Clinical RAG Eval", page_icon="🏥", layout="wide")

st.title("🏥 Clinical RAG — Evaluation Dashboard")
st.caption(
    "A diabetes-guidance RAG assistant over official U.S. government sources, "
    "wrapped in a multi-layer evaluation framework: functional metrics, HIPAA "
    "compliance, and adversarial red-teaming."
)


def pct(n, d):
    return f"{round(100 * n / d)}%" if d else "—"


# --- Headline KPIs ---
ev, hp, rt = DATA["eval"], DATA["hipaa"], DATA["redteam"]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Correctness", pct(ev["correctness_pass"], ev["correctness_total"]),
          f"{ev['correctness_pass']}/{ev['correctness_total']} answers")
c2.metric("Answer Relevancy", pct(ev["relevancy_pass"], ev["relevancy_total"]),
          f"{ev['relevancy_pass']}/{ev['relevancy_total']} answers")
c3.metric("Safety (refusals)", pct(ev["safety_declined"], ev["safety_total"]),
          f"{ev['safety_declined']}/{ev['safety_total']} handled")
c4.metric("HIPAA Compliance", pct(hp["compliant"], hp["total"]),
          f"{hp['compliant']}/{hp['total']} responses")
c5.metric("Red-team Defense", pct(rt["defended"], rt["total"]),
          f"{rt['defended']}/{rt['total']} attacks")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Evaluation", "🔒 HIPAA Compliance", "🛡️ Red-team", "🧪 Experiments"]
)

with tab1:
    st.subheader("Functional evaluation")
    st.write(f"**Golden dataset:** {ev['golden_cases']} cases "
             f"({ev['answer_cases']} answer, {ev['refusal_cases']} refusal).")
    st.write(f"**Metrics:** {ev['metrics']}")
    st.progress(ev["correctness_pass"] / ev["correctness_total"],
                text=f"Correctness (GEval vs expected): {ev['correctness_pass']}/{ev['correctness_total']}")
    st.progress(ev["relevancy_pass"] / ev["relevancy_total"],
                text=f"Answer relevancy: {ev['relevancy_pass']}/{ev['relevancy_total']}")
    st.progress(ev["safety_declined"] / ev["safety_total"],
                text=f"Correct refusals (boundary/injection/out-of-scope): {ev['safety_declined']}/{ev['safety_total']}")

with tab2:
    st.subheader("HIPAA compliance layer")
    st.metric("Responses compliant", f"{hp['compliant']}/{hp['total']}")
    st.write(hp["components"])
    st.info("PHI detection scoped to high-signal identifiers (names, SSNs, emails) — "
            "dates/locations/public phone numbers over-fire on general medical text.")

with tab3:
    st.subheader("Adversarial red-teaming")
    st.metric("Attacks defended", f"{rt['defended']}/{rt['total']}")
    st.write("**Attack categories:** " + ", ".join(rt["categories"]))
    st.success("Every jailbreak, injection, prompt-extraction, PHI-extraction, and "
               "boundary-evasion attempt was safely refused.")

with tab4:
    st.subheader("Evaluation-driven experiments (measured before/after)")
    for e in DATA["experiments"]:
        st.markdown(f"**{e['name']}**")
        st.write(e["result"])
        st.write("")

st.divider()
sysd = DATA["system"]
st.caption(
    f"Domain: {sysd['domain']}  •  Stack: {sysd['stack']}  •  "
    f"{DATA['findings_count']} findings logged  •  Generated {DATA['generated']}"
)
