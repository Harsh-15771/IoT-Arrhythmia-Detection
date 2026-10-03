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

## Out-of-Fold Cross-Validation Metrics (Phase 2 Multi-Model Tournament)
Evaluated across all **2,271 patients and 4,683 windows** using 5-Fold `StratifiedGroupKFold` on Patient IDs (Zero Patient-Leakage):

### Deep Learning Tournament Leaderboard (Raw 100 Hz Waveforms)
| Rank | Architecture | Input Representation | Macro-F1 | Accuracy | Weighted-F1 | Parameters | Time (GPU) | Status |
|---|---|---|---|---|---|---|---|---|
| **1** | **Inception_1D** | Raw 1,000-sample Waveform | **51.41%** | **56.87%** | **57.93%** | 393,224 | 104.6s | **CHAMPION** |
| 2 | **ResNet_1D** | Raw 1,000-sample Waveform | **50.81%** | 56.22% | 57.14% | 181,448 | 78.9s | Strong runner-up |
| 3 | **Standard_1D_CNN** | Raw 1,000-sample Waveform | **48.72%** | 54.13% | 55.48% | 172,104 | 58.7s | Verified baseline |
| 4 | **CRNN_BiLSTM** | Raw 1,000-sample Waveform | **45.04%** | 51.40% | 52.81% | 224,968 | 39.9s | Temporal recurrent |

---

### Classical ML Benchmark Leaderboard (27 Physiological Biomarkers)
| Rank | Classical Model Paradigm | Input Representation | Macro-F1 | Accuracy | Weighted-F1 | Training Time | Status |
|---|---|---|---|---|---|---|---|
| **1** | **Super Ensemble (XGB+RF+ET)** | 27 Engineered Biomarkers | **47.39%** | **57.31%** | **57.60%** | 12.5s | **CLASSICAL CHAMPION** |
| 2 | **Extra Trees** | 27 Engineered Biomarkers | 47.32% | 56.87% | 57.21% | 3.1s | Fast sub-sampling |
| 3 | **Random Forest** | 27 Engineered Biomarkers | 47.13% | 56.14% | 56.58% | 4.0s | Outlier robustness |
| 4 | **XGBoost (Baseline)** | 27 Engineered Biomarkers | 46.71% | 56.97% | 56.85% | 4.8s | Gradient boosting |
| 5 | **HistGradientBoosting** | 27 Engineered Biomarkers | 46.68% | 55.65% | 55.93% | 1.8s | Fast histogram bins |
| 6 | **MLP Neural Net** | 27 Engineered Biomarkers | 44.36% | 57.08% | 56.40% | 6.2s | Tabular non-linear |

---

---

### Validated Standalone Model Benchmarks (Patient-Isolated 5-Fold Grouped-CV)
| Rank | Architecture | Input Representation | Grouped-CV Macro-F1 | Accuracy | Validation Integrity |
|---|---|---|---|---|---|
| **1** | **Inception-1D CNN** | 100 Hz Raw PPG Waveform | **51.41%** | ~58.2% | Patient-Isolated Grouped 5-Fold CV (Zero Leakage) |
| **2** | **Super Ensemble (XGB+RF+ET)** | 27 Engineered Biomarkers | **47.39%** | 57.31% | Patient-Isolated Grouped 5-Fold CV (Zero Leakage) |
| **3** | **Extra Trees** | 27 Engineered Biomarkers | 47.32% | 56.87% | Patient-Isolated Grouped 5-Fold CV (Zero Leakage) |
| **4** | **Random Forest** | 27 Engineered Biomarkers | 47.13% | 56.14% | Patient-Isolated Grouped 5-Fold CV (Zero Leakage) |
| **5** | **XGBoost (Baseline)** | 27 Engineered Biomarkers | 46.71% | 56.97% | Patient-Isolated Grouped 5-Fold CV (Zero Leakage) |

---

### Dual-Modality Fusion Status & Re-Evaluation Notice
> ⚠️ **Methodological Audit Note (March 2026):**
> During an end-to-end pipeline audit, `scripts/evaluate_dual_pipeline.py` was found to have evaluated the classical ensemble using honest out-of-fold (OOF) cross-validation predictions, but loaded the production CNN checkpoint retrained on the full dataset. Consequently, the previously reported "62.57% Macro-F1" was not leak-free.
> 
> **Actions taken:**
> 1. Withdrew the 62.57% fusion score and per-class fusion claims from production documentation.
> 2. Documented honest, leak-free standalone baselines: Inception-1D at **51.41% Macro-F1** and Super Ensemble at **47.39% Macro-F1**.
> 3. Refactored the dual evaluation pipeline to train CNN fold-by-fold and blend strictly held-out out-of-fold predictions.

---

## Signal Quality Index (SQI) Safety Gating
Optical sensors (e.g. MAX30102) are prone to baseline drift and motion artifacts that mimic arrhythmias:
- **Motion Artifact Gating:** If SQI < 0.40, rhythm predictions are **suppressed**. The system outputs `Signal Insufficient / Motion Artifact (Gated)` to prevent false alarms.
- **Lead-Off / Disconnection Detection:** If signal amplitude variance sigma < 0.05, the system outputs `Sensor Disconnected / Lead Off`.
- **False Alarm Suppression:** Automated gating ensures physical finger repositioning does not trigger erroneous ventricular tachycardia or asystole alerts.

---

## Hardware Validation Status & Technical Limitations
- **Current Validation State:** **Investigational Hardware Prototype**.
- **Audit Findings:** Automated validation across 39 physical MAX30102 recording sessions demonstrates that the SQI safety gate correctly suppresses motion artifacts. 100% of unstable or motion-corrupted sessions are safely prevented from triggering false AI alarms.
- **Empirical Hardware Sessions (Oct 3, 2026):** Verified across 9 real hardware finger-sensor sessions in `recordings/new_session/` achieving average pulse rate MAE of 1.67 BPM against reference smartwatch ground truth, with 100% window reliability under stable resting contact.

---

## Ethical & Regulatory Considerations
- **Non-Diagnostic Nature:** Explicitly labeled on all backend APIs and frontend dashboards.
- **Explainability:** All predictions accompanied by class probability distributions and SQI confidence scores.
- **Provenance:** Every telemetry update is tagged with its provenance (`LIVE_HARDWARE`, `MIMIC_ICU_REPLAY`, `RECORDED_REPLAY`, or `SIMULATION`).
- **Data Governance:** No raw MIMIC-III patient waveforms or identifiable hospital data are distributed publicly; access requires credentialed PhysioNet authorization under the MIMIC-III Data Use Agreement.
