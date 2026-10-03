# 🫀 CardioTwin v4 — Master Engineering Plan & Product Pivot

**Project:** CardioTwin — Personalized Cardiovascular Instability Digital Twin & Research Waveform Screening  
**Version:** 4.0.0 (Canonical Pivot)  
**Hackathon:** Digital Twin Challenge 2026 (Happiest Health)  
**Status:** Executed & Verified

---

## 🎯 Executive Summary & Strategic Repositioning

### From Diagnosis Device to Personalized Digital Twin
CardioTwin has undergone a fundamental architectural and product repositioning:
- **Previous Framing (v3):** Consumer optical PPG device attempting autonomous 8-class cardiac arrhythmia diagnosis.
- **Defect Identified:** Cross-dataset confounding audit proved that multi-center ICU datasets (CinC 2015, MIMIC-III) exhibit deep hospital acquisition signatures (e.g., 100% of asystole and ventricular tachycardia derive from CinC 2015). A single-site optical sensor cannot autonomously diagnose complex electrophysiological arrhythmias without a 12-lead ECG.
- **New Framing (v4):** A **Personalized Cardiovascular Instability Digital Twin** that continuously evaluates:
  > *"Is this individual currently departing meaningfully from their own verified, empirical resting baseline?"*

### Core Engineering Tenet
> **Every number displayed must be provably real, every score must be provably valid, and every claim must be defensibly grounded in clinical literature and leak-free empirical data.**

---

## 📊 Summary of Architectural Changes

| Dimension | Previous State (v3) | CardioTwin v4 (Current State) |
|:---|:---|:---|
| **Primary Dashboard Output** | 8-class arrhythmia classification label | **Continuous Instability Index (0–100)** anchored to personal baseline |
| **Arrhythmia Detection Framing** | Autonomous diagnosis | **Research Waveform Pattern Screening** (Observational aid; 12-lead ECG required) |
| **Personal Baseline** | Static population-wide assumptions | **Empirical 2-min calibration** (Median HR, MAD dispersion, RMSSD baseline) |
| **Departure Detection** | Rigid arbitrary thresholds | **Robust Z-Score formulation** ($z = \frac{\Delta}{1.4826 \times \text{MAD}}$) |
| **Signal Reliability Gate** | Monolithic gate blocking high RR-CV and extreme BPM | **Decoupled Architecture**: Hardware gate blocks AI; physiological observations surface freely |
| **Hardware Telemetry** | Server-side receipt timestamps, fake SpO2=98% fallback | **Microsecond hardware timing**, sequence continuity tracking, truthful `N/A (IR Only)` |
| **Dual ML Evaluation** | Blended OOF classical with retrained full-set CNN | **Strict fold-isolated evaluation** via `evaluate_dual_pipeline_v2.py` |

---

