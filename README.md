# 🫀 CardioTwin Sentinel — Personalized Cardiovascular & Cardiometabolic Digital Twin

[![Python 3.10 / 3.11](https://img.shields.io/badge/Python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite-61dafb.svg)](https://react.dev/)
[![FreeRTOS Dual-Core](https://img.shields.io/badge/Firmware-ESP32%20FreeRTOS%20Dual--Core-red.svg)](hardware/esp32_ppg_sender/esp32_ppg_sender.ino)
[![ML Benchmark](https://img.shields.io/badge/Deep%20Learning%20Champion-51.41%25%20Macro--F1%20(Patient--Isolated)-success.svg)](docs/MODEL_CARD.md)
[![Clinical Engine](https://img.shields.io/badge/Clinical%20Model-Framingham%20Cox%20(1.45x%20South%20Asian%20Recalibrated)-orange.svg)](docs/SOUTH_ASIAN_RISK_CALIBRATION.md)
[![Tests Passing](https://img.shields.io/badge/Tests-49%20Passing%20(100%25)-brightgreen.svg)](tests/)
[![Status](https://img.shields.io/badge/Status-Submission--Ready%20(Digital%20Twin%20Challenge%202026)-purple.svg)](docs/EXECUTIVE_SUMMARY.md)

---

## 🎯 What CardioTwin Sentinel IS

CardioTwin Sentinel is a **personalized hypertension and cardiometabolic-risk digital twin** that:
1. **Learns your individual resting pulse baseline** through a 2-minute seated empirical calibration (median BPM, MAD, RR-CV, RMSSD).
2. **Detects sustained physiological departures** from that baseline in real time using robust non-parametric statistics.
3. **Explains why departures occur** via transparent, SHAP-inspired biomarker attribution and temporal persistence context.
4. **Empowers clinicians to simulate preventive What-If scenarios** using a Framingham-grounded Cox proportional hazards model recalibrated for South Asian populations ($1.45\times$ risk multiplier).
5. **Openly discloses what it does NOT know** through a machine-readable Evidence Ledger (no SpO₂, no 12-lead ECG equivalence, ICU dataset bias transparency).

### What CardioTwin Sentinel is NOT:
| ❌ NOT This | ✅ Because |
|:---|:---|
| **An 8-class autonomous diagnostic machine** | Single-channel optical PPG cannot replace 12-lead diagnostic ECG for electrophysiology |
| **A consumer pulse-oximeter** | Single-channel IR sensor; no red LED $\rightarrow$ SpO₂ is declared unavailable rather than fabricated |
| **A dashboard of detached numbers** | Every metric is anchored directly to your personal calibrated resting baseline |
| **A "99% accurate" black-box model** | We report honest, leak-free, patient-isolated cross-validation numbers ($51.41\%$ Inception-1D Macro-F1) |

---

## 📑 Core Documentation Index

- 📄 **[docs/EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md)** — 1-Page Hackathon Pitch & Value Proposition for Judges
- 📋 **[docs/MODEL_CARD.md](docs/MODEL_CARD.md)** — Patient-Isolated Multi-Modal Benchmark, Architectures & Source Bias
- 🔬 **[docs/SHAP_EXPLAINABILITY_REPORT.md](docs/SHAP_EXPLAINABILITY_REPORT.md)** — SHAP TreeExplainer Attributions for 27 Biomarkers
- 🕵️ **[docs/SOURCE_CONFOUNDING_AUDIT.md](docs/SOURCE_CONFOUNDING_AUDIT.md)** — Cross-Dataset Provenance & Class Concentration Audit
- 🇮🇳 **[docs/SOUTH_ASIAN_RISK_CALIBRATION.md](docs/SOUTH_ASIAN_RISK_CALIBRATION.md)** — $1.45\times$ Framingham Multiplier Clinical Justification
- 💰 **[docs/HARDWARE_BOM_COST_ANALYSIS.md](docs/HARDWARE_BOM_COST_ANALYSIS.md)** — Bill of Materials (~₹1,165 / $14) vs Clinical Alternatives
- 🏥 **[docs/ABDM_FHIR_INTEGRATION.md](docs/ABDM_FHIR_INTEGRATION.md)** — Ayushman Bharat Digital Mission & HL7 FHIR R4 Specification
- 📊 **[docs/DATA_CARD.md](docs/DATA_CARD.md)** — Dataset Provenance (2,271 patients) & PhysioNet DUA Compliance
- 🏗️ **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — End-to-End Multimodal System Architecture

---

## 🌟 Technical Highlights & Core Innovations

### 1. Dual-Core FreeRTOS Embedded Firmware
- **Core 1 (Hardware ISR & Sampling):** Runs a high-priority FreeRTOS task sampling the MAX30102 optical sensor at exactly 100 Hz ($10,000\,\mu\text{s}$ interval) using hardware microsecond timing (`micros()`).
- **Core 0 (Networking & Buffering):** Decoupled FreeRTOS task handles WiFi transmission, HTTP polling, and JSON serialization without stalling optical acquisition.
- **Hardware Telemetry Integrity:** Transmits `device_boot_id`, sequential chunk numbering (`seq`), and microsecond timestamps. Detects sample jitter, timing drift, and buffer drops.

### 2. Personal Baseline Governance (Zero Population Defaults)
- **Empirical Calibration Requirement:** Requires at least 6 high-quality, post-settling 10-second windows ($>60\,\text{s}$ clean seated data).
- **No Population Guessing:** Uncalibrated users return `instability_score: null` and status `"Personal baseline required"`.
- **Robust Non-Parametric Statistics:** Tracks Median and Median Absolute Deviation (MAD), eliminating sensitivity to outlier spikes.
- **Strict Invalidation Rules:** Baselines expire after 30 days or immediately if device ID or optical sensor configuration (LED current, sample rate) changes.

### 3. Decoupled 5-Part Signal Reliability Gate
- **Physical Reliability (Blocks AI):** Detects finger-off ($<20\,\text{k}$ ADC ceiling), amplifier saturation ($>260\,\text{k}$ ADC limit), and sample timing jitter.
- **Physiological Plausibility (Informs AI):** Extreme rates (<40 BPM or >180 BPM) or chaotic rhythms (AFib, VT) are **not gated out as noise**; they pass through as verified physiological observations marked for clinical review.

### 4. Patient-Isolated Machine Learning Benchmark (10-Model Tournament)
- Evaluated on **2,271 unique patients across 4,683 windows** from MIMIC-III, PhysioNet CinC 2015, BUT PPG v2.0, and BIDMC.
- **Strict 5-Fold Stratified Grouped Cross-Validation on Patient IDs:** Zero patient overlap between train and test folds.
- **Deep Learning Champion:** Inception-1D CNN with multi-scale convolutions achieves **51.41% Macro-F1** (74.05% Accuracy).
- **Classical Super Ensemble:** XGBoost + Random Forest + ExtraTrees on 27 biomarkers achieves **48.00% Macro-F1** (65.98% Accuracy).
- **Source Confounding Transparency:** We openly disclose that 100% of VT and Asystole instances in the training corpus originate from CinC 2015 ICU alarms, preventing overconfident claims.

### 5. Explainable AI & Evidence Ledger
- **SHAP Feature Attribution:** Per-class feature importance derived from TreeExplainer on 27 biomarkers (`docs/shap_summary_plot.png`).
- **Natural-Language Explanations:** Explains exact deviation in BPM, RR-CV, and RMSSD with temporal duration context.
- **Evidence Ledger:** Machine-readable limitation disclosures accompany every telemetry evaluation.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          STREAM 1: PATIENT EHR                              │
│  Demographics, Vitals, Lipid Panel, HbA1c, Smoking, South Asian Multiplier   │
│  Framingham 10-Year Cardiovascular Event Risk (Cox Proportional Hazards)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     STREAM 2: IOT OPTICAL TELEMETRY                         │
│  ESP32 FreeRTOS (Core 1: 100 Hz Optical Capture | Core 0: WiFi JSON Stream) │
│  MAX30102 PPG Waveform ──► Decoupled 5-Part Signal Reliability Gate         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│               PERSONAL BASELINE & INSTABILITY ENGINE (0–100)                │
│  • Empirical 2-Min Seated Calibration (Median, MAD, RR-CV, RMSSD)           │
│  • Robust Z-Score Distance Metrics (Pulse Rate, Irregularity, Vagal Tone)   │
│  • Multi-Window Temporal Persistence Consensus Memory                       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  DUAL-MODALITY CLINICAL SCREENING ENGINE                    │
│  • Modality A: Classical Super Ensemble (XGB+RF+ET on 27 Biomarkers)        │
│  • Modality B: Inception-1D Deep Convolutional Waveform Champion            │
│  • SHAP Game-Theoretic Feature Attribution & Machine Evidence Ledger        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CLINICIAN DECISION SUPPORT PORTAL                       │
│  • Real-Time Oscilloscope Waveform & Baseline Departure HUD (React 19)      │
│  • Interactive Framingham What-If Treatment Outcome Simulator               │
│  • ABDM / HL7 FHIR R4 Clinician Report Exporter                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites & Environment Setup
```bash
# Clone the repository
git clone https://github.com/Harsh-15771/IoT-Arrhythmia-Detection.git
cd IoT-Arrhythmia-Detection

# Activate Python 3.11 virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux / macOS

# Install pinned dependencies
pip install -r requirements.txt
```

### 2. Run Automated Verification Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
*Expected: 49 tests pass with OK status across clinical engine, signal gate, personal baseline, API contract, and target validation conditions.*

### 3. Launch Backend API Server
```bash
python backend/api_server.py
```
*Starts Flask + Socket.IO server on `http://127.0.0.1:5000` with 17 REST endpoints and WebSocket telemetry broadcast.*

### 4. Launch Doctor's Clinical Dashboard
```bash
cd frontend/web
npm install
npm run dev
```
*Open `http://localhost:5173` to interact with the live clinical command portal.*

### 5. Run Source Confounding & SHAP Explainability Audits
```bash
# Generate SHAP feature importance & plots
python scripts/generate_shap_explanations.py

# Run dataset provenance & source confounding audit
python scripts/audit_source_confounding.py

# Run visual segment morphology audit
python scripts/audit_visual_segments.py
```

---

## 🧪 Verified Performance Matrix

| Metric | Random Guess | Classical Super Ensemble (XGB+RF+ET) | Inception-1D CNN (Champion) | Evaluation Standard |
|:---|:---:|:---:|:---:|:---|
| **Macro-F1 (8 Classes)** | 12.50% | **48.00%** | **51.41%** | 5-Fold Stratified Grouped CV (Patient-Isolated) |
| **Accuracy** | 12.50% | **65.98%** | **74.05%** | 5-Fold Stratified Grouped CV (Patient-Isolated) |
| **Unique Patients** | — | 2,271 patients | 2,271 patients | Zero patient overlap between folds |
| **BPM MAE (Resting)** | — | $\le 2.0\text{ BPM}$ | $\le 1.8\text{ BPM}$ | Verified against synthetic & reference telemetry |
| **Finger-Off Detection** | 0% | 100% | 100% | Gated by Signal Reliability Gate |
| **Motion False Alarms** | High | **0 false persistent alarms** | **0 false persistent alarms** | Multi-window persistence consensus |

---

## ⚖️ Clinical Disclaimer & Regulatory Boundary

CardioTwin Sentinel is an investigational clinical decision-support and digital twin prototype developed for the **Digital Twin Challenge 2026 / Happiest Health**. 

1. Photoplethysmography (PPG) measures volumetric microvascular pulse waves, not myocardial electrical vectors. It cannot diagnose acute myocardial infarction, ST elevation/depression, bundle branch blocks, or definitive ventricular arrhythmias.
2. All screening alerts explicitly declare: *"Investigational prototype — clinical 12-lead ECG review required."*
3. The system is designed to support clinical triage, track longitudinal resting baseline stability, and explore preventive cardiometabolic scenarios, not autonomously prescribe medications or replace board-certified physicians.

---

*Authored by Harshvardhan & the CardioTwin Sentinel Engineering Team.*
