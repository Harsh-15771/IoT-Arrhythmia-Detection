# 🔬 CardioTwin v4 — Source Confounding & Dataset Provenance Audit

**Audit Date:** March 2026  
**Objective:** Investigate whether rhythm labels correlate strongly or exclusively with dataset source (CinC 2015, MIMIC-II, BUT-PPG, BIDMC), creating dataset domain signatures.

---

## 1. Dataset × Class Windows Contingency Matrix

| Rhythm Class | CinC 2015 | MIMIC-II | BUT-PPG | BIDMC | Total Windows | Primary Source % | Status |
|---|---|---|---|---|---|---|---|
| **AFib** | 0 | 400 | 0 | 0 | **400** | 100.0% (MIMIC) | CRITICALLY CONFOUNDED (Single Source) |
| **Asystole** | 204 | 0 | 0 | 0 | **204** | 100.0% (CinC) | CRITICALLY CONFOUNDED (Single Source) |
| **Bradycardia** | 234 | 400 | 0 | 0 | **634** | 63.1% (MIMIC) | Distributed Across Sources |
| **Cardiac_Paced** | 0 | 400 | 0 | 0 | **400** | 100.0% (MIMIC) | CRITICALLY CONFOUNDED (Single Source) |
| **Normal** | 0 | 400 | 792 | 1 | **1,193** | 66.4% (BUT) | Distributed Across Sources |
| **Tachycardia** | 648 | 400 | 0 | 0 | **1,048** | 61.8% (CinC) | Distributed Across Sources |
| **V_Flutter_Fib** | 72 | 0 | 0 | 0 | **72** | 100.0% (CinC) | CRITICALLY CONFOUNDED (Single Source) |
| **V_Tachycardia** | 732 | 0 | 0 | 0 | **732** | 100.0% (CinC) | CRITICALLY CONFOUNDED (Single Source) |

---

## 2. Source-Classification Test (Domain Fingerprinting)

To determine whether individual datasets have distinct physiological or sensor acquisition signatures that allow a model to recognize the origin rather than the physiology:

- **Source Predictor:** ExtraTreesClassifier (Grouped 5-Fold CV on 27 Biomarkers)
- **Overall Source Accuracy:** **77.08%**
- **Balanced Accuracy:** **81.30%**

### Per-Dataset Classification Report:
| Dataset | Precision | Recall | F1-Score | Support |
|---|---|---|---|---|
| **BUT** | 99.7% | 99.9% | 99.8% | 792.0 |
| **CinC** | 80.8% | 56.7% | 66.6% | 1,890.0 |
| **MIMIC** | 68.1% | 87.4% | 76.6% | 2,000.0 |

---

## 3. Key Findings & Scientific Implications

1. **Severe Source Exclusivity**:
   - Several arrhythmia classes originate predominantly or exclusively from single hospital ICU databases (e.g. CinC 2015 for alarm-triggered arrhythmias, BUT-PPG for clean normals).
   - This creates an inherent risk of **domain confounding**, where machine learning models may inadvertently learn sensor-specific or hospital-specific sampling characteristics rather than generalizable electrophysiological patterns.

2. **Strong Domain Fingerprints**:
   - The high accuracy of the source classifier confirms that different datasets exhibit distinct systemic differences in signal-to-noise ratio, baseline morphology, and sampling characteristics.

3. **Strategic Product Decision**:
   - This empirical finding directly reinforces the **CardioTwin v4 pivot**:
   - **Do NOT position CardioTwin as a multi-class definitive diagnostic tool.**
   - **Position it as a personalized digital twin**: measuring stability relative to the user's own empirical baseline, with research-grade waveform screening flagged as exploratory evidence.

---
