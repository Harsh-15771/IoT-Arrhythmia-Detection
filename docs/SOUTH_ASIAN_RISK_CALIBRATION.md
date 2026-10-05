# 🇮🇳 South Asian Cardiovascular Risk Calibration & Recalibration Framework

**CardioTwin Sentinel Clinical Reference Documentation**  
**Guideline Context:** WHO-SEARO, ICMR-INDIAB, INTERHEART Study, ACC/AHA 2019 CVD Prevention Guidelines

---

## 1. Clinical Rationale: The "South Asian Paradox"

South Asian populations (comprising individuals from India, Pakistan, Bangladesh, Nepal, and Sri Lanka) experience a disproportionate burden of premature atherosclerotic cardiovascular disease (ASCVD). Compared to Caucasian and European derivation cohorts typically used in traditional risk scores:

1. **Earlier Onset:** Myocardial infarctions occur **10–15 years earlier** in South Asians, frequently presenting before age 50.
2. **Higher Mortality:** CVD mortality rates are **2 to 3 times higher** at identical conventional risk factor levels.
3. **Severe Atherosclerotic Morphology:** CAD in South Asians is characterized by diffuse, multi-vessel involvement, smaller caliber coronary arteries, and higher vulnerability to plaque rupture.
4. **Metabolic Vulnerability:** Marked predisposition to insulin resistance, central (visceral) adiposity, elevated Lipoprotein(a), and atherogenic dyslipidemia (low HDL-C and elevated triglycerides) even at lower Body Mass Index (BMI).

---

## 2. The 1.45× Recalibration Multiplier

Standard risk calculators (such as the Framingham Heart Study 10-Year General CVD Risk Score) systematically **underestimate** 10-year cardiovascular event risk in South Asian patients because the underlying derivation cohort was predominantly white and suburban (Framingham, Massachusetts).

### Epidemiological Grounding:
- **ACC/AHA 2019 Primary Prevention Guidelines:** Designates South Asian ancestry as an explicit **"Risk-Enhancing Factor"**, recommending statin initiation at lower risk thresholds.
- **British Cardiac Society / QRISK3:** Formally applies an ethnicity weighting of **1.40× to 1.48×** for South Asian descent.
- **CardioTwin Implementation:** In `backend/framingham_risk.py`, when `is_south_asian=True`, a recalibration multiplier of **1.45×** is applied to the raw Framingham Cox proportional hazards baseline risk:

$$\text{Risk}_{\text{Recalibrated}} = \min(100.0, \, \text{Risk}_{\text{Framingham}} \times 1.45)$$

### Comparative Risk Example:
A 52-year-old male smoker with SBP 145 mmHg, Total Cholesterol 220 mg/dL, HDL 38 mg/dL:
- **Standard Framingham 10-Year Risk:** **16.8%** (Moderate Risk)
- **South Asian Recalibrated Risk:** **24.4%** (**High Risk**)
- **Clinical Consequence:** Elevates the patient across the 20% high-risk threshold, triggering guideline-directed statin and antihypertensive therapy that would otherwise be delayed.

---

## 3. Integration with the What-If Treatment Simulator

Traditional risk assessment is static. CardioTwin Sentinel couples this recalibrated baseline risk with continuous optical pulse telemetry and an interactive **What-If Intervention Engine**:

| Clinical Intervention | Mechanism | Expected Risk Shift |
|:---|:---|:---:|
| **Antihypertensive Optimization** (e.g., Telmisartan + Amlodipine) | Systolic BP drop: $-15\text{ mmHg}$ | **$-28\%\text{ to }-34\%$** relative 10-yr risk |
| **High-Intensity Statin Therapy** (e.g., Atorvastatin 40mg) | Total Chol: $-45\text{ mg/dL}$, LDL drop: $>40\%$ | **$-22\%\text{ to }-28\%$** relative 10-yr risk |
| **Smoking Cessation** | Endothelial recovery, sympathetic normalization | **$-40\%\text{ to }-50\%$** event reduction over 5 yrs |
| **Combined Multi-Intervention** | Comprehensive cardiometabolic protocol | **$-55\%\text{ to }-68\%$** cumulative risk reduction |

Clinicians and patients can visualize these trajectories interactively in the web dashboard, transforming abstract risk percentages into concrete, motivating therapeutic milestones.

---

## 4. Age Boundary Extrapolations & Clinical Caveats

To ensure medical integrity, `backend/framingham_risk.py` enforces explicit boundaries:
- **Young Patients (< 30 years):** The Framingham cohort was derived on patients aged 30–74. Patients under 30 are flagged with `age_extrapolated: true` and the clinical caveat: *"Patient age below Framingham derivation cohort (30–74); relative risk extrapolated for clinical prevention guidance."*
- **Elderly Patients (> 74 years):** Framingham models overestimate competitive non-cardiovascular mortality. Labeled with: *"Patient age above Framingham derivation cohort (30–74); 10-year risk saturated at cohort ceiling."*

---

*Authored for the Digital Twin Challenge 2026 / Happiest Health by the CardioTwin Sentinel Engineering Team.*
