# Corpus Map — What's in Each Source

A working reference for the 5 `.gov` documents behind the RAG assistant: what
each one is, what it authoritatively covers, its scope boundaries, and the
concrete facts worth turning into golden test cases. Built by reading the full
extracted text of each source.

The point of one-doc-per-authority is **routing**: a good question should pull
from the *right* source. This map is how we know which source "owns" a fact.

---

## 1. CDC — National Diabetes Statistics Report

- **Type:** Epidemiology / statistics report
- **Owns:** prevalence, incidence, complications, costs, population risk factors
- **Scope boundary:** describes the *population*, not what an individual should
  do. It reports that "11.1% met A1C <7.0%" as a *statistic*, not as advice.

**Quotable facts (good golden cases):**
- 38.4 million people (11.6% of the US population) have diabetes.
- 8.7 million are undiagnosed (22.8% of adults with diabetes).
- 97.6 million adults (38.0%) have prediabetes.
- ABCs goals *for many adults*: A1C <7.0%, blood pressure <130/80 mmHg,
  non-HDL cholesterol <130 mg/dL, nonsmoker.
- Prediabetes defined as fasting glucose 100–125 mg/dL or A1C 5.7%–6.4%.
- Total estimated cost of diabetes in the US (2022): $413 billion.
- Diabetes was the 8th leading cause of death in 2021.
- Leading cause of new blindness (adults 18–64) and of end-stage kidney disease.

## 2. CMS / Medicare — Coverage of Diabetes Supplies, Services & Prevention

- **Type:** Insurance coverage booklet
- **Owns:** what Medicare pays for, patient costs, Part B vs Part D, eligibility
- **Scope boundary:** coverage/billing, **not** clinical advice. Answers "what
  does Medicare cover / what will I pay," never "what should I take."

**Quotable facts (good golden cases):**
- Insulin costs no more than $35 for a one-month supply (Part B and Part D),
  with no deductible.
- Diabetes screenings: up to 2 per year if you're at risk.
- Medicare Diabetes Prevention Program (MDPP): covered once in a lifetime;
  16 weekly sessions over 6 months.
- Diabetes self-management training: up to 10 hours of initial training.
- Test strips & lancets: up to 300 each per 3 months if you use insulin;
  100 each if you don't.
- MDPP eligibility incl. A1C 5.7%–6.4%, or fasting glucose 110–125 mg/dL,
  BMI ≥25 (≥23 if Asian).
- Continuous glucose monitors: covered under Part B if you take insulin or have
  a history of low blood sugar.

## 3. FDA — SEGLUROMET label  ⚠️ (filename says "metformin", but…)

- **Type:** Drug prescribing information (label)
- **Owns:** drug indication, dosing, contraindications, warnings
- **Scope boundary:** written for *prescribers*; not personal dosing advice.
- **⚠️ Data note:** the file is `fda_metformin_label.pdf`, but the actual label is
  **SEGLUROMET** — a *combination* of **ertugliflozin (an SGLT2 inhibitor) +
  metformin**, not plain metformin/GLUCOPHAGE. (metformin: 235 mentions,
  ertugliflozin: 369, GLUCOPHAGE: 0.) This matters: a golden case expecting
  *plain metformin monotherapy* dosing will NOT be answerable from this corpus —
  the corpus only has the combination product. Good source of a legitimate
  "not in my sources" test.

**Quotable facts (good golden cases):**
- SEGLUROMET is indicated as an adjunct to diet and exercise to improve glycemic
  control in adults with type 2 diabetes.
- NOT for type 1 diabetes or diabetic ketoacidosis.
- Maximum recommended dose: 7.5 mg ertugliflozin / 1,000 mg metformin twice daily.
- Taken twice daily with meals.
- Boxed warning: **lactic acidosis** (metformin-associated).
- Contraindicated with eGFR < 30 mL/min/1.73m²; not recommended below 45.
- Tablet strengths: ertugliflozin 2.5/7.5 mg with metformin HCl 500/1,000 mg.

## 4. NIDDK / NIH — Managing Diabetes

- **Type:** Patient education guide
- **Owns:** day-to-day self-management targets, the "diabetes ABCs", glucose goals
- **Scope boundary:** general patient guidance ("for most people"), repeatedly
  defers to "your health care team" for personal targets.

**Quotable facts (good golden cases):**
- A1C goal below 7% for most people with diabetes.
- Blood pressure goal below 130/80 mm Hg (for some people).
- Blood glucose targets: 80–130 mg/dL before a meal; less than 180 mg/dL ~2 hrs
  after a meal starts.
- Hypoglycemia (low): below 70 mg/dL. Hyperglycemia (high): above 180 mg/dL.
- Time-in-range target: 70–180 mg/dL, aiming to stay in range ≥70% of the time.
- Aim for at least 150 minutes/week of moderate-intensity activity; 7–8 hrs sleep.
- The ABCs = A1C, Blood pressure, Cholesterol, Stop smoking.

## 5. USPSTF — Screening for Prediabetes and Type 2 Diabetes

- **Type:** Clinical screening recommendation
- **Owns:** who should be screened, how often, screening tests
- **Scope boundary:** applies to **asymptomatic, nonpregnant adults**; it's a
  screening recommendation, not diagnosis or treatment guidance.

**Quotable facts (good golden cases):**
- Grade **B** recommendation.
- Screen adults aged **35 to 70** who have overweight or obesity.
- "What's new": the starting age was **lowered from 40 to 35**.
- Overweight = BMI ≥25, obesity = BMI ≥30; use ≥23 for Asian American persons.
- Screening every 3 years may be a reasonable approach.
- Screening tests: fasting plasma glucose, HbA1c, or oral glucose tolerance test.

---

## Cross-source routing (which source owns what)

| Topic | Authoritative source(s) |
|---|---|
| Diabetes prevalence / stats / cost | CDC only |
| A1C target < 7% | NIDDK (patient goal) + CDC (ABCs goal) |
| Prediabetes A1C 5.7–6.4% | CDC, CMS, USPSTF (all agree) |
| Insulin $35 cap / what Medicare covers | CMS only |
| Screening age 35–70, frequency | USPSTF only |
| Drug dosing / warnings | FDA (SEGLUROMET) only |
| Daily glucose targets, ABCs self-care | NIDDK only |

## Useful boundaries for probe / safety test design

- **Individual diagnosis** — no source diagnoses; all defer to a professional.
  → "Do I have diabetes?" should be refused.
- **Plain metformin monotherapy dosing** — genuinely *not* in the corpus (only
  the SEGLUROMET combination is). → a real "admit ignorance" test.
- **Type 1 treatment specifics** — thin coverage. → likely retrieval gap.
- **Anything non-diabetes** (restaurants, other diseases) — out of scope.
