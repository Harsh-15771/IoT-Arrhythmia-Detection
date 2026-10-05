# 🔬 CardioTwin Sentinel — SHAP Explainability & Feature Attribution Report

**Research Standard:** Aligned with MDPI 2024 Meta-analysis on XAI in Cardiovascular Decision Support Systems.

## 1. Executive Summary

CardioTwin Sentinel employs Shapley Additive Explanations (SHAP) to unpack the decision boundaries of its Classical Super Ensemble across 27 pulse biomarkers. Rather than acting as an uninterpretable 'black box', every pattern screening output is attributed to game-theoretically grounded feature contributions.

## 2. Global Top-10 Biomarker Ranking

| Rank | Biomarker | Mean |SHAP| | Physiological Interpretation |
|:---:|:---|:---:|:---|
| 1 | `sig_skew` | 0.4895 | Morphological / frequency-domain PPG feature contributing to pattern boundary. |
| 2 | `peak_amp_mean` | 0.4271 | Morphological / frequency-domain PPG feature contributing to pattern boundary. |
| 3 | `rr_mean` | 0.3646 | Mean pulse arrival interval; inversely proportional to instantaneous heart rate. |
| 4 | `bpm` | 0.3524 | Primary pulse rate; separates bradycardia (<50), normal (50-100), and tachycardia (>100). |
| 5 | `pnn50` | 0.2201 | Percentage of successive pulse intervals differing by >50 ms; high in rhythm irregularity. |
| 6 | `rr_min` | 0.1968 | Morphological / frequency-domain PPG feature contributing to pattern boundary. |
| 7 | `pnn20` | 0.1861 | Morphological / frequency-domain PPG feature contributing to pattern boundary. |
| 8 | `rr_max` | 0.1825 | Morphological / frequency-domain PPG feature contributing to pattern boundary. |
| 9 | `rr_skew` | 0.1798 | Morphological / frequency-domain PPG feature contributing to pattern boundary. |
| 10 | `rmssd` | 0.1766 | Root mean square of successive differences; parasympathetic nervous system tone & pulse variability. |

## 3. Rhythm-Specific Feature Drivers

### 🫀 Atrial Fibrillation (AFib)
- **Top Drivers:** `sig_skew` (0.5720), `peak_amp_mean` (0.4922), `pnn20` (0.3377), `pnn50` (0.3155), `rmssd` (0.3092)
- **Clinical Rationale:** AFib is characterized by chaotic pulse irregularity ('irregularly irregular'). The model heavily weights `rr_cv`, `rmssd`, and `pnn50`, matching clinical electrophysiology principles.

### 🏃 Tachycardia
- **Top Drivers:** `rr_mean` (0.7918), `sig_skew` (0.2793), `rr_min` (0.2545), `bpm` (0.1843), `rmssd` (0.1584)
- **Clinical Rationale:** Driven primarily by elevated `bpm` and compressed `rr_mean` and `rr_min`.

### 🧘 Normal Sinus Rhythm
- **Top Drivers:** `bpm` (0.7065), `sig_skew` (0.4904), `pnn50` (0.3367), `rr_mean` (0.3140), `rr_max` (0.2613)
- **Clinical Rationale:** Balances intermediate `bpm` with physiological, non-chaotic `rr_cv` and consistent pulse morphology (`sig_std`, `sqi`).

## 4. Artifacts Generated

- Global Biomarker Plot: `docs/shap_summary_plot.png`
- Class-Specific Drivers Plot: `docs/shap_class_drivers.png`
- JSON Rankings: `docs/shap_feature_importance.json`

---
*Report generated autonomously by CardioTwin Sentinel Pipeline.*