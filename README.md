# 🫀 CardioTwin — Evidence-Aware Cardiovascular Digital Twin & Clinical Decision Support Portal

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite-61dafb.svg)](https://react.dev/)
[![ML Model](https://img.shields.io/badge/ML%20Version-v3.0.0--clinical--mimic--2000-success.svg)](docs/MODEL_CARD.md)
[![Clinical Engine](https://img.shields.io/badge/Clinical%20Model-Framingham%20Cox%20(South%20Asian%20Recalibrated)-orange.svg)](backend/framingham_risk.py)
[![Model Status](https://img.shields.io/badge/Status-Investigational%20Screening%20Prototype-yellow.svg)](docs/MODEL_CARD.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **CardioTwin** is an evidence-aware cardiovascular risk twin for early identification of physiological instability in patients with cardiometabolic risk factors. It fuses synthetic longitudinal electronic health record (EHR) data with live PPG-derived pulse, pulse-rate variability, $\text{SpO}_2$, and signal-quality measurements to support clinician review — not autonomously diagnose arrhythmia or prescribe treatment.

---

## 📑 Core Documentation Links
- 🎯 **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Comprehensive System Architecture, Data Streams & State Fusion
- 📋 **[MODEL_CARD.md](docs/MODEL_CARD.md)** — Rigorous Leak-Free Evaluation, 5-Fold Grouped Metrics & Safety Gating
- 📊 **[DATA_CARD.md](docs/DATA_CARD.md)** — Provenance Manifest, ICU Waveform Datasets & PhysioNet DUA Compliance
- 🧪 **[tests/test_cardiotwin.py](tests/test_cardiotwin.py)** — Automated Test Suite (17 unit & integration tests)

---

## 🌟 Key Highlights (v3 Authoritative Release)

1. **Multimodal Dual-Stream Fusion**:
   - **Stream 1 (Static EHR Baseline)**: Longitudinal clinical profile (Demographics, SBP, DBP, Lipid panel, HbA1c, Smoking) running through a **D'Agostino 2008 Cox proportional hazards general CVD model** with an **exploratory 1.45× South Asian recalibration factor** and age boundary guardrails (ages 30–74).
   - **Stream 2 (Real-Time Wearable Telemetry)**: Live 100 Hz photoplethysmogram (PPG) from an ESP32 microcontroller with a MAX30102 optical sensor, extracting 27 morphological, HRV, and Welch spectral biomarkers.
2. **Authoritative 8-Class Clinical Rhythm Screening Model (v3)**:
   - Grounded in **2,271 unique clinical patients across 4,683 standardized windows**, featuring **2,000 authentic ICU patients from MIMIC-III-Ext-PPG v1.1.0** (400 AFib, 400 Bradycardia, 400 Tachycardia, 400 Cardiac Paced / Blocks, 400 Normal controls) combined with PhysioNet CinC 2015 true alarms and BUT PPG v2.0 wearable optical noise.
   - Evaluated using **StratifiedGroupKFold (5-Fold cross-validation on Patient IDs)** with **zero patient overlap** between train and validation partitions.
   - Cross-validation performance: **56.97% accuracy, 0.4671 Macro-F1** across 8 complex rhythm classes (against 12.5% random guess).
   - Incorporates automated **Signal Quality Index (SQI) Safety Gating** ($SQI \ge 0.40$ and $\sigma \ge 0.05$) to prevent motion artifacts from triggering spurious critical alarms.
3. **Evidence-Aware Dynamic State Fusion**:
   - Distinctly separates the **10-year baseline Framingham CVD risk percentage** from the **real-time dynamic physiological instability score (0–100)**, avoiding the trap of merging an epidemiological 10-year probability with acute sensor fluctuations.
   - Non-diagnostic screening framing: all critical rhythm findings explicitly require 12-lead diagnostic ECG review.
4. **Interactive "What-If" Outcome Simulator**:
   - Clinicians can simulate virtual pharmacological interventions (Beta-blockers like Metoprolol, Statins like Atorvastatin, ACE inhibitors like Ramipril) and lifestyle modifications with a transparent **5–10 year sustained adherence time horizon**.
5. **Clinical Command Center (Doctor's Web Portal)**:
   - High-tech, dark-mode glassmorphic portal built with **React 19, Vite, and Lucide icons**, featuring real-time oscilloscope SVG PPG waveform monitoring, live biometrics, data provenance tags (`LIVE_HARDWARE`, `SIMULATION`, `STANDBY`), and multi-layer risk decomposition.
6. **Physical Edge IoT Hardware Contract**:
   - Working ESP32 + MAX30102 + SH1106 OLED embedded system with synchronized polling via `/command` and dual JSON payload support (`values` and `samples`) to `/data` and `/ingest_telemetry`.

---

## 🏗️ Architecture Overview

```
                      +------------------------------------------+
                      |         STREAM 1: PATIENT EHR            |
                      | Demographics, Vitals, Labs, Lifestyle,   |
                      | 10-Yr Framingham CVD Risk (D'Agostino)   |
                      +--------------------+---------------------+
                                           |
                                           v
+------------------------+      +--------------------+      +-------------------------+
| STREAM 2: IoT SENSORS  | ---> |   MULTIMODAL FUSION| ---> |  INTERACTIVE CLINICIAN  |
| ESP32 + MAX30102 PPG   |      |  DIGITAL TWIN CORE |      |        DASHBOARD        |
| 100 Hz Optical Pulse   |      | Layer 1: Base CVD  |      | Dynamic Trajectory      |
| SQI Artifact Rejection | ---> | Layer 2: Instability| ---> | What-If Simulator       |
| 27 Biomarkers + XGBoost|      | Layer 3: EMA State |      | Alert Auditing Panel    |
+------------------------+      +--------------------+      +-------------------------+
```

---

## 📁 Repository Directory Structure

```
CardioTwin/
├── backend/                       # REST & WebSocket Real-Time Digital Twin Engine
│   ├── api_server.py             # Flask + Socket.IO API server (port 5000, 14 routes)
│   ├── digital_twin_engine.py    # Evidence-Aware Dynamic Risk State & What-If Simulator
│   ├── framingham_risk.py        # Framingham 10-Yr CVD Cox Model (D'Agostino 2008)
│   ├── ehr_generator.py          # Synthetic Indian EHR generator
│   └── synthetic_patients.json   # 100 curated patient profiles with clinical baselines
│
├── frontend/                      # Unified Frontend Applications
│   ├── web/                      # Clinician Decision Support Portal (React 19 + Vite)
│   │   ├── src/                  # App.jsx, App.css, main.jsx
│   │   ├── package.json          # Vite scripts & dependencies
│   │   └── vite.config.js
│   └── mobile/                   # Patient Wearable Monitor (React Native / Expo)
│       ├── App.js                # Mobile BLE/PPG monitor screen
│       ├── package.json          # Expo dependencies
│       └── app.json
│
├── hardware/                      # Embedded Firmware & Edge Hardware (IoT)
│   └── esp32_ppg_sender/         # ESP32 + MAX30102 + SH1106 OLED 100Hz sender
│       └── esp32_ppg_sender.ino
│
├── ml/                            # Machine Learning Models, Training & Research
│   ├── train_unified_models.py   # [ACTIVE v3] 8-class leak-free training pipeline (2,271 patients)
│   ├── build_clean_dataset.py    # Multi-modal compiler (MIMIC-III + BUT PPG + CinC + BIDMC)
│   ├── export_colab_data_and_notebook.py # Colab data exporter
│   └── CardioTwin_1D_CNN_Colab.ipynb # Deep learning 1D-CNN research notebook
│
├── model/                         # Investigational Screening Model Artifacts & Evaluation (v3)
│   ├── xgboost_ppg_model.pkl     # Trained 8-class XGBoost model (v3.0.0)
│   ├── scaler.pkl                # Standardizer fit strictly on training patient records
│   ├── label_encoder.pkl         # 8-class target encoder
│   ├── feature_names.pkl         # 27 physiological feature names
│   ├── model_metadata.json       # Leak-free 5-fold CV metrics, patient counts & provenance
│   ├── confusion_matrix_xgboost.png # Normalized 8-class confusion matrix
│   └── feature_importance_xgboost.png # Top physiological biomarker rankings
│
├── data/                          # Data Specifications & Metadata
│   └── dataset_manifest.json     # Complete record-level provenance manifest
│   # Note: Raw clinical waveforms and credentialed MIMIC-III files are excluded
│   # via .gitignore in strict compliance with the PhysioNet Data Use Agreement.
│
├── docs/                          # Submission Documentation & Standards
│   ├── MODEL_CARD.md             # Standard Model Card (Mitchell et al. / Google standard)
│   ├── DATA_CARD.md              # Dataset provenance, licenses, and DUA compliance
│   └── ARCHITECTURE.md           # End-to-end multimodal systems architecture
│
├── tests/                         # Automated Verification Suite
│   └── test_cardiotwin.py        # 17 unit & integration tests (Clinical, Twin, API, ML)
│
├── scripts/                       # Automation & Hardware Audit Scripts
│   ├── run_v3_pipeline.py        # Master v3 pipeline orchestrator
│   └── validate_hardware_recordings.py # SQI audit on raw recorded sessions
│
├── recordings/                    # Hardware Telemetry Stream Logs (39 CSV dumps)
├── requirements.txt               # Pinned, tested Python dependencies
├── .env.example                   # Environment configuration template
└── LICENSE                        # MIT License with research disclaimer
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites & Environment Setup
```bash
# Clone the repository
git clone https://github.com/Harsh-15771/IoT-Arrhythmia-Detection.git
cd IoT-Arrhythmia-Detection

# Create virtual environment and activate
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux / macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Automated Verification Tests
```bash
python -m unittest tests/test_cardiotwin.py
```
*Expected: 17 tests pass with OK status.*


### 3. Launch Backend API Server
```bash
python api_server.py
```
*Starts Flask + Socket.IO server on `http://127.0.0.1:5000`.*

### 4. Launch Doctor's Clinical Dashboard
```bash
cd frontend/web
npm install
npm run dev
```
*Open `http://localhost:5173` to view the live dashboard.*

### 5. Run Hardware Recording SQI Audit
```bash
python scripts/validate_hardware_recordings.py
```

---

## 🔬 Scientific & Clinical Rigor Highlights

| Characteristic | Superficial Prototype Pitfall | CardioTwin Verified Standard |
|---|---|---|
| **Train/Test Splitting** | Random window-level split (overlapping patient windows leak between train & test) | **Record-Level Grouped Splitting** (`StratifiedGroupKFold`) ensuring 100% patient isolation |
| **Preprocessing Scaling** | Scaler fit across entire dataset before splitting | **Train-Only Scaling** fit strictly on training partition records |
| **Telemetry Ingestion** | Hardcoded payload key or missing control endpoints | **Dual Contract Support** (`values` & `samples`) + bidirectional `/command` sync |
| **Sensor Motion Artifact** | False arrhythmia alarms during hand movement | **Signal Quality Index (SQI) Safety Gating** ($SQI \ge 0.40$ required for screening) |
| **Clinical Framing** | Overclaiming autonomous diagnosis or prescribing | **Evidence-Aware Screening**; all rhythm alerts framed as requiring 12-lead ECG review |
| **What-If Horizon** | Instantaneous medication effect on 10-year risk | **Explicit 5–10 Year Sustained Adherence Horizon** with trial-derived parameters |

---

## ⚖️ Clinical Disclaimer
CardioTwin is an exploratory decision-support system designed for educational, research, and hackathon demonstration purposes. Photoplethysmography (PPG) is an observational screening modality and does not replace diagnostic 12-lead electrocardiography (ECG) or professional physician evaluation.
