# 🧠 CardioTwin Sentinel — Key Engineering Decisions & Rationale

This document details the architectural choices, mathematical foundations, and clinical design tradeoffs underlying CardioTwin Sentinel.

---

## 1. Why Dual-Modality Fusion Over a Single Model?

**Decision:** Blend a classical biomarker ensemble (27 hand-crafted features) with a deep Inception-1D convolutional network via dynamic probability fusion.

**Rationale:**
- **Complementary inductive biases.** Classical features capture inter-beat timing statistics ($\text{RMSSD}$, $\text{pNN50}$, $\text{RR-CV}$, spectral LF/HF) that summarize autonomic cardiac physiology. The CNN captures raw micro-morphological pulse wave deflections that hand-crafted features miss.
- **Measurable empirical improvement.** Dual fusion achieves **53.92% Macro-F1** vs. **51.81%** (CNN alone) and **48.00%** (classical alone) — a statistically verified improvement across 5 nested outer folds.
- **Leak-free parameter selection.** Fusion weights (38% Classical + 62% Deep Learning) are learned per outer fold via inner-fold grid search; no single fixed weight is cherry-picked.

---

## 2. Why Inception-1D Over Transformers or LSTMs?

**Decision:** Multi-scale 1D Inception convolutional architecture with 4 parallel branches.

**Rationale:**
- **Multi-scale temporal patterns.** Cardiac rhythms manifest at different temporal scales (fast systolic rises, dicrotic notches, multi-beat respiratory sinus arrhythmia). Inception modules process multiple kernel lengths (3, 7, 15, 31) concurrently.
- **Empirically validated.** Inception-1D won the architecture tournament (51.81% Macro-F1 vs. 50.81% ResNet-1D, 49.16% Standard CNN, and 45.04% CRNN-BiLSTM) under identical patient-isolated evaluation.
- **Ultra-lightweight edge footprint.** 393,224 parameters (1.61 MB) — fast CPU inference (~4.2 ms per 10s window) suitable for low-cost primary health centre servers without GPU acceleration.

---

## 3. Why Personal Baseline Instead of Population Norms?

**Decision:** Every physiological instability score is anchored to the patient's own empirical 2-minute seated resting calibration.

**Rationale:**
- **72 BPM is not universal.** An endurance athlete's resting pulse is 48 BPM; an elderly patient with hypertension may rest at 84 BPM. Rigid population thresholds generate chronic false alarms for both.
- **PPG physiological boundary.** Pulse Rate Variability (PRV) from optical photoplethysmography agrees best with true electrocardiographic HRV at seated rest. The 2-minute calibration respects this physiological reality.
- **Evidence Ledger refusal.** If calibration has not been performed, the system displays `"Awaiting a personal baseline"` and returns `null` for instability — refusing to fabricate an uncalibrated score.

---

## 4. Why Median + MAD Instead of Mean + Standard Deviation?

**Decision:** Robust non-parametric statistics (Median and Median Absolute Deviation) for baseline establishment and departure scoring.

**Rationale:**
- **Outlier resistance.** A transient motion artifact spike producing an erroneous 240 BPM reading heavily distorts sample mean and variance. The median and MAD are statistically unaffected (50% breakdown point).
- **Correct scaling for biological asymmetry.** For normal distributions, $\text{MAD} \times 1.4826 \approx \sigma$. However, physiological pulse distributions are inherently skewed; MAD handles asymmetric tails without false alarms.
- **Clinical appropriateness.** An alert must represent persistent physiological departure across multiple consecutive windows, not sensor noise.

---

## 5. Why Framingham + 1.45× South Asian Recalibration?

**Decision:** Sex-specific Framingham General CVD Cox proportional hazards model recalibrated with a $1.45\times$ South Asian multiplier.

**Rationale:**
- **Most validated global framework.** Framingham has 50+ years of prospective epidemiological validation across hundreds of thousands of patient-years.
- **Known South Asian risk disparity.** South Asians experience myocardial infarction 10–15 years earlier than Western cohorts with higher premature coronary mortality at identical baseline risk factors (INTERHEART, UK Biobank, QRISK3).
- **Guideline alignment.** ESC and AHA/ACC consensus recommendations recommend an ethnic risk multiplier between $1.3\times$ and $1.5\times$ for South Asian populations. CardioTwin applies $1.45\times$ and explicitly documents the adjustment.
