# 🏆 Digital Twin Challenge 2026 — CardioTwin Master Plan & Audit

## Honest Assessment First

### Should you use the existing IoT project?

**YES — as the empirical hardware and telemetry foundation.**

Here's the audited reality:
- A standalone PPG classifier is **not** a Digital Twin; a true Digital Twin requires the bidirectional fusion of longitudinal clinical priors (EHR, cardiometabolic labs, Framingham risk) with real-time physiological dynamics.
- Naive window-level splitting on physiological signals creates severe data leakage (overlapping windows from the same patient in train and test), creating an illusion of ~85%+ accuracy. A scientifically defensible evaluation requires **patient-level grouped cross-validation (`StratifiedGroupKFold`)**, which demonstrates the true uninflated generalization metric.
- **CardioTwin v3 Authoritative Model**: Ingests **2,271 real clinical patients across 4,683 windows**, including **2,000 authentic ICU patients from MIMIC-III-Ext-PPG v1.1.0** (400 AFib, 400 Bradycardia, 400 Tachycardia, 400 Paced/Blocks, 400 Normal controls) combined with PhysioNet CinC 2015 true alarms and BUT PPG v2.0 wearable optical noise. Achieves **56.97% accuracy and 0.4671 Macro-F1** across 8 complex rhythm classes (against 12.5% random guess).
- The physical hardware (ESP32 + MAX30102 + OLED + Flask + React Doctor's Portal) provides **empirical provenance**: streaming real biological photons from a finger into a live virtual patient model.

> [!IMPORTANT]
> 95% of teams submit synthetic CSV data and static Figma mockups. CardioTwin demonstrates a **live optical sensor streaming real biological pulses into an evidence-aware Digital Twin engine with clinical safety gating, grounded in 2,000 genuine ICU patient recordings from MIMIC-III**.

### Key Conceptual Pillars Verified:
- ✅ **Multimodal Fusion**: EHR (Clinical MIMIC & Indian Cohorts) + Wearable Telemetry (ESP32 MAX30102).
- ✅ **Dual-Tier Risk Separation**: Longitudinal 10-Year CVD Baseline (Framingham Cox Model) separated from Real-Time Physiological Instability (0–100 score).
- ✅ **Signal Quality Gating**: SQI safety threshold ($SQI \ge 0.40$) preventing false asystole/tachycardia alarms from motion artifacts or sensor liftoff.
- ✅ **Clinical Governance**: PPG framed strictly as an investigational screening prototype requiring 12-lead ECG clinical confirmation.
- ✅ **PhysioNet DUA Compliance**: Zero raw patient waveforms in public GitHub; reproducible pipeline scripts and manifests only.

---

## The Concept: **CardioTwin — Personalized Cardiovascular Digital Twin**

### One-Line Pitch
> "A real-time cardiovascular digital twin that fuses longitudinal clinical history with live wearable PPG telemetry to continuously track acute physiological instability and simulate 5–10 year treatment outcomes — demonstrated with live IoT hardware."

### Why Cardiovascular + PPG?
| Factor | Clinical & Practical Justification |
|:---|:---|
| **Disease Burden** | CVD accounts for over 28% of all mortality in India, striking South Asians up to a decade earlier than Western cohorts. Addressing this aligns directly with the "Reimagining Healthcare in India" summit mission. |
| **Hardware Match** | The MAX30102 optical sensor acquires raw photoplethysmography (PPG) at 100 Hz, extracting heart rate, HRV time/frequency biomarkers (RMSSD, SDNN, pNN50, LF/HF), SpO2, and Signal Quality Index (SQI). |
| **Data Provenance** | Grounded in 2,271 unique clinical patients across 4,683 windows, featuring 2,000 authentic ICU patients from MIMIC-III-Ext-PPG v1.1.0 under a signed PhysioNet DUA, combined with PhysioNet CinC 2015, BUT PPG v2.0, and BIDMC. Longitudinal profiles modeled using synthetic Indian patient cohorts. |
| **"What-If" Simulation** | Projecting the hemodynamic and risk impact of guideline-directed medical therapies (statins, beta-blockers, ACE inhibitors, smoking cessation) over a 5–10 year horizon provides actionable clinical decision support. |

---

## Architecture: What We Built

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CARDIOTWIN ENGINE                               │
│                                                                        │
│  ┌──────────────────────┐              ┌────────────────────────────┐  │
│  │   STREAM 1: EHR      │              │    STREAM 2: LIVE PPG      │  │
│  │   (Clinical Priors)  │              │    (ESP32 + MAX30102)      │  │
│  │                      │              │                            │  │
│  │  • Demographics      │              │  • Raw 100Hz Optical PPG   │  │
│  │  • SBP / DBP (mmHg)  │              │  • Heart Rate & SpO2       │  │
│  │  • Lipid Panel       │              │  • HRV: RMSSD, SDNN, pNN50 │  │
│  │  • Fasting Glucose   │              │  • Spectral: LF, HF, LF/HF │  │
│  │  • Smoking History   │              │  • Pulse Morphology & SQI  │  │
│  │  • Prior MI / Stroke │              │  • Signal Quality Gating   │  │
│  └──────────┬───────────┘              └─────────────┬──────────────┘  │
│             │                                        │                 │
│             ▼                                        ▼                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                MULTIMODAL RISK DECOMPOSITION                     │  │
│  │                                                                  │  │
│  │  Tier 1: Framingham 10-Yr CVD Baseline (D'Agostino 2008)         │  │
│  │          • Sex-stratified Cox proportional hazards model         │  │
│  │          • Age boundary clamping (30–74) + extrapolation flag    │  │
│  │          • Exploratory South Asian 1.45× recalibration           │  │
│  │                                                                  │  │
│  │  Tier 2: Leak-Free 6-Class XGBoost Acute Rhythm Classifier       │  │
│  │          • Grouped cross-validation (StratifiedGroupKFold, K=5)  │  │
│  │          • 27 extracted physiological biomarkers                 │  │
│  │          • SQI safety gating (motion artifacts safely suppressed)│  │
│  │                                                                  │  │
│  │  Tier 3: Dynamic Physiological Instability Index (0–100)         │  │
│  │          • Autonomic modulation (RMSSD suppression factor)       │  │
│  │          • Hemodynamic & SpO2 penalty weighting                  │  │
│  │          • Continuous risk trajectory & alert gating             │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │                                  │
│             ┌───────────────────────┴───────────────────────┐          │
│             ▼                                               ▼          │
│  ┌───────────────────────────────┐     ┌────────────────────────────┐  │
│  │ PREDICTION & MONITORING       │     │ "WHAT-IF" SIMULATOR        │  │
│  │ ────────────────────────────  │     │ ────────────────────────── │  │
│  │ • Current 10-Yr Baseline Risk │     │ • Antihypertensive therapy │  │
│  │ • Real-time Instability Index │     │ • Statin lipid lowering    │  │
│  │ • SQI-gated Screening Alerts  │     │ • Smoking cessation        │  │
│  │ • 12-lead ECG review discl.   │     │ • 5–10 yr projected impact │  │
│  └───────────────────────────────┘     └────────────────────────────┘  │
└─────────────────────────────────────┬──────────────────────────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
    ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
    │ Doctor's     │           │ Mobile App   │           │ ESP32 OLED   │
    │ Web Portal   │           │ Client       │           │ Local Screen │
    │ (React 19)   │           │ (Expo Native)│           │ (SH1106)     │
    └──────────────┘           └──────────────┘           └──────────────┘
```

---

## Critical Strategic Decisions & Scientific Integrity

### 1. Leak-Free Machine Learning Protocol (Authoritative v3 Model)
- **The Issue with Naive Splitting**: Randomly shuffling 10-second sliding windows splits identical cardiac waveforms of the same patient across both training and testing folds. This artificial autocorrelation generates inflated metrics (~82% accuracy) that collapse in real-world deployment.
- **Our Audited Solution**: We built the authoritative **CardioTwin v3** pipeline ([`ml/train_unified_models.py`](ml/train_unified_models.py)) using **`StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`** grouped strictly on patient identifiers across **2,271 unique clinical patients and 4,683 windows** (MIMIC-III-Ext-PPG: 2,000 patients; PhysioNet CinC 2015: 231 records; BUT PPG v2.0: 39 subjects; BIDMC: 1 patient).
- **Authoritative v3 Performance (8 Classes)**:
  - **Classes**: `AFib`, `Asystole`, `Bradycardia`, `Cardiac_Paced`, `Normal`, `Tachycardia`, `V_Flutter_Fib`, `V_Tachycardia`.
  - **Out-of-Fold Cross-Validation Accuracy**: **56.97%** across 8 complex rhythm classes (vs 12.5% random guess baseline).
  - **Macro-F1 Score**: **0.4671** (zero patient overlap across all 5 folds; 95% CI: [0.4285, 0.5057]).
  - **Weighted-F1 Score**: **0.5685**.
  - **High Clinical Sensitivity**: Normal F1: 0.7802, Bradycardia F1: 0.6542, Tachycardia F1: 0.6292, AFib F1: 0.5614.
  - **Legacy Archive (v2)**: The preliminary 6-class / 354-record model (38.54% accuracy, 0.3468 Macro-F1) is archived as a baseline historical milestone ([`ml/train_model_v2.py`](ml/train_model_v2.py)).
  - **Scientific Defense**: This uninflated, patient-isolated benchmark provides the exact medical justification for why single-channel PPG is positioned as an **observational screening and physiological instability modulator** rather than a definitive diagnostic tool.

### 2. Signal Quality Index (SQI) Safety Gating
- Optical sensor recordings (MAX30102) are susceptible to baseline wander and motion artifacts. Unfiltered classifiers frequently misidentify finger movement as Ventricular Tachycardia or Asystole.
- **Safety Rule**:
  - If $\sigma < 0.05$: Flag `Sensor Disconnected / Lead Off`.
  - If $SQI < 0.40$: Suppress acute classification; flag `Signal Insufficient / Motion Artifact (Gated)`.
  - Only when $SQI \ge 0.40$ does the system evaluate acute rhythm probabilities.

### 3. Clinically Sound Risk Modeling
- **Framingham CVD Base Score**: Implemented exactly from D'Agostino et al. (Circulation 2008). Added boundary handling for patients outside the 30–74 age derivation window, setting an explicit `age_extrapolated: True` flag.
- **South Asian Multiplier**: Documented transparently as an exploratory prototype assumption (1.45× recalibration based on Bansal et al. 2020 and Garg et al. 2017) to account for premature cardiovascular onset in India.
- **Risk Tiering**: Baseline 10-year CVD risk (%) and Real-Time Physiological Instability Score (0–100) are maintained as separate clinical concepts.

---

## Implementation Status & Deliverables Verification

| Phase | Milestone / Deliverable | Status | Verification & Artifact |
|:---|:---|:---:|:---|
| **Firmware** | ESP32 dual payload contract (`samples` + `values`), SpO2, `/command` sync | ✅ Done | [`esp32_ppg_sender/esp32_ppg_sender.ino`](esp32_ppg_sender/esp32_ppg_sender.ino) |
| **Backend** | REST API, WebSocket push, SQI gating, Provenance tracking, Ingestion buffer (10s) | ✅ Done | [`backend/api_server.py`](backend/api_server.py) |
| **Risk Engine** | Framingham 10-Yr CVD Model, Age boundary handling, South Asian 1.45× modifier | ✅ Done | [`backend/framingham_risk.py`](backend/framingham_risk.py) |
| **Digital Twin** | Multimodal fusion engine, Instability scoring (0-100), What-If treatment simulator | ✅ Done | [`backend/digital_twin_engine.py`](backend/digital_twin_engine.py) |
| **ML Pipeline (v3)** | 8-Class XGBoost model on 2,271 patients (4,683 windows), leak-free 5-fold CV | ✅ Done | [`ml/train_unified_models.py`](ml/train_unified_models.py), [`model/model_metadata.json`](model/model_metadata.json) |
| **Data Governance**| Strict PhysioNet DUA compliance; all raw MIMIC-III waveforms gitignored | ✅ Done | [`.gitignore`](.gitignore), [`docs/DATA_CARD.md`](docs/DATA_CARD.md) |
| **Hardware Audit**| Live hardware recording verification script (39 CSVs tested) | ✅ Done | [`scripts/validate_hardware_recordings.py`](scripts/validate_hardware_recordings.py) |
| **Web Portal** | React 19 + Vite dashboard, live SVG oscilloscope, What-If sliders, ECG review notice | ✅ Done | [`cardiotwin-dashboard/src/App.jsx`](cardiotwin-dashboard/src/App.jsx) |
| **Automated Tests**| 17 comprehensive unit & integration tests covering risk, SQI, APIs, and models | ✅ Done | [`tests/test_cardiotwin.py`](tests/test_cardiotwin.py) (17/17 passing) |
| **Documentation** | Model Card, Data Card, Architecture Spec, Dataset Manifest, License | ✅ Done | `docs/MODEL_CARD.md`, `docs/DATA_CARD.md`, `docs/ARCHITECTURE.md` |

---

## 🗓️ Official Roadmap to Submission (October 2 – October 20, 2026)

| Dates | Phase | Work | Exit Gate | Status |
|:---|:---|:---|:---|:---:|
| **Oct 2–3** | **Release Consolidation** | Choose v3 as the authoritative model; update README, PLAN, DONE, model card, data card, architecture, dashboard labels, and tests to 8 classes / 2,271 patients / 4,683 windows. Archive or clearly label v2 as legacy. | Every displayed metric and class matches one reproducible artifact. | ✅ **DONE** |
| **Oct 2–3** | **Data-Governance Cleanup** | Add raw MIMIC, raw PhysioNet, recordings, model-training caches, and .env files to `.gitignore`. Retain only download/preprocessing scripts, dataset manifest, citations, and aggregate metrics. | `git status` contains no restricted raw dataset files. | ✅ **DONE** |
| **Oct 3–5** | **Reproducible ML Release** | Create one command that builds the unified dataset, trains v3, writes metrics, model card values, confusion matrix, and feature importance. Record source-specific class counts and patient-level splits. | A clean environment can reproduce model artifacts or clearly reports which credentialed data are required. | ✅ **DONE** |
| **Oct 4–6** | **Model Evidence** | Add per-class precision/recall/F1, confusion matrix, calibration/confidence analysis, and an explicit held-out test protocol. Avoid only reporting overall accuracy. | Model card is consistent, complete, and scientifically defensible. | 🔄 **In Progress** |
| **Oct 5–8** | **Hardware Acceptance Test** | Record at least 10 stable 60-second sessions, 5 motion sessions, and 5 finger-off sessions. Compare BPM against a pulse oximeter or manual 60-second count. | Stable data: BPM MAE $\le 5$ BPM, $\ge 90\%$ accepted windows. Motion/finger-off: 100% gated. | ⏳ Planned |
| **Oct 7–9** | **Sensor Improvement** | If acceptance fails, tune physical contact, LED current, sampling timing, peak prominence/distance, filtering, and SQI threshold. Retest using the same protocol. | Hardware produces credible live pulse data before ML is enabled. | ⏳ Planned |
| **Oct 9–11** | **Twin Product Polish** | Make the main UI sequence explicit: Data quality $\to$ live pulse/SpO₂ $\to$ pulse-rate variability $\to$ instability score $\to$ EHR baseline risk $\to$ clinician review. Keep baseline 10-year risk separate from acute state. | Judges can understand every score and alert in under 30 seconds. | ⏳ Planned |
| **Oct 11–12** | **Clinical Scenarios** | Prepare three scripted patient journeys: preventive-care baseline, high cardiometabolic risk, and simulated acute instability. Clearly label all replays and simulations. | Every demo scenario has a one-sentence clinical story, data source, and expected outcome. | ⏳ Planned |
| **Oct 12–14** | **Submission Documentation** | Finalize architecture PDF, presentation PDF, model/data cards, limitations, hardware validation table, license, setup guide, citations, and team details. | A reviewer can run and evaluate the project without verbal explanation. | ⏳ Planned |
| **Oct 15–17** | **Video** | Record hardware footage separately as a backup. Produce the 20-minute video: problem $\to$ architecture $\to$ honest evidence $\to$ live hardware $\to$ dashboard $\to$ scenario $\to$ what-if $\to$ limitations $\to$ impact. | One reliable, rehearsed, upload-ready video. | ⏳ Planned |
| **Oct 18–19** | **Release Rehearsal** | Fresh clone, dependency install, tests, frontend build, backend startup, hardware test, dashboard test, and link audit. | Full stack works from clean setup. | ⏳ Planned |
| **Oct 20** | **Submit** | Public repo, no restricted data, video, architecture PDF, presentation PDF, license, and correct team details. | Submission complete. | ⏳ Planned |

---

## 🎯 The Priority Order

1. **Version / Documentation Consistency** (Make v3 authoritative everywhere)
2. **MIMIC Public-Repo Compliance** (Zero restricted hospital data tracked)
3. **Hardware Accuracy and Signal-Quality Acceptance Testing** (Resolve the biggest technical risk)
4. **Reproducible v3 Model Evidence** (Complete dual-model benchmark)
5. **Dashboard Storytelling and Submission Assets** (Clinical patient journeys & video)

---

## 🚀 Product Development Roadmap (Execution Plan)

### 1. Fix and Validate the Live PPG Pipeline First (Foundational Gate)
*The foundation of the digital twin. Do not advance ML claims until the edge hardware produces reliable, empirically grounded pulse signals.*

#### A. Five-Part Signal Reliability Gate (per 10-second window):
1. **Sensor Contact / Amplitude Check**: Detect finger-off, flatline, optical clipping, or ADC saturation ($\sigma < 0.05$ or clipping ratio $> 0.05$).
2. **Sample-Timing Check**: Verify timestamps are within $10 \pm 2\,\text{ms}$ spacing ($100\,\text{Hz}$). Flag any dropped packets or gaps $> 250\,\text{ms}$.
3. **Peak Regularity Check**: Verify optical systolic peaks have plausible spacing ($0.30\,\text{s} \le \text{IBI} \le 1.6\,\text{s}$) and normalized prominence $\ge 0.25$.
4. **Physiological Plausibility Check**: For a seated adult subject, accept pulse rate strictly between **$40 - 180\,\text{BPM}$**. Any reading outside this range flags `VERIFY_SIGNAL` rather than an immediate acute dysrhythmia.
5. **Window Stability Check**: Require at least **three consecutive valid 10-second windows** before transitioning to active AI screening.

#### B. Computed Window Metrics:
- $\text{sample\_rate\_estimate} = \frac{1}{\text{median}(\Delta t)}$
- $\text{bpm} = \frac{60}{\text{median}(\text{valid peak intervals})}$
- $\text{peak\_coverage} = \frac{\text{valid peaks}}{\text{expected peaks}}$
- $\text{rr\_cv} = \frac{\text{std}(RR)}{\text{mean}(RR)}$
- $\text{clipping\_ratio} = \frac{\text{samples near ADC limit}}{\text{total samples}}$

#### C. Explicit Five-State Finite State Machine:
```
[NO_FINGER] ──(contact detected)──> [BUFFERING (0-10s)] ──(10s complete)──> [SIGNAL_CHECK]
     ▲                                                                           │
     │                                                     ┌─────────────────────┴──────────────────┐
     │                                                     │ (fails any of 5 tests)                 │ (passes 5 tests)
     │                                                     ▼                                        ▼
     └────────────────(finger liftoff)──────────── [SIGNAL_UNRELIABLE]                       [LIVE_RELIABLE]
                                                           ▲                                        │
                                                           │                              (3 stable windows)
                                                           │ (quality drop)                         │
                                                           │                                        ▼
                                                           └─────────────────────────────── [SCREENING_ACTIVE]
                                                                                            (ML model enabled)
```
*Rule: Only execute ML rhythm inference when in `SCREENING_ACTIVE` state.*

#### D. Hardware Tuning Specification (ESP32 + MAX30102):
- **Sampling Frequency**: $100\,\text{Hz}$
- **LED Mode**: Dual Red + IR mode
- **Sample Averaging**: 4 samples per FIFO read
- **Pulse Width**: $411\,\mu\text{s}$ (18-bit resolution)
- **ADC Range**: $4096\,\text{nA}$ full-scale
- **LED Current**: Initialized to $25 - 35\,\text{mA}$, tuned experimentally per user optical absorption
- **Optical Shielding**: Black foam / neoprene sensor shroud to eliminate 50/60 Hz ambient lighting flicker
- **Placement Guidance**: Warm finger, gentle uniform contact without blanching capillary bed

#### E. Hardware Acceptance Test Protocol (`recordings/validation/`):
Record 17 systematically labeled validation sessions (anonymized IDs only):
1. **9 Stable Sessions**: 3 participants $\times$ 3 repeat 60-second stable seated recordings with ground-truth reference BPM from a certified pulse oximeter or manual 60-second radial pulse count.
2. **3 Controlled Motion Sessions**: Seated finger with deliberate motion artifacts at $t = 20\,\text{s}$ and $t = 40\,\text{s}$.
3. **3 Finger-Off Sessions**: Active recording with deliberate sensor liftoff at $t = 20\,\text{s}$.
4. **2 Low-Contact Sessions**: Intentionally loose, misaligned placement.

#### F. Acceptance Criteria Table:
| Test Scenario | Required Pass Condition | Exit Gate Status |
|:---|:---|:---:|
| **Stable Session Duration** | $\ge 60$ seconds uninterrupted recording | Mandatory |
| **Signal Quality Rate** | $\ge 90\%$ of 10-second windows accepted as reliable | Mandatory |
| **BPM Accuracy** | Mean Absolute Error ($\text{MAE}) \le 5\,\text{BPM}$ vs reference pulse oximeter | Mandatory |
| **Stable Normal Session** | Zero false critical rhythm alerts (`V_Tachycardia`, `V_Flutter_Fib`, `Asystole`) | Mandatory |
| **Finger-Off Sessions** | $100\%$ classified as `NO_FINGER` or `SIGNAL_UNRELIABLE` | Mandatory |
| **Motion Sessions** | $\ge 90\%$ of motion-corrupted windows successfully gated | Mandatory |
| **Data Stream Integrity** | Zero packet or timestamp gaps exceeding $250\,\text{ms}$ | Mandatory |

---

### 2. Hierarchical ML Architecture & Dual-Model Benchmark
*Move from an uncalibrated single-model oracle to a defensible, multi-layered clinical decision hierarchy. Retain and complete the PyTorch 1D-CNN companion model for a dual-model benchmark.*

#### A. Three-Layer Decision Architecture:
- **Layer 0 (Signal Quality)**: Outputs exclusively one of: `NO_FINGER`, `BUFFERING`, `SIGNAL_UNRELIABLE`, `SIGNAL_RELIABLE`. No clinical rhythm labels exist at this layer.
- **Layer 1 (Deterministic Physiological Pulse State)**: Validated rule-based physiological observations:
  - $\text{Pulse Rate} < 50\,\text{BPM} \implies$ **Low pulse-rate observation**
  - $50 - 100\,\text{BPM} \implies$ **Typical resting range**
  - $100 - 120\,\text{BPM} \implies$ **Elevated pulse-rate observation**
  - $> 120\,\text{BPM}$ for $\ge 3$ consecutive windows $\implies$ **Sustained elevated pulse-rate observation**
  - $\text{SpO}_2 < 92\%$ for $\ge 3$ consecutive windows $\implies$ **Oxygenation review flag**
  *(Strictly non-diagnostic: uses "observation" and "review flag" rather than disease diagnosis).*
- **Layer 2 (ML Rhythm Screening & Dual-Model Benchmark)**:
  - **Model A (Interpretable Clinical Baseline)**: 8-class XGBoost operating on 27 physiological biomarkers.
  - **Model B (Deep Learning Representation)**: **PyTorch 1D-CNN** trained on normalized raw waveforms (`X_waveforms`, 1,000 samples @ 100 Hz) to deliver the planned end-to-end representation benchmark.
  - **Multi-Window Persistence Agreement**: Never trigger rhythm alerts from a single 10-second window. Require:
    $$\text{Reliable Signal} \land (\text{Same Non-Normal Pattern in } \ge 3 \text{ of last 4 windows}) \land (\text{Calibrated Confidence} \ge \tau_{\text{class}})$$
    Output: *"Persistent abnormal pulse pattern detected. Obtain ECG review."*

#### B. Model Improvements & Rigorous Evidence:
1. **Per-Source Cross-Dataset Evaluation**: Train on MIMIC-III (ICU) + CinC 2015, evaluate out-of-domain generalization separately on BUT PPG v2.0 (smartphone optical noise) and BIDMC.
2. **Confidence Calibration**: Fit Platt Scaling / Isotonic Regression strictly on training partitions to output calibrated posterior probabilities rather than raw softmax values.
3. **Class-Specific Decision Thresholds**: Ventricular Tachycardia and Flutter/Fib require higher evidentiary thresholds ($\tau \ge 0.75$) compared to Sinus Tachycardia ($\tau \ge 0.50$).
4. **Live-Device False-Positive Rate**: Quantify $\text{FPR} = \frac{\text{Non-Normal Screened Windows}}{\text{Reliable Normal Windows}}$ on empirical validation recordings to prove absence of false alarms under normal resting conditions.

---

### 3. Truly Longitudinal EHR Profiles (12-Month Patient Journeys)
*Transform the EHR component from a static baseline snapshot into a dynamic longitudinal trajectory showing how risk evolves over 12 months for 3 flagship patients.*

#### A. Longitudinal Schema Structure:
```json
{
  "patient_id": "MIMIC-p044570",
  "timeline": [
    { "month": 0,  "date": "2025-10-01", "systolic_bp": 146, "diastolic_bp": 92, "ldl": 168, "hba1c": 7.4, "smoker": true,  "adherence": "low",      "event": "Initial diagnosis of Stage 2 HTN & Dyslipidemia" },
    { "month": 3,  "date": "2026-01-01", "systolic_bp": 138, "diastolic_bp": 88, "ldl": 145, "hba1c": 7.1, "smoker": true,  "adherence": "moderate", "event": "Started Atorvastatin 20mg & Telmisartan 40mg" },
    { "month": 6,  "date": "2026-04-01", "systolic_bp": 130, "diastolic_bp": 82, "ldl": 112, "hba1c": 6.8, "smoker": false, "adherence": "high",     "event": "Smoking cessation achieved; LDL reduced 33%" },
    { "month": 12, "date": "2026-10-01", "systolic_bp": 122, "diastolic_bp": 78, "ldl": 88,  "hba1c": 6.4, "smoker": false, "adherence": "high",     "event": "Cardiometabolic targets achieved; baseline risk halved" }
  ]
}
```

#### B. Three Flagship Patient Profiles:
1. **Patient 1 (Cardiometabolic Risk Journey)**: `MIMIC-p044570` — 58y Indian male, uncontrolled HTN, dyslipidemia, smoking cessation journey.
2. **Patient 2 (Preventive Care Baseline)**: `MIMIC-p031260` — 44y female, early-stage pre-diabetes and border-line lipid elevation stabilized via lifestyle.
3. **Patient 3 (Complex Arrhythmia & Pacemaker History)**: `MIMIC-p006279` — 69y male with paroxysmal AFib and ventricular pacing history under rhythm surveillance.

#### C. UI Component:
- Dedicated **"Patient Journey"** trend visualization displaying 12-month trajectories of SBP, LDL, HbA1c, and Framingham CVD risk percentage with event milestone markers.

---

### 4. Target-Based What-If Outcome Simulator
*Transition from instantaneous medication toggle switches to scientifically credible target-based risk modifications evaluated over a sustained 5–10 year horizon.*

#### A. Target Modifications:
- **Target Systolic BP**: $145 \to 120\,\text{mmHg}$
- **Target Total Cholesterol / LDL**: $240 \to 175\,\text{mg/dL}$ ($160 \to 85\,\text{mg/dL}$)
- **Smoking Status**: Current smoker $\to$ Sustained cessation
- **Time Horizon**: Explicit 5–10 year sustained adherence calculation using the Framingham Cox proportional hazards equation.

#### B. Clinically Grounded Presets:
1. **Preset 1 (No Intervention / Natural History)**: Uncontrolled hypertension, active tobacco use, deteriorating lipid profile.
2. **Preset 2 (Partial Adherence)**: BP controlled ($130\,\text{mmHg}$), but smoking persists and lipids remain sub-optimal.
3. **Preset 3 (Comprehensive Prevention Plan)**: Guideline-directed targets achieved across BP ($120\,\text{mmHg}$), LDL ($< 100\,\text{mg/dL}$), and complete smoking cessation over 5–10 years.

---

### 5. Clinician Decision Flow Dashboard Architecture
*Redesign the Doctor's Web Portal around a 5-step clinical diagnostic inquiry sequence:*

1. **Step 1: Is the sensor connected and reliable?** (5-state signal reliability badge + SQI metric breakdown).
2. **Step 2: What is happening right now?** (Real-time 100 Hz oscilloscope, pulse rate, $\text{SpO}_2$, PRV / RMSSD).
3. **Step 3: Is this patient already high risk?** (Longitudinal 12-month EHR trajectory + 10-year baseline Framingham score).
4. **Step 4: Why did the system raise concern?** (**Alert Explanation Panel** showing exact causal factors: sustained pulse rate, SpO2 drop, HRV reduction, persistent ML rhythm pattern).
5. **Step 5: What changes could improve long-term trajectory?** (Target-based What-If simulator with 5–10 year horizon).

#### A. Structured Layout:
- **Top Bar**: Patient Selector | Data Provenance (`[LIVE_HARDWARE]`, `[SIMULATION]`, `[REPLAY]`) | 5-State Sensor Status Badge | Last Packet Timestamp
- **Left Panel (EHR)**: Demographics, Comorbidities, Medications, 12-Month Longitudinal Trend Graphs (BP, LDL, HbA1c)
- **Center Panel (Telemetry)**: 100 Hz Live PPG Waveform Trace, Instantaneous Pulse Rate, $\text{SpO}_2$, RMSSD, 5-part Signal Reliability Status
- **Right Panel (Risk & Explainability)**:
  - 10-Year Baseline Framingham Risk (%)
  - Real-Time Physiological Instability Score (0–100)
  - Hierarchical Rhythm Screening Output (Top pattern + Calibrated Confidence)
  - **Alert Explanation Panel** (Quantitative multi-factor clinical reasoning breakdown)
- **Bottom Panel (Intervention)**: Target-based What-If Treatment Simulator, Dynamic Instability Trajectory History, Clinical Event Milestones.

---

### 6. Ten-Step Sequential Implementation Roadmap

```
[Phase 1: HW Validation & SQI FSM]  ──>  [Phase 2: Hierarchical ML & 1D-CNN]  ──>  [Phase 3: Longitudinal EHR & What-If]  ──>  [Phase 4: Dashboard & Rehearsal]
  Steps 1, 2, 3, 4                        Steps 5, 6, 7                             Steps 8, 9                                Step 10
```

| Step | Scope | Description & Deliverables | Verification Exit Gate |
|:---:|:---|:---|:---|
| **Step 1** | **HW Validation Tooling** | Create `scripts/record_validation_session.py` and `scripts/compute_session_quality_report.py` implementing the 5 window quality metrics (`sample_rate_estimate`, `bpm`, `peak_coverage`, `rr_cv`, `clipping_ratio`). | Generates automated quality JSON and plots for any recording. |
| **Step 2** | **Validation Data Collection** | Execute the 17-session hardware protocol in `recordings/validation/` (9 stable with ground-truth reference BPM, 3 motion, 3 finger-off, 2 low-contact). | 17 session CSVs recorded and cataloged with reference BPMs. |
| **Step 3** | **Firmware & Sensor Tuning** | Update `esp32_ppg_sender.ino` with optimal MAX30102 registers (sample avg 4, 411µs, 25-35mA LED current) and peak detection parameters. | Stable BPM MAE $\le 5$ BPM vs reference; $\ge 90\%$ window acceptance. |
| **Step 4** | **Signal State Machine** | Implement the 5-state FSM (`NO_FINGER` $\to$ `BUFFERING` $\to$ `SIGNAL_CHECK` $\to$ `LIVE_RELIABLE` $\to$ `SCREENING_ACTIVE`) in `backend/api_server.py`. | State transitions verified in backend and reflected via WebSocket. |
| **Step 5** | **Deterministic Pulse Rules** | Implement Layer 1 pulse-state observations (low PR, typical, elevated, sustained elevated, hypoxia) with 3-window alert persistence. | Observation flags trigger only after 3 consecutive agreeing windows. |
| **Step 6** | **Hierarchical ML Layer** | Re-architect rhythm inference into Layer 2 screening: require reliable signal, $\ge 3$ of 4 window agreement, and class-specific thresholds. | Model inference suppressed during motion/noise; alerts persist. |
| **Step 7** | **Dual-Model Benchmark (1D-CNN)** | Train PyTorch 1D-CNN on `X_waveforms` in `ml/train_1d_cnn.py`, calibrate XGBoost confidence with Platt scaling, and measure out-of-domain BUT PPG and live false-positive rates. | Comprehensive dual-model benchmark table (XGBoost vs 1D-CNN) documented in Model Card. |
| **Step 8** | **Longitudinal EHR Trajectories** | Expand `backend/synthetic_patients.json` and `backend/ehr_generator.py` with 12-month histories and event milestones for 3 flagship patients. | `/patient/<id>` returns 12-month longitudinal timeline. |
| **Step 9** | **Target-Based Simulator** | Upgrade `backend/digital_twin_engine.py` What-If engine to target-based SBP/lipid/smoking modifications with 3 presets and 5–10 year horizon. | Simulator outputs 5–10 year absolute risk reduction for all 3 presets. |
| **Step 10**| **Decision-Flow Dashboard** | Rebuild `cardiotwin-dashboard/src/App.jsx` with 5-part layout, 12-month EHR trends, 5-state sensor badge, and Alert Explanation panel. | Production build passes; clinician flow answers all 5 questions seamlessly. |


