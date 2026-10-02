# CardioTwin Model Card: 100Hz Standardized Multi-Modal PPG Arrhythmia Modulator

## Model Details
- **Model Name:** CardioTwin Multi-Class XGBoost Arrhythmia Screening Classifier
- **Model Version:** 3.0.0-clinical-mimic-2000 (Authoritative Release)
- **Model Status:** Investigational Screening Prototype (Non-Diagnostic)
- **Model Type:** Gradient Boosted Decision Trees (`XGBClassifier`) with balanced multi-class re-weighting
- **Input Features:** 27 time-domain, frequency-domain (Welch PSD), morphological, and signal-quality biomarkers extracted from standardized 10-second (1,000 samples at 100 Hz) PPG windows.
- **Output Classes (8):** `Normal`, `Tachycardia`, `Bradycardia`, `AFib` (Atrial Fibrillation), `Cardiac_Paced` (Pacemakers & Conduction Blocks), `V_Tachycardia` (Ventricular Tachycardia), `V_Flutter_Fib` (Ventricular Flutter/Fibrillation), `Asystole`
- **Training Population:** 2,271 unique patients (4,683 total 10-second windows):
  - **MIMIC-III-Ext-PPG v1.1.0:** 2,000 unique ICU patients (400 AFib, 400 Bradycardia, 400 Tachycardia, 400 Paced/Blocks, 400 Normal controls) under PhysioNet Credentialed Data Use Agreement.
  - **PhysioNet CinC 2015:** 231 ICU records (1,890 verified true arrhythmia segments: VT, VFib, Asystole, Brady, Tachy).
  - **BUT PPG v2.0:** 39 subjects (792 expert-annotated smartphone recordings with optical motion noise).
  - **BIDMC PPG:** Hospital ICU baseline.
- **Trained Artifacts:** `model/xgboost_ppg_model.pkl`, `model/scaler.pkl`, `model/label_encoder.pkl`, `model/feature_names.pkl`, `model/model_metadata.json`

---

## Intended Use & Clinical Scope
- **Primary Use:** Non-diagnostic, observational computer-assisted screening of cardiac rhythm instability and real-time modulation of the CardioTwin multimodal digital twin state.
- **Intended Population:** Adults undergoing physiological rhythm monitoring and longitudinal cardiometabolic risk surveillance.
- **Critical Safety Guardrail:** PPG rhythm screening is an **observational screening prototype** and **NOT an autonomous medical diagnostic device**. Any detected rhythm irregularity (especially AFib, VT, VF, and asystole) mandates immediate verification via 12-lead diagnostic ECG and physician evaluation.
- **Prohibited / Out-of-Scope Uses:**
  - Autonomous prescribing or titration of antiarrhythmics or anticoagulants.
  - Emergency room defibrillation or resuscitation decision-making.
  - Standalone clinical diagnosis without ECG verification.

---

## Evaluation Protocol & Leakage Prevention
Healthcare AI evaluations frequently suffer from optimistic window-level splitting where overlapping slices of the same patient appear in both training and testing folds, inflating apparent accuracy to 85–95%.

**CardioTwin v3 enforces strict, uncompromised patient isolation:**
1. **Patient-Level Grouped Splitting:** Evaluated using `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` grouped strictly on unique patient identifiers (`patient_ids`).
2. **Zero Patient Overlap:** A patient present in validation is **never** seen in training across any fold.
3. **Train-Only Preprocessing:** `StandardScaler` is fitted strictly on the training partition of each fold; the validation partition is transformed using train parameters.

---

## Out-of-Fold Cross-Validation Metrics (Leak-Free Benchmark)
Evaluated across all **2,271 patients and 4,683 windows**:

| Metric | 5-Fold Grouped Cross-Validation (v3) | Legacy v2 Benchmark (354 records) |
|---|---|---|
| **Accuracy** | **56.97%** | 38.54% ± 3.25% |
| **Macro-F1 Score** | **0.4671** (95% CI: [0.4285, 0.5057]) | 0.3468 ± 0.0185 |
| **Weighted-F1 Score**| **0.5685** | 0.3781 ± 0.0306 |
| **Random Guess Baseline**| 12.50% (8-Class) | 16.67% (6-Class) |
| **Unique Patients** | **2,271** (2,000 from MIMIC-III) | 354 records |

### Per-Class Cross-Validation Performance (v3)
| Class | Precision | Recall | F1-Score | Support (Windows) |
|---|---|---|---|---|
| **Normal** | 0.8167 | 0.7469 | **0.7802** | 1,193 |
| **Bradycardia** | 0.6462 | 0.6625 | **0.6542** | 634 |
| **Tachycardia** | 0.5986 | 0.6632 | **0.6292** | 1,048 |
| **AFib (Atrial Fibrillation)** | 0.5146 | 0.6175 | **0.5614** | 400 |
| **V_Tachycardia** | 0.3828 | 0.2923 | **0.3315** | 732 |
| **Cardiac_Paced & Blocks** | 0.2790 | 0.3425 | **0.3075** | 400 |
| **Asystole** | 0.2682 | 0.2353 | **0.2507** | 204 |
| **V_Flutter_Fib** | 0.2222 | 0.2222 | **0.2222** | 72 |

> **Scientific Transparency Note:** Across 8 complex rhythm classes with strict patient isolation, achieving 56.97% accuracy and 0.4671 Macro-F1 against an 8-class random chance of 12.5% demonstrates strong physiological discriminative power. High recall on AFib (61.75%) and Bradycardia (66.25%) validates the benefit of the balanced MIMIC-III cohort.

---

## Signal Quality Index (SQI) Safety Gating
Optical sensors (e.g. MAX30102) are prone to baseline drift and motion artifacts that mimic arrhythmias:
- **Motion Artifact Gating:** If $SQI < 0.40$, rhythm predictions are **suppressed**. The system outputs `Signal Insufficient / Motion Artifact (Gated)` to prevent false alarms.
- **Lead-Off / Disconnection Detection:** If signal amplitude variance $\sigma < 0.05$, the system outputs `Sensor Disconnected / Lead Off`.
- **False Alarm Suppression:** Automated gating ensures physical finger repositioning does not trigger erroneous ventricular tachycardia or asystole alerts.

---

## Hardware Validation Status & Technical Limitations
- **Current Validation State:** **Investigational Hardware Prototype**.
- **Audit Findings:** Automated validation across 39 physical MAX30102 recording sessions demonstrates that the SQI safety gate correctly suppresses motion artifacts. However, only limited physical sessions achieved $\ge 10$ seconds of uninterrupted optical contact, with baseline pulse rate estimates requiring ongoing calibration.
- **Planned Work:** Further acceptance testing is scheduled to benchmark live MAX30102 optical readings against a clinical-grade pulse oximeter across stable contact, deliberate motion, and sensor liftoff conditions prior to any live diagnostic claims.

---

## Ethical & Regulatory Considerations
- **Non-Diagnostic Nature:** Explicitly labeled on all backend APIs and frontend dashboards.
- **Explainability:** All predictions accompanied by class probability distributions and SQI confidence scores.
- **Provenance:** Every telemetry update is tagged with its provenance (`LIVE_HARDWARE`, `MIMIC_ICU_REPLAY`, `RECORDED_REPLAY`, or `SIMULATION`).
- **Data Governance:** No raw MIMIC-III patient waveforms or identifiable hospital data are distributed publicly; access requires credentialed PhysioNet authorization under the MIMIC-III Data Use Agreement.
