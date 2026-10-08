# 📊 CardioTwin Sentinel — Verified Performance Matrix

**Evaluation Standard:** Patient-Isolated Stratified GroupKFold (Zero Data Leakage)  
**Cohort:** 2,271 Patients | 4,683 Standardized 10-Second Windows | 8 Rhythmic Classes  

---

## 1. Standalone Model Benchmarks (5-Fold Stratified Grouped CV)

All models evaluated strictly on held-out patients who never appear in the training partition of any fold:

| Model | Macro-F1 (8 Classes) | Accuracy | Evaluation Protocol |
|:---|:---:|:---:|:---|
| Random Guess Baseline | 12.50% | 12.50% | Uniform random probability |
| Classical Super Ensemble (XGB+RF+ET) | **48.00%** | 58.32% | 5-Fold StratifiedGroupKFold (Patient-Isolated) |
| Inception-1D CNN (Champion) | **51.81%** | 56.37% | 5-Fold StratifiedGroupKFold (Patient-Isolated) |

---

## 2. Nested Dual-Modality Fusion (Canonical Benchmark)

Nested cross-validation where fusion weights (38% Classical + 62% Deep Learning) are discovered strictly on inner folds, preventing meta-parameter leakage:

| Metric | Value | Interpretation |
|:---|:---:|:---|
| **Macro-F1** | **53.92%** | Primary metric across all 8 classes |
| **Accuracy** | **59.21%** | Raw sample accuracy |
| **Balanced Accuracy** | **57.46%** | Unweighted average recall |
| **Weighted F1** | **59.70%** | Frequency-weighted F1 |
| **95% Confidence Interval** | **$54.09\% \pm 5.45\%$** | Empirical confidence across 5 outer folds |
| **Optimal Fusion Weights** | **38% Classical + 62% DL** | Mean optimal blend weights |
| **Validation Scheme** | **Nested 5-Fold StratifiedGroupKFold** | Zero patient overlap between partitions |
| **Total Patients** | **2,271** | Verified PhysioNet MIMIC-III + CinC 2015 + BUT PPG |
| **Total Windows** | **4,683** | Standardized 10-second segments @ 100 Hz |

---

## 3. Deep Learning Architecture Tournament

Tournament evaluated under identical 5-fold patient-isolated splits:

| Rank | Architecture | Macro-F1 | Accuracy | Parameters | Training Time |
|:---:|:---|:---:|:---:|:---:|:---:|
| 🥇 | **Inception-1D** | **51.81%** | **56.37%** | 393,224 | 105s |
| 🥈 | **ResNet-1D** | 49.44% | 54.96% | 181,448 | 77s |
| 🥉 | **Standard 1D-CNN** | 49.16% | 54.30% | 172,104 | 60s |
| 4 | **CRNN-BiLSTM** | 45.04% | 51.46% | 215,680 | 40s |

---

## 4. Per-Class Performance (Dual Fusion)

| Rhythm Class | Precision | Recall | F1-Score | Support (Windows) | Clinical Notes |
|:---|:---:|:---:|:---:|:---:|:---|
| **AFib** | 46.70% | 63.75% | 53.91% | 400 | Strong recall prioritizes screening sensitivity |
| **Asystole** | 39.75% | 61.76% | 48.37% | 204 | Critical low-amplitude event capture |
| **Bradycardia** | 64.94% | 70.98% | 67.82% | 634 | High precision and recall on low-rate rhythms |
| **Cardiac Paced** | 28.11% | 47.50% | 35.32% | 400 | Challenging morphological variation without ECG spike |
| **Normal** | 95.73% | 67.73% | 79.33% | 1,193 | High specificity preserves clinician trust |
| **Tachycardia** | 61.81% | 69.18% | 65.29% | 1,048 | Reliable detection of sustained tachyarrhythmia |
| **V Flutter/Fib** | 42.86% | 54.17% | 47.85% | 72 | Rare critical emergency rhythm |
| **V Tachycardia** | 52.48% | 24.59% | 33.49% | 732 | Hardest single-lead optical classification |

> **Honest Disclosure:** These are leak-free, patient-isolated cross-validation numbers — not inflated train-set metrics. We report what the model actually achieves on unseen patients.

---

## 5. Operational Safety Metrics

| Metric | Result | Mechanism |
|:---|:---:|:---|
| **Finger-Off Rejection** | 100% | Optical threshold & standard deviation gating |
| **Motion False Alarms** | 0 persistent alarms | Multi-window consensus & SQI threshold ($<0.40$) |
| **Resting BPM MAE** | $\le 2.0$ BPM | Peak detection validated against ground-truth annotations |
| **Automated Tests** | 49/49 Passing | Regression test suite covering signal, baseline, and APIs |