## 🏗️ CardioTwin v4 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CARDIOTWIN v4 SYSTEM ARCHITECTURE                        │
│                                                                                 │
│   ┌─────────────────────────────┐           ┌────────────────────────────────┐  │
│   │ STREAM 1: CLINICAL EHR      │           │ STREAM 2: LIVE TELEMETRY       │  │
│   │ (Longitudinal Priors)       │           │ (ESP32 MAX30102 @ 100 Hz)      │  │
│   │                             │           │                                │  │
│   │ • Patient Demographics      │           │ • Hardware sequence counter    │  │
│   │ • Blood Pressure History    │           │ • Microsecond clock delta      │  │
│   │ • Lipid Panel & HbA1c       │           │ • 100 Hz raw infrared flux     │  │
│   │ • Framingham 10-Yr CVD Risk │           │ • Truthful SpO2 (N/A IR only)  │  │
│   │   (South Asian 1.45x Model) │           │ • Dynamic pulse rate (PR)      │  │
│   └──────────────┬──────────────┘           └───────────────┬────────────────┘  │
│                  │                                          │                   │
│                  ▼                                          ▼                   │
│   ┌──────────────────────────────────────────────────────────────────────────┐  │
│   │               DECOUPLED 5-PART SIGNAL RELIABILITY GATE                   │  │
│   │                                                                          │  │
│   │  [Filter 1: Signal Quality Gate] ──► Blocks AI strictly on hardware/     │  │
│   │  • Contact Amplitude (IR > 50k)      optical failure (FINGER_OFF,        │  │
│   │  • Sample Timing (100 ± 15 Hz)       SENSOR_SATURATION, POOR_TIMING)     │  │
│   │  • ADC Saturation (Clip ≤ 5%)                                            │  │
│   │  • Pulse Morphology (≥ 3 peaks)                                          │  │
│   │                                                                          │  │
│   │  [Filter 2: Physiological Observations] ──► Informs clinical context;    │  │
│   │  • Rate state (Bradycardic / Typical / Tachycardic)                      │  │
│   │  • Rhythm regularity (RR-CV > 0.35 surfaced as IRREGULAR_RHYTHM)         │  │
│   │  • Never blocks screening for quality-verified optical windows           │  │
│   └─────────────────────────────────────┬────────────────────────────────────┘  │
│                                         │                                       │
│                                         ▼                                       │
│   ┌──────────────────────────────────────────────────────────────────────────┐  │
│   │          PERSONALIZED CARDIOVASCULAR INSTABILITY ENGINE                  │  │
│   │                                                                          │  │
│   │  2-Minute Calibration Protocol:                                          │  │
│   │  • 30s settling window discarded; 90s quality-passed windows aggregated  │  │
│   │  • Robust non-parametric baseline: Median BPM & MAD, Median RMSSD & MAD  │  │
│   │                                                                          │  │
│   │  Instability Index Formulation (0–100):                                  │  │
│   │  • 35% Sustained Pulse-Rate Departure (Robust Z-Score)                   │  │
│   │  • 25% Pulse Irregularity Departure (Beat-to-Beat RR-CV)                 │  │
│   │  • 20% Autonomic Modulation (RMSSD Parasympathetic Suppression)          │  │
│   │  • 20% Multi-Window Temporal Memory (4-Window Persistence Consensus)     │  │
│   │                                                                          │  │
│   │  Clinical States:                                                        │  │
│   │  • 0–20: Stable | 20–40: Mild Departure | 40–70: Sustained | 70+: Review │  │
│   └───────────────────┬─────────────────────────────────┬────────────────────┘  │
│                       │                                 │                       │
│                       ▼                                 ▼                       │
│   ┌────────────────────────────────────┐ ┌───────────────────────────────────┐  │
│   │ PRIMARY CLINICAL DISPLAY           │ │ SECONDARY RESEARCH TOOL           │  │
│   │ ────────────────────────────────── │ │ ───────────────────────────────── │  │
│   │ • Real-time Instability Index      │ │ • Inception-1D Waveform Screener  │  │
│   │ • Calibrated vs Prior Baseline     │ │ • 51.41% Grouped-CV Macro-F1      │  │
│   │ • 4-Pillar Biomarker Breakdown     │ │ • Investigational Screening Aid   │  │
│   │ • Rolling Trajectory Sparkline     │ │ • Mandatory 12-lead ECG Disclaimer│  │
│   └────────────────────────────────────┘ └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Eight-Step Execution Roadmap & Verification

### Step 1: Make Live Telemetry Truthful ✅ (COMPLETED)
- **1.1 Firmware Integrity (`hardware/esp32_ppg_sender/esp32_ppg_sender.ino`)**:
  - Removed hardcoded `"spo2": 98` fallback.
  - Removed fake default `bpm > 0 ? bpm : 72`.
  - Added hardware timestamp provenance: `sequence` tracking, `first_sample_ms`, and `sample_interval_us: 10000`.
- **1.2 Backend Reconstruction (`backend/api_server.py`)**:
  - Reconstructed accurate microsecond timing grid in `receive_sensor_data()`.
  - Added sequence continuity tracking and packet drop monitoring (`sequence_gaps`).
  - Implemented truthful unmeasured reporting: `spo2 = None`, `spo2_status: "UNAVAILABLE_NO_RED_CHANNEL"`.
- **1.3 Safe Rule Execution (`backend/pulse_rules.py`, `backend/digital_twin_engine.py`)**:
  - Safeguarded vitals parsing against `None` values without raising exceptions or falling back to arbitrary numbers.

---

### Step 2: Decouple the Signal Reliability Gate ✅ (COMPLETED)
- **2.1 Architectural Separation (`backend/signal_gate.py`)**:
  - Split `evaluate_window()` into two distinct outputs:
    1. `signal_quality`: (`contact_ok`, `timing_ok`, `saturation_ok`, `pulse_morphology_ok`, `screening_allowed`) — strictly blocks AI inference only on physical sensor failure.
    2. `physiological_observation`: (`pulse_rate`, `rate_state`, `rr_cv`, `irregularity_state`, `recheck_recommended`) — contextual observations that never block screening.
