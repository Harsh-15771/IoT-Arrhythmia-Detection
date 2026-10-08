# 🫀 CardioTwin Sentinel — Unified AI Model & Data Card

**Model Card & Evaluation Protocol:** FAT* / Google Responsible AI Standard  
**Version:** 4.1.0-sentinel | **Lead Author:** Harsh Mishra (Root Access)  
**Standard:** Patient-Isolated Stratified GroupKFold (Zero Data Leakage)  
**Clinical Scope:** Investigational Decision-Support Prototype (Non-Diagnostic)

---

## 1. System Architectures & Model Overview

CardioTwin Sentinel employs an honest **Dual-Modality Architecture** combining classical physiological signal processing with deep 1D convolutional neural networks:

- **Modality A (Classical Super Ensemble):** Soft-voting ensemble of **XGBoost Classifier**, **Random Forest**, and **Extra Trees** trained on 27 extracted time, frequency, morphological, and pulse-rate variability biomarkers.
- **Modality B (Deep Learning Champion):** **Inception-1D CNN** (393,224 parameters, 1.61 MB) featuring 4 parallel multi-scale convolutional branches (kernel sizes 3, 7, 15, 31) with residual skip connections operating on raw 100 Hz photoplethysmogram waveforms (1,000 samples / 10s window).
- **Nested Fusion Layer:** Dynamically balances predictions via inner-fold optimization: $0.38 \times \text{Classical} + 0.62 \times \text{Deep Learning}$.
- **Target Rhythm Classes (8):** `Normal`, `Tachycardia`, `Bradycardia`, `AFib` (Atrial Fibrillation), `Cardiac_Paced`, `V_Tachycardia`, `V_Flutter_Fib`, `Asystole`.

---

## 2. Training Cohort & Data Provenance

The unified telemetry training cohort comprises **4,683 standardized 10-second windows** across **2,271 unique clinical individuals** from four established databases:

| Database / Source | Records / Patients | Windows | Primary Clinical Role & Ground Truth | Governance |
|:---|:---:|:---:|:---|:---|
| **MIMIC-III-Ext-PPG v1.1.0** (PhysioNet) | **2,000 patients** | 2,000 | Clinical ICU Telemetry (400 AFib, 400 Brady, 400 Tachy, 400 Paced, 400 Normal) | PhysioNet Credentialed DUA (Exited from repo) |
| **PhysioNet CinC 2015** | **231 records** | 1,890 | Expert-adjudicated true alarms (VT, VFib, Asystole, Brady, Tachy) | Open PhysioNet Contributor License |
| **BUT PPG v2.0** (Brno Univ.) | **39 subjects** | 792 | Wearable optical motion noise & smartphone PPG baseline drift | Open Research License |
| **BIDMC PPG** | **1 patient** | 1 | Hospital ICU baseline | Open Data Commons |
| **Total Cohort** | **2,271 unique patients** | **4,683 windows** | Standardized to 100 Hz (1,000 samples/window) | Patient-level grouping (`patient_ids`) |

### Class Ground-Truth Distribution
1. **Normal Sinus Rhythm:** 1,193 windows (25.5%)
2. **Sinus Tachycardia:** 1,048 windows (22.4%)
3. **Ventricular Tachycardia (VT):** 732 windows (15.6%)
4. **Sinus Bradycardia:** 634 windows (13.5%)
5. **Atrial Fibrillation (AFib):** 400 windows (8.5%)
6. **Cardiac Paced & Blocks:** 400 windows (8.5%)
7. **Asystole:** 204 windows (4.4%)
8. **Ventricular Flutter / Fib:** 72 windows (1.5%)

> **Data Governance Guarantee:** In strict adherence to the **PhysioNet MIMIC-III Data Use Agreement (DUA)**, no raw clinical `.hea`, `.dat`, or identifiable patient recordings are stored in this public repository. All raw data paths are excluded via [`.gitignore`](../.gitignore).

---

## 3. Leak-Free Evaluation Protocol & Performance Matrix

CardioTwin strictly enforces **Patient-Isolated Stratified GroupKFold** (`n_splits=5`, grouped on `patient_ids`). Windows from the same patient never span train and test sets. All feature scalers are fit strictly on training partitions.

### Canonical Nested Dual-Modality Benchmark (5 Outer Folds)

