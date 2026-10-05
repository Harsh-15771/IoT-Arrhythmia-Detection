# 🫀 CardioTwin Sentinel — Executive Summary

**Project Title:** CardioTwin Sentinel: A Personalized Cardiovascular & Cardiometabolic Digital Twin  
**Target:** Digital Twin Challenge 2026 (Happiest Health)  
**Lead Developer:** Harshvardhan  
**Repository:** [Harsh-15771/IoT-Arrhythmia-Detection](https://github.com/Harsh-15771/IoT-Arrhythmia-Detection)  

---

## 🎯 Executive Elevator Pitch (30-Second Brief)

Cardiovascular disease is the leading cause of mortality in India (28% of all deaths), striking South Asians 10–15 years earlier than Western populations. Current monitoring tools are either cost-prohibitive consumer luxuries (Apple Watch ₹45k+), hospital-confined (Holter monitors ₹5k–₹15k), or lack intelligence (basic finger pulse-oximeters).

**CardioTwin Sentinel** is an ultra-low-cost (~₹1,165 / $14), research-backed cardiovascular digital twin that:
1. **Learns your personal empirical resting baseline** in 2 minutes (zero population-default guesses).
2. **Detects sustained autonomic and rhythm departures** using robust non-parametric statistical metrics (Median, MAD, RR-CV, RMSSD).
3. **Explains why departures occurred** using SHAP game-theoretic feature attribution and temporal persistence context.
4. **Empowers clinicians to simulate preventive What-If treatment outcomes** using an ethnicity-recalibrated ($1.45\times$) Framingham Cox proportional hazards engine.
5. **Openly reports what it does NOT know** through a machine-readable Evidence Ledger, prioritizing scientific honesty over inflated hackathon claims.

---

## 🏆 The "Wow Factor" Stack (Why CardioTwin Wins)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CARDIOTWIN SENTINEL — WOW FACTORS                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. REAL HARDWARE, REAL OPTICAL PHYSICS                                     │
│     ESP32 + MAX30102 live streaming at 100 Hz via FreeRTOS dual-core        │
│     Core 1 dedicated to optical acquisition; Core 0 handles WiFi telemetry  │
│     Sub-microsecond timestamping with jitter & buffer drop tracking         │
│                                                                             │
│  2. PERSONALIZED, NOT POPULATION-BASED                                      │
│     Every instability score is anchored to YOUR empirical resting baseline  │
│     Strictly blocks scoring prior to calibration (zero 72 BPM defaults)     │
│     Grounding: PRV agreement with HRV is strongest at seated rest           │
│                                                                             │
│  3. CLINICAL WHAT-IF INTERVENTION SIMULATOR                                 │
│     Bridges acute IoT telemetry with 10-year longitudinal CVD epidemiology  │
│     Simulates SBP reductions, statin therapy, and smoking cessation        │
│     Features 1.45x South Asian recalibration factor for Indian patients     │
│                                                                             │
│  4. GAME-THEORETIC XAI & EVIDENCE LEDGER                                    │
│     SHAP TreeExplainer unpacks decisions across 27 physiological markers   │
│     Machine-readable Evidence Ledger discloses SpO2, ECG, and data limits   │
│     Domain confounding audit reveals ICU dataset signatures                 │
│                                                                             │
│  5. MASS-DEPLOYABLE FOR INDIA'S PRIMARY CARE GAP                            │
│     Total hardware BOM: ₹1,165 (~$14) vs ₹50,000+ smartwatches              │
│     4,000-patient synthetic Indian cohort spanning 24 urban & rural blocks  │
│     HL7 FHIR R4 & Ayushman Bharat Digital Mission (ABDM) integration pathway│
│                                                                             │
│  6. PUBLICATION-GRADE VERIFICATION                                          │
│     49 automated tests passing (100% test suite green)                      │
│     Patient-isolated 5-fold cross-validation on 2,271 patients (no leakage) │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Core Performance & Benchmark Scorecard

| Milestone / Subsystem | Benchmark Metric | Standard Achieved | Verification Evidence |
|:---|:---|:---:|:---|
| **Honest Nested Dual-Modality Fusion** | Macro-F1 (Outer Folds) | **53.92%** (Acc: 59.21%) | Nested 5-Fold StratifiedGroupKFold (`model/dual_modality_benchmark_v2.json`) |
| **Deep Learning Waveform Champion** | Macro-F1 (8 Classes) | **51.81%** (Acc: 56.37%) | Inception-1D OOF (`model/cnn_metadata-1.json`) |
| **Classical Super Ensemble (XGB+RF+ET)**| Macro-F1 (27 Features) | **48.00%** (Acc: 58.32%) | 10-Model Algorithm Tournament (`model/`) |
| **Cohort Diversity** | Unique ICU/Ambulatory Patients| **2,271 Patients** | MIMIC-III, CinC 2015, BUT PPG v2.0, BIDMC |
| **Automated Testing Suite** | Unit & Target Validation Tests | **49 / 49 PASSING** | `tests/test_cardiotwin.py` + `tests/test_instability_target_validation.py` |
| **Hardware Optical Sampling** | Sampling Rate & Jitter | **100.0 Hz ($\pm 0.4$ ms)** | FreeRTOS Core 1 Hardware ISR Timer |
| **Signal Quality Yield** | Post-Settling Usable Windows | **$\ge 92.4\%$** | Decoupled 5-Part Signal Reliability Gate |
| **Estimated Hardware BOM** | Total Unit Cost | **₹1,165 (~$14)** | Bulk sourcing analysis (`docs/HARDWARE_BOM_COST_ANALYSIS.md`) |
| **Interoperability** | Standards Alignment | **HL7 FHIR R4 / ABDM** | Export specification (`docs/ABDM_FHIR_INTEGRATION.md`) |

---

## 🔬 System Workflow in 4 Steps

```
[1] SEATED CALIBRATION (2 Mins)
    ESP32 MAX30102 collects 6 clean 10s windows at seated rest.
    CardioTwin establishes personal Median BPM, MAD, RMSSD, and RR-CV.
            │
            ▼
[2] REAL-TIME MONITORING & GATING
    Decoupled 5-Part Signal Gate verifies physical integrity (finger-off / clipping).
    Physiological observations (tachycardia / irregular pulse) are preserved for AI.
            │
            ▼
[3] INSTABILITY ENGINE & EXPLAINABILITY
    Robust Z-scores compute Personal Instability Index (0–100).
    SHAP attributions and Evidence Ledger disclose exact drivers and limitations.
            │
            ▼
[4] CLINICIAN WHAT-IF DECISION SUPPORT
    Doctor reviews live oscilloscope wave and explores pharmacological scenarios:
    "What if this patient's SBP drops 15 mmHg via Telmisartan?" ──► 31% risk reduction.
```

---

## 👥 Project Team & Submission Details

- **Author / Developer:** Harshvardhan
- **Academic Context:** Machine Learning & Internet-of-Things (IoT) Research
- **Competition:** Digital Twin Challenge 2026 (Organized by Happiest Health)
- **Codebase License:** MIT License with Open Science Research Disclaimer

*CardioTwin Sentinel transforms affordable optical sensors into clinically accountable, personalized cardiovascular twins.*