- **2.2 Pathology Preservation**:
  - High beat-to-beat variability (`rr_cv > 0.35`) is surfaced as `IRREGULAR_PULSE_OBSERVATION` (`status: "IRREGULAR_RHYTHM"`), allowing genuine AFib to reach the screening model.
  - Rate bounds (<40 or >180 BPM) are flagged as `RECHECK_REQUIRED` rather than discarding the window.

---

### Step 3: Build the Personalized Digital Twin Engine ✅ (COMPLETED)
- **3.1 Empirical 2-Minute Calibration (`backend/personal_baseline.py`)**:
  - 30-second settling period automatically discarded to allow vasomotor relaxation.
  - Subsequent 90 seconds aggregated across quality-verified windows.
  - Computes robust non-parametric parameters:
    - Median BPM and MAD (Median Absolute Deviation $\times 1.4826$).
    - Median RMSSD and MAD.
    - Median RR interval and RR-CV.
- **3.2 Multimodal Instability Index (0–100)**:
  - Robust Z-scores computed against the individual's own distribution.
  - Weighted fusion: 35% HR departure + 25% rhythm irregularity + 20% RMSSD suppression + 20% multi-window memory.
- **3.3 Persistence & REST API**:
  - Baselines persisted per patient in `backend/baselines/<patient_id>.json`.
  - Added endpoints: `POST /baseline/calibrate`, `POST /baseline/cancel`, `GET /baseline/<patient_id>`.

---

### Step 4: Repair the ML Evaluation Pipeline ✅ (COMPLETED)
- **4.1 Leakage Elimination (`scripts/evaluate_dual_pipeline_v2.py`)**:
  - Evaluated the Classical Super Ensemble using 5-fold `StratifiedGroupKFold` across all 2,271 patients with zero patient overlap.
  - Generated and verified `model/oof_predictions_classical.npz` (48.00% Grouped-CV Macro-F1, 58.32% Accuracy).
- **4.2 Deep Learning Tournament Integration**:
  - Updated `ml/CardioTwin_1D_CNN_Colab.ipynb` to export `oof_predictions_cnn.npz` across all 5 folds.
  - Retained verified standalone Inception-1D champion benchmark: **51.41% Grouped-CV Macro-F1** (56.87% Accuracy).
- **4.3 Scorecard Integrity**:
  - Withdrew invalid 62.57% claims from code, model cards, and documentation.

---