| System Configuration | Input Modality | Macro-F1 (8 Classes) | Balanced Accuracy | Accuracy | 95% Confidence Interval |
|:---|:---|:---:|:---:|:---:|:---:|
| Standalone Random Guess Baseline | Uniform Random | 12.50% | 12.50% | 12.50% | — |
| Standalone Classical Super Ensemble | 27 Hand-Crafted Biomarkers | 48.00% | 50.21% | 58.32% | $\pm 4.8\%$ |
| Standalone Inception-1D CNN | Raw 100 Hz Waveform (1000 samples) | 51.81% | 56.72% | 56.37% | $\pm 5.1\%$ |
| **🏆 Honest Nested Dual-Modality Fusion** | **Waveforms + Biomarkers ($0.38\text{ Classical} + 0.62\text{ DL}$)** | **53.92%** | **57.46%** | **59.21%** | **$54.09\% \pm 5.45\%$** |

### Deep Learning Architecture Tournament (Identical 5-Fold Grouped Splits)

| Rank | Architecture | Input Representation | Macro-F1 | Accuracy | Parameters | Inference / CPU |
|:---:|:---|:---|:---:|:---:|:---:|:---:|
| 🥇 | **Inception-1D CNN** | Raw 100 Hz (4 branches: 3, 7, 15, 31) | **51.81%** | **56.37%** | 393,224 | **~4.2 ms** |
| 🥈 | **ResNet-1D** | Raw 100 Hz (Residual blocks) | 49.44% | 54.96% | 181,448 | ~3.8 ms |
| 🥉 | **Standard 1D-CNN** | Raw 100 Hz (Sequential convolutions) | 49.16% | 54.30% | 172,104 | ~3.1 ms |
| 4 | **CRNN-BiLSTM** | Raw 100 Hz (Conv + Bidirectional LSTM) | 45.04% | 51.46% | 215,680 | ~9.6 ms |

### Per-Class Performance Breakdown (Dual Fusion on 4,683 Windows)

| Rhythm Class | Precision | Recall | F1-Score | Support | Clinical Significance |
|:---|:---:|:---:|:---:|:---:|:---|
| **Normal** | 95.73% | 67.73% | **79.33%** | 1,193 | High specificity preserves clinician trust |
| **Bradycardia** | 64.94% | 70.98% | **67.82%** | 634 | High recall prevents missing hemodynamically slow rhythms |
| **Tachycardia** | 61.81% | 69.18% | **65.29%** | 1,048 | Reliable identification of sustained tachyarrhythmias |
| **AFib** | 46.70% | 63.75% | **53.91%** | 400 | Sensitivity prioritized for silent atrial fibrillation triage |
| **Asystole** | 39.75% | 61.76% | **48.37%** | 204 | Critical low-perfusion capture |
| **V_Flutter_Fib** | 42.86% | 54.17% | **47.85%** | 72 | Rapid life-threatening ventricular flutter |
| **Cardiac Paced** | 28.11% | 47.50% | **35.32%** | 400 | Difficult morphology without sharp electrical pacer spike |
| **V_Tachycardia** | 52.48% | 24.59% | **33.49%** | 732 | Hardest single-lead optical classification; triggers ECG review |

---

## 4. Explainable AI: SHAP Feature Attributions

Using `shap.TreeExplainer` across the 27 extracted pulse biomarkers, predictions are explained via game-theoretic Shapley attributions:

### Global Top-10 Biomarker Ranking

| Rank | Biomarker | Mean \|SHAP\| | Primary Clinical & Physiological Role |
|:---:|:---|:---:|:---|
| 1 | `sig_skew` | **0.4895** | Pulse wave asymmetry & systolic deflection rate |
| 2 | `peak_amp_mean` | **0.4271** | Mean pulsatile optical pulse amplitude (vascular volume shift) |
| 3 | `rr_mean` | **0.3646** | Inter-beat interval duration; inverse of instantaneous pulse rate |
| 4 | `bpm` | **0.3524** | Primary rate separator (Brady <50, Normal 50–100, Tachy >100) |
| 5 | `pnn50` | **0.2201** | Fraction of consecutive RR differences >50ms; sensitive to AFib irregularity |
| 6 | `rr_min` | **0.1968** | Minimum RR interval within the 10-second observation window |
| 7 | `pnn20` | **0.1861** | Fine-grained short-term autonomic interval dispersion |
| 8 | `rr_max` | **0.1825** | Compensatory pauses and post-ectopic intervals |
| 9 | `rr_skew` | **0.1798** | Rhythm skewness across window |
| 10 | `rmssd` | **0.1766** | Parasympathetic vagal tone; drops sharply in autonomic distress |

