# CardioTwin Data Card: Multi-Modal Clinical PPG & Cardiometabolic Cohorts

## Overview & Dataset Architecture
CardioTwin unites two clinical data streams to construct a personalized cardiovascular digital twin:
1. **Stream 1: Longitudinal Patient EHR Profiles** — Demographics, ICD-9 diagnosis codes, laboratory lipid panels, systolic/diastolic blood pressure, glycemic state, smoking history, and 10-year Framingham CVD baseline risk.
2. **Stream 2: High-Frequency Continuous Telemetry** — Standardized 100 Hz photoplethysmogram (PPG) waveforms, derived pulse rate, heart-rate variability (RMSSD, SDNN, pNN50), pulse-rate variability (PRV), and peripheral capillary oxygen saturation ($\text{SpO}_2$).

---

## 1. Unified Multi-Modal Clinical Telemetry Dataset (v3.0.0)

CardioTwin v3 compiles **4,683 standardized 10-second windows** at 100 Hz across **2,271 unique clinical individuals** from four established clinical and open research repositories:

| Database / Source | Records / Patients | Waveforms Ingested | Primary Role & Clinical Taxonomy | Access & Governance |
|:---|:---:|:---:|:---|:---|
| **MIMIC-III-Ext-PPG v1.1.0** (PhysioNet) | **2,000 unique patients** | 2,000 10s windows | **Clinical ICU Telemetry**: 400 Atrial Fibrillation (`AFib`), 400 Sinus Bradycardia, 400 Sinus Tachycardia, 400 Cardiac Paced / AV Blocks, 400 Normal controls. | 🔐 **Credentialed Access** (PhysioNet Data Use Agreement). Raw data excluded from public repository. |
| **PhysioNet CinC Challenge 2015** | **231 ICU records** | 1,890 10s windows | **Critical ICU Alarms**: Expert cardiologist-adjudicated True Alarms: Ventricular Tachycardia (`V_Tachycardia`), Ventricular Flutter/Fib (`V_Flutter_Fib`), Asystole, Bradycardia, Tachycardia. | 📂 **Open Research License** (PhysioNet Contributor License). |
| **BUT PPG v2.0** (Brno Univ. of Technology) | **39 subjects** | 792 10s windows | **Wearable Optical Robustness**: High-noise smartphone PPG recordings with optical motion artifacts and baseline drift. | 📂 **Open Research License**. |
| **BIDMC PPG & Respiration** | **1 patient** | 1 10s window | Clean hospital ICU baseline. | 📂 **Open Data Commons PDDL**. |
| **Total Unified Cohort** | **2,271 unique patients** | **4,683 windows** | Standardized to 100 Hz (1,000 samples/window matching ESP32 hardware). | Strict patient-level grouping (`patient_ids`). |

---

## 2. Multi-Class Ground Truth Taxonomy (8 Classes)

The compiled dataset spans the following clinical rhythm categories:
1. **Normal Sinus Rhythm (`Normal`):** 1,193 windows (25.5%)
2. **Sinus Tachycardia (`Tachycardia`):** 1,048 windows (22.4%)
3. **Ventricular Tachycardia (`V_Tachycardia`):** 732 windows (15.6%)
4. **Sinus Bradycardia (`Bradycardia`):** 634 windows (13.5%)
5. **Atrial Fibrillation (`AFib`):** 400 windows (8.5%)
6. **Cardiac Paced & Conduction Blocks (`Cardiac_Paced`):** 400 windows (8.5%) — VPACE, AVPACE, APACE, 1AVB, AFLT
7. **Asystole / Cardiac Arrest (`Asystole`):** 204 windows (4.4%)
8. **Ventricular Flutter / Fibrillation (`V_Flutter_Fib`):** 72 windows (1.5%)

---

## 3. Data Governance & PhysioNet DUA Compliance Policy

> [!IMPORTANT]
> **Strict Non-Redistribution Guarantee:**
> In accordance with the **PhysioNet MIMIC-III Data Use Agreement (DUA)** and institutional data-governance standards:
> - **NO raw MIMIC-III patient waveforms, `.dat`, `.hea`, or clinical metadata files are committed to or distributed in this public repository.**
> - All raw data directories (`data/raw/`, `recordings/`, `*.npz`) are strictly excluded via [`.gitignore`](file:///.gitignore).
> - Only reproducible acquisition scripts ([`scripts/run_v3_pipeline.py`](file:///scripts/run_v3_pipeline.py)), non-identifiable dataset manifests, and aggregated statistical summaries are tracked in Git.
> - Researchers seeking to reproduce the full MIMIC-III ingestion must sign the PhysioNet DUA and provide valid credentialed credentials via local environment prompts.

---

## 4. Longitudinal Cardiometabolic Cohort (Synthetic EHR)

### Indian Cardiometabolic Patient Profiles
- **File:** `backend/synthetic_patients.json`
- **Total Profiles:** 100 clinically parameterized Indian patients (50 male, 50 female).
- **Clinical Variables:**
  - Demographics: Age, Gender, City, State.
  - Vitals: Baseline Resting HR, Systolic Blood Pressure (SBP), Diastolic BP, Baseline $\text{SpO}_2$, Antihypertensive Treatment Status.
  - Laboratory Panels: Total Cholesterol (mg/dL), HDL Cholesterol (mg/dL), Fasting Blood Glucose, $\text{HbA}_{1c}$, Serum Creatinine.
  - Comorbidities & History: Smoking status, pack-years, Type-2 Diabetes Mellitus, prior Percutaneous Coronary Intervention (PCI) / Coronary Artery Disease.
- **Framingham Heart Study Implementation:**
  - Derived using the D'Agostino et al. (*Circulation* 2008) sex-stratified Cox proportional hazards general CVD model.
  - Age extrapolation guardrails: Derivation cohort bounded to ages 30–74. Patients outside this range have explicit `age_extrapolated: True` flags.
- **South Asian Recalibration Factor:**
  - Evaluated at 1.45× based on epidemiological consensus (Bansal et al. 2020, Garg et al. 2017, ACC/AHA South Asian guidance).
  - Explicitly labeled in the codebase as an **exploratory prototype assumption** rather than an autonomous clinical diagnostic determination.

---

## 5. Signal Preprocessing & Quality Controls
1. **Bandpass Filtering:** 4th-order Butterworth bandpass filter ($0.5\,\text{Hz} - 8.0\,\text{Hz}$) to eliminate baseline wander and high-frequency noise.
2. **Standardization:** Resampled to 100 Hz matching ESP32 MAX30102 hardware capabilities.
3. **Feature Extraction:** 27 time-domain, frequency-domain (Welch PSD), HRV (RMSSD, SDNN, pNN50, pNN20), and morphological biomarkers extracted per 10-second window.
4. **Signal Quality Index (SQI):** Real-time SQI threshold ($SQI \ge 0.40$ and $\sigma \ge 0.05$) to safely suppress motion artifacts and lead-off conditions.
