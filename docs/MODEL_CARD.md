# 🫀 CardioTwin Sentinel Model Card: Multi-Modal Cardiovascular Digital Twin & Pulse Screening System

**Model Card Version:** 4.1.0-sentinel  
**Date:** October 2026  
**Format:** Mitchell et al. (FAT* 2019) / Google Responsible AI Model Card Standard  
**Authors:** Harshvardhan & CardioTwin Sentinel Engineering Team  
**Evaluation Standard:** Patient-Isolated Stratified GroupKFold (Zero Data Leakage)  

---

## 1. Model Details

- **Model Name:** CardioTwin Sentinel Dual-Modality Arrhythmia Screening Engine
- **Model Version:** 4.1.0-sentinel (Digital Twin Challenge 2026 Release)
- **Model Status:** Investigational Decision-Support Prototype (Non-Diagnostic)
- **Core Architectures:**
  1. **Modality A (Classical Super Ensemble):** Soft-voting ensemble combining **XGBoost Classifier**, **Random Forest**, and **Extra Trees** trained on 27 extracted time, frequency, morphological, and signal-quality biomarkers.
  2. **Modality B (Deep Learning Champion):** **Inception-1D CNN** featuring 4 multi-scale convolution branches (kernel sizes 3, 7, 15, 31) with residual skip connections operating directly on 100 Hz raw photoplethysmogram waveforms (1,000 samples / 10s).
- **Target Classes (8):** `Normal`, `Tachycardia`, `Bradycardia`, `AFib` (Atrial Fibrillation), `Cardiac_Paced`, `V_Tachycardia` (Ventricular Tachycardia), `V_Flutter_Fib` (Ventricular Flutter/Fibrillation), `Asystole`.
- **Training Cohort:** **2,271 unique clinical patients across 4,683 standardized 10-second windows**:
  - **MIMIC-III-Ext-PPG v1.1.0:** 2,000 unique ICU patients (400 AFib, 400 Bradycardia, 400 Tachycardia, 400 Paced, 400 Normal controls) under PhysioNet Credentialed Data Use Agreement.
  - **PhysioNet CinC 2015:** 231 ICU records (1,890 verified true arrhythmia segments: VT, VFib, Asystole, Brady, Tachy).
  - **BUT PPG v2.0:** 39 subjects (792 expert-annotated smartphone recordings with optical motion noise).
  - **BIDMC PPG:** Hospital ICU baseline.

---

## 2. Intended Use & Clinical Scope

- **Primary Intended Use:**
  1. Establishment of personal empirical resting pulse baselines via seated 2-minute calibration.
  2. Real-time identification of acute and sustained departures from personalized baseline stability.
  3. Non-diagnostic computer-assisted screening of cardiac rhythm patterns to prioritize clinician review.
  4. Clinical simulation of preventive cardiometabolic interventions (antihypertensive and lipid-lowering therapies) using a South Asian-recalibrated ($1.45\times$) Framingham Cox proportional hazards model.
- **Out-of-Scope & Prohibited Uses:**
  - Standalone clinical diagnosis without confirmatory 12-lead electrocardiography (ECG).
  - Primary diagnosis of acute myocardial infarction, ST elevation/depression, or bundle branch blocks.
  - Autonomous titration or initiation of prescription pharmaceuticals.
  - Resuscitation or emergency defibrillation decision-making.

---

## 3. Rigorous Evaluation Protocol (Leak-Free Grouped CV)

A pervasive failure in commercial and hackathon health ML is random window-level splitting: slices of the same patient's continuous recording appear in both training and test partitions, falsely inflating Macro-F1 scores into the 80–95% range.

**CardioTwin Sentinel enforces strict patient isolation:**
1. **Patient-Level Grouping:** Evaluated strictly using `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` grouped on unique patient identifiers (`patient_ids`).
2. **Zero Patient Overlap:** A patient evaluated in the held-out validation fold is **never** observed in the training fold.
3. **Train-Only Preprocessing:** `StandardScaler` transformations are fit strictly on training patients per fold.

### 5-Fold Stratified Grouped-CV Benchmark (2,271 Patients)
| Rank | Architecture | Input Representation | Macro-F1 (8 Classes) | Accuracy | Model Parameters | Status |
|:---:|:---|:---|:---:|:---:|:---:|:---|
| **1** | **Inception-1D CNN** | Raw 100 Hz Waveform (1000 samples) | **51.41%** | **74.05%** | 393,224 | **DEEP LEARNING CHAMPION** |
| 2 | **ResNet-1D** | Raw 100 Hz Waveform (1000 samples) | 50.81% | 56.22% | 181,448 | Strong Runner-Up |
| 3 | **Standard 1D-CNN** | Raw 100 Hz Waveform (1000 samples) | 48.72% | 54.13% | 172,104 | Baseline CNN |
| **4** | **Super Ensemble (XGB+RF+ET)** | 27 Engineered Biomarkers | **48.00%** | **65.98%** | Tabular Bundle | **CLASSICAL CHAMPION** |
| 5 | **Extra Trees** | 27 Engineered Biomarkers | 47.32% | 56.87% | Tree Ensemble | Fast Sub-Sampling |
| 6 | **Random Forest** | 27 Engineered Biomarkers | 47.13% | 56.14% | Tree Ensemble | Outlier Resilient |
| 7 | **XGBoost (Standalone)** | 27 Engineered Biomarkers | 46.71% | 56.97% | Boosted Trees | Gradient Boosting Baseline |
| 8 | **HistGradientBoosting** | 27 Engineered Biomarkers | 46.68% | 55.65% | Tree Ensemble | Histogram Binned |
| 9 | **CRNN-BiLSTM** | Raw 100 Hz Waveform (1000 samples) | 45.04% | 51.40% | 224,968 | Recurrent Hybrid |
| 10 | **MLP Neural Net** | 27 Engineered Biomarkers | 44.36% | 57.08% | 65,480 | Dense Feedforward |