### Rhythm-Specific Attributions
- **AFib:** Driven by elevated `rr_cv`, `pnn50`, and `rmssd` reflecting irregular-irregular chaotic rhythm.
- **Tachycardia:** Driven by compressed `rr_mean`, `rr_min`, and elevated `bpm`.
- **Normal Sinus:** Balanced intermediate `bpm` with non-chaotic `rr_cv` and consistent dicrotic morphology.

---

## 5. Dataset Provenance & Visual Audits

### Cross-Dataset Source Confounding Audit
To identify potential hospital or acquisition signatures, CardioTwin conducted a systematic source provenance audit:

```
DATASET × CLASS CONTINGENCY MATRIX (WINDOWS):
source         BIDMC  BUT  CinC  MIMIC   All
class                                       
AFib               0    0     0    400   400  (100% MIMIC)  -> Single-Source Confounded
Asystole           0    0   204      0   204  (100% CinC)   -> Single-Source Confounded
Bradycardia        0    0   234    400   634  (Distributed MIMIC + CinC)
Cardiac_Paced      0    0     0    400   400  (100% MIMIC)  -> Single-Source Confounded
Normal             1  792     0    400  1193  (Distributed BUT + MIMIC)
Tachycardia        0    0   648    400  1048  (Distributed CinC + MIMIC)
V_Flutter_Fib      0    0    72      0    72  (100% CinC)   -> Single-Source Confounded
V_Tachycardia      0    0   732      0   732  (100% CinC)   -> Single-Source Confounded
```

- **Domain Fingerprint Test:** An ExtraTrees classifier predicting dataset origin from the 27 biomarkers achieves **77.08% Accuracy (81.30% Balanced Accuracy)**.
- **Scientific Impact:** Models trained on single-hospital datasets learn acquisition hardware signatures rather than pure electrophysiology. CardioTwin transparently discloses this domain boundary in the **Evidence Ledger** and frames rhythm outputs as screening guidance rather than standalone diagnoses.

### Visual Waveform Morphology Audit

| Rhythm Class | Total Windows | Sampled | Mean Peaks / 10s | Implied BPM | Mean SNR | Morphological Characteristic |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **Normal** | 1,193 | 25 | 22.0 | 132.2 | 27.11 dB | Consistent dicrotic notch morphology |
| **Bradycardia** | 634 | 25 | 9.3 | 55.7 | 41.74 dB | Elongated inter-beat intervals |
| **Tachycardia** | 1,048 | 25 | 15.5 | 92.9 | 34.47 dB | Rapid systolic recurrence, short runoff |
| **AFib** | 400 | 25 | 14.0 | 84.0 | 39.39 dB | Chaotic beat-to-beat amplitude and interval variation |
| **Asystole** | 204 | 25 | 10.2 | 61.2 | 29.97 dB | Severely attenuated perfusion signals |
| **V_Flutter_Fib**| 72 | 25 | 9.5 | 56.9 | 38.07 dB | Complex irregular multi-peaked wave |
| **V_Tachycardia** | 732 | 25 | 13.4 | 80.2 | 37.31 dB | Rapid monomorphic pulsatile deflections |

---

## 6. Personal Baseline & Signal Gating Guardrails

1. **2-Minute Seated Baseline Protocol:** Requires at least 6 valid post-settling 10-second windows. Replaces fixed population assumptions with personal Median and MAD. If uncalibrated, instability score returns `null` with `"Personal baseline required"`.
2. **Decoupled 5-Part Signal Gate:**
   - *Physical Failures (Blocks AI):* Flatline / Finger-off ($<20\text{k}$ ADC ceiling), saturation ($>260\text{k}$ ADC ceiling), sample timing jitter (>20% timestamp variance).
   - *Physiological Irregularities (Passes to AI):* Extreme heart rates (<40 or >180 BPM) and irregular pulse arrival times (AFib) pass physical gates for downstream evaluation.
3. **Operational Validation:** 100% finger-off rejection, zero persistent false alarms across 49 automated target validation scenarios (`tests/test_instability_target_validation.py`), and $\le 2.0$ BPM MAE against reference pulse ground truth.