### Step 5: Audit Source & Cohort Confounding ✅ (COMPLETED)
- **5.1 Confounding Audit Execution (`scripts/audit_source_confounding.py`)**:
  - Analyzed the distribution of 4,683 windows across 2,271 patients from MIMIC-III, CinC 2015, and BUT-PPG.
  - Generated [docs/SOURCE_CONFOUNDING_AUDIT.md](file:///c:/Users/harsh/Desktop/Harsh%20Folder/Machine%20Learning/IoT%20Project/docs/SOURCE_CONFOUNDING_AUDIT.md) and [docs/source_confounding_audit.json](file:///c:/Users/harsh/Desktop/Harsh%20Folder/Machine%20Learning/IoT%20Project/docs/source_confounding_audit.json).
- **5.2 Empirical Findings**:
  - CinC 2015 accounts for 100% of Asystole (17 patients), 100% of V_Flutter_Fib (6 patients), and 100% of V_Tachycardia (61 patients).
  - MIMIC-III accounts for 100% of AFib (400 patients) and Cardiac_Paced (400 patients).
  - An ExtraTrees classifier achieved **77.08% accuracy (81.30% balanced accuracy)** purely predicting the origin hospital dataset from 27 PPG features.
  - Proved that cross-hospital domain signatures exist, confirming the necessity of tracking personal baseline departure over raw multi-class labeling.

---

### Step 6: Reframe the Research Waveform Classifier ✅ (COMPLETED)
- **6.1 Investigational Reframing (`backend/dual_engine.py`, `backend/api_server.py`)**:
  - Arrhythmia prediction output updated to `research_waveform_pattern`.
  - Added non-diagnostic research disclaimer:
    > *"Investigational screening prototype. Optical patterns cannot substitute for clinical 12-lead diagnostic ECG."*
- **6.2 Clinical Presentation**:
  - Renamed labels to pattern descriptions (e.g., *Atrial Fibrillation Pattern*, *Normal Sinus Rhythm Pattern*).

---

### Step 7: Hardware Telemetry Dataset Protocol ✅ (COMPLETED)
- **7.1 Validation Tooling (`scripts/record_validation_session.py`, `scripts/validate_hardware_recordings.py`)**:
  - Implemented 5 window quality metrics (`sample_rate_estimate`, `bpm`, `peak_coverage`, `rr_cv`, `clipping_ratio`).
  - Conducted session-level validation auditing real finger-on, motion artifact, and sensor liftoff recordings.
- **7.2 True Telemetry Verification**:
  - Zero fabricated SpO2 or BPM in live hardware recording sessions.

---

### Step 8: Evidence-Based Dashboard Alignment ✅ (COMPLETED)
- **8.1 Clinical Web Portal (`frontend/web/src/App.jsx`, `frontend/web/src/index.css`)**:
  - **Headline Card**: Personalized Cardiovascular Instability Score (0–100) with color-coded badges and 4-pillar breakdown (HR departure Z-score, RR-CV irregularity, RMSSD autonomic suppression, multi-window consensus).
  - **Secondary Tool**: Research Waveform Pattern Screening with prominent investigational banner and probability meters.
  - **Truthful Telemetry**: Displays `N/A (IR Only)` for SpO2 during live hardware mode and `--` when pulse rate is uncomputed.
  - **Interactive Calibration**: Real-time 2-minute baseline calibration workflow with animated settling countdown, window counter, and cancellation controls.
  - **Decoupled Gate HUD**: Telemetry tab distinctly displays hardware quality gate vs physiological observations.
  - **Build Verification**: Compiled with Vite in **752 ms** with zero errors or warnings.

---

## 📈 Verified Standalone Benchmarks

| Candidate Model | Input Modality | Grouped-CV Macro-F1 | Grouped-CV Accuracy | Evaluation Guarantee |
|:---|:---|:---:|:---:|:---|
| **Inception-1D Deep Learning Champion** | Raw 100 Hz Waveform (10s) | **51.41%** | **56.87%** | 5-Fold StratifiedGroupKFold on 2,271 Patients |
| **ResNet-1D** | Raw 100 Hz Waveform (10s) | **50.81%** | **56.22%** | 5-Fold StratifiedGroupKFold on 2,271 Patients |
| **Standard 1D-CNN** | Raw 100 Hz Waveform (10s) | **48.72%** | **54.13%** | 5-Fold StratifiedGroupKFold on 2,271 Patients |
| **Classical Super Ensemble (XGB+RF+ET)** | 27 Extracted Biomarkers | **48.00%** | **58.32%** | 5-Fold StratifiedGroupKFold on 2,271 Patients |
| **Baseline XGBoost** | 27 Extracted Biomarkers | **46.71%** | **56.97%** | 5-Fold StratifiedGroupKFold on 2,271 Patients |
| **CRNN (Conv1D + BiLSTM)** | Raw 100 Hz Waveform (10s) | **45.04%** | **51.40%** | 5-Fold StratifiedGroupKFold on 2,271 Patients |
| **Personal Baseline Instability Engine** | Telemetry + Longitudinal EHR | **Continuous (0–100)** | N/A | Individualized robust Z-score vs calibrated baseline |

---

## 🔒 Automated Verification & Quality Gates

```
Automated Test Suite: 37 Unit & Integration Tests
Platform: Windows / Python 3.12 / PyTorch / Scikit-Learn / Flask-SocketIO
Command: python -m unittest tests.test_cardiotwin -v
Result: 37 Passed / 0 Failed / 0 Errors (100% OK in 1.3s)
Frontend Build: npm run build in frontend/web/ (Vite Production: Clean build in 752ms)
```

### Verified Test Categories:
1. **API Server Contracts**: Live hardware telemetry parsing, device command polling, sequence tracking, truthful null handling.
2. **Clinical Framingham Engine**: Age boundary clamping (30–74), South Asian 1.45× recalibration toggle.
3. **Decoupled Signal Reliability Gate**: Sensor liftoff, optical saturation, sample timing jitter, physiological irregularity preservation.
4. **Personal Baseline & Instability Engine**: 2-minute empirical calibration, robust Z-scores, instability escalation, recovery tracking.
5. **Deterministic Pulse Rules & Persistence**: Multi-window consensus alerting, transient noise rejection, asymmetric evidentiary thresholds.
6. **Dual-Modality Architecture**: Inception-1D tensor forward passes, Classical Super Ensemble inferences, leak-free artifact contracts.