---

## 4. Dataset Source-Confounding Audit (Domain Bias Transparency)

To prevent overconfidence, CardioTwin Sentinel conducted a systematic cross-dataset provenance audit (`scripts/audit_source_confounding.py`):

```
DATASET × CLASS CONTINGENCY MATRIX (WINDOW COUNTS):
source         BIDMC  BUT  CinC  MIMIC   All
class                                       
AFib               0    0     0    400   400  (100.0% MIMIC) -> Single-Source Confounded
Asystole           0    0   204      0   204  (100.0% CinC)  -> Single-Source Confounded
Bradycardia        0    0   234    400   634  (Distributed MIMIC + CinC)
Cardiac_Paced      0    0     0    400   400  (100.0% MIMIC) -> Single-Source Confounded
Normal             1  792     0    400  1193  (Distributed BUT + MIMIC)
Tachycardia        0    0   648    400  1048  (Distributed CinC + MIMIC)
V_Flutter_Fib      0    0    72      0    72  (100.0% CinC)  -> Single-Source Confounded
V_Tachycardia      0    0   732      0   732  (100.0% CinC)  -> Single-Source Confounded
All                1  792  1890   2000  4683
```

### Critical Findings:
1. **Single-Source Confounding:** 100% of Ventricular Tachycardia, Ventricular Flutter/Fib, and Asystole instances originate from PhysioNet CinC 2015 ICU alarms.
2. **Domain Fingerprint Test:** An ExtraTrees source-classifier trained to predict dataset origin achieves **77.08% accuracy (81.30% Balanced Accuracy)** from 27 PPG features alone.
3. **Clinical Mitigation:** Rather than claiming global generalizability, CardioTwin Sentinel explicitly flags these conditions in its **Evidence Ledger** as requiring mandatory ECG verification.

---

## 5. Explainable AI: SHAP Feature Attribution

Using `shap.TreeExplainer` on the Classical Super Ensemble (`scripts/generate_shap_explanations.py`), predictions are attributed to 27 physiological biomarkers:

| Rank | Biomarker | Mean \|SHAP\| | Primary Clinical Role |
|:---:|:---|:---:|:---|
| 1 | `bpm` | **0.4281** | Primary pulse rate separating bradycardia (<50) from tachycardia (>100) |
| 2 | `rr_mean` | **0.2814** | Mean inter-beat interval duration |
| 3 | `rr_cv` | **0.2450** | Coefficient of variation in RR intervals; key driver for Atrial Fibrillation |
| 4 | `rmssd` | **0.1983** | Parasympathetic vagal tone index; suppresses sharply during stress / tachycardia |
| 5 | `rr_range` | **0.1742** | Dynamic interval dispersion across 10-second observation window |
| 6 | `sdnn` | **0.1520** | Total autonomic nervous system variability |
| 7 | `sqi` | **0.1340** | Decoupled signal quality gate metric |
| 8 | `sig_kurt` | **0.1180** | Morphological peak sharpness |

---

## 6. Personal Baseline Governance

CardioTwin Sentinel replaces population defaults (such as assuming a universal 72 BPM resting baseline) with a strict empirical governance protocol (`backend/personal_baseline.py`):
1. **Mandatory Calibration:** Requires at least 6 valid, post-settling 10-second windows during seated rest.
2. **Uncalibrated State:** Returns `instability_score: null` with status `"Personal baseline required"`.
3. **Robust Metrics:** Uses Median and Median Absolute Deviation (MAD), resisting distortion from momentary PAC/PVC outliers.
4. **Invalidation Lifecycle:** Baselines expire after 30 days or immediately upon device ID mismatch or sensor reconfiguration (LED current or sample rate changes).

---

## 7. Decoupled 5-Part Signal Reliability Gate

- **Physical Quality Checks:**
  - Flatline / Finger-off ($<20\,\text{k}$ ADC ceiling) $\rightarrow$ Blocks AI screening (`FINGER_OFF`)
  - Transimpedance Amplifier Saturation ($>260\,\text{k}$ ADC ceiling) $\rightarrow$ Blocks AI screening (`SENSOR_SATURATED`)
  - High Timing Jitter (>20% timestamp variance) $\rightarrow$ Blocks AI screening (`POOR_TIMING`)
- **Physiological Observations:**
  - Rates <40 or >180 BPM pass physical quality but trigger `EXTREME_RATE` clinical recheck flags.
  - AFib / irregular pulses are **not** discarded as motion; they are routed to the Instability Engine.

---

## 8. Quantitative Hardware Validation

- **Hardware Platform:** ESP32-WROOM-32D Dual-Core (FreeRTOS) + MAX30102 Infrared Sensor.
- **Timing Integrity:** 100.0 Hz measured optical sampling frequency with hardware microsecond ISR timing ($\pm 0.4$ ms jitter).
- **Physical Volunteer Sessions:** Validated across 10+ recording sessions; achieved resting BPM Mean Absolute Error (MAE) of **$\le 1.8$ BPM** against simultaneous reference ground truth.
- **False Alarm Immunity:** Zero false persistent alarms observed across 49 automated target validation test scenarios (`tests/test_instability_target_validation.py`).

---

*This Model Card adheres to the ACM FAccT and IEEE standards for clinical decision-support transparency.*
