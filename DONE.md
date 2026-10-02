# 📋 CardioTwin — Engineering Work Log & Progress (DONE.md)

**Project:** CardioTwin — Evidence-Aware Cardiovascular Digital Twin & Clinical Decision Support Portal  
**Hackathon:** Digital Twin Challenge 2026 (Happiest Health)  
**Log Format:** Chronological Work Entries (Date-Wise)

---

## 📅 Log Entry: October 1, 2026 — Initial Digital Twin Architecture & Portal Setup

### 1. Multimodal Architecture & Core Concept
- Established the **CardioTwin** multimodal framework combining two complementary clinical streams:
  - **Stream 1 (Static EHR Baseline)**: Patient demographics, blood pressure history, lipid panels, HbA1c, and smoking history running through a sex-stratified Framingham general CVD Cox model (D'Agostino 2008) with a 1.45× South Asian recalibration factor.
  - **Stream 2 (Real-Time Wearable Telemetry)**: Live 100 Hz photoplethysmogram (PPG) from an ESP32 microcontroller with a MAX30102 pulse oximeter, extracting morphological, HRV (RMSSD, SDNN, pNN50), and Welch spectral biomarkers.
- Generated initial synthetic cohort of 100 Indian patient EHR records (`backend/synthetic_patients.json` and `backend/ehr_generator.py`).
- Implemented 3-layer risk fusion engine and interactive "What-If" treatment outcome simulator (`backend/digital_twin_engine.py`).

### 2. Machine Learning Baseline & Data Acquisition
- Downloaded PhysioNet 2015 Challenge ICU recordings and BIDMC PPG dataset.
- Processed 10-second segments resampled to standardized 100 Hz (`data/processed/ppg_100hz_dataset.npz`).
- Trained initial 6-class XGBoost classifier on extracted pulse features detecting *Normal, Bradycardia, Tachycardia, Ventricular Tachycardia, Ventricular Flutter/Fibrillation,* and *Asystole*.
- Created Google Colab export script and notebook for 1D-CNN exploration (`ml/CardioTwin_1D_CNN_Colab.ipynb`, `ml/export_colab_data_and_notebook.py`).

### 3. Edge Hardware Firmware & Clinician Portal
- Developed ESP32 firmware (`esp32_ppg_sender/esp32_ppg_sender.ino`) for MAX30102 sensor and SH1106 I2C OLED display, sampling at 100 Hz and transmitting chunks via HTTP.
- Built Doctor's Clinical Web Portal in `cardiotwin-dashboard/` using **React 19, Vite, and Lucide icons**, featuring real-time oscilloscope SVG PPG waveform monitoring, live biometrics, patient switcher, and What-If simulator sliders.
- Verified patient mobile app in `ppg-monitor/` (React Native / Expo).

---

## 📅 Log Entry: October 2, 2026 — Scientific Rigor Audit, Hardware Alignment & Test Suite

### 1. Hardware-to-Backend Contract Synchronization
- **Dual-Contract Payload Support**: Updated ESP32 firmware [`esp32_ppg_sender/esp32_ppg_sender.ino`](esp32_ppg_sender/esp32_ppg_sender.ino) to send both `"samples"` and `"values"` in JSON chunk payloads alongside computed `bpm` and `spo2`.
- **Bidirectional Command Polling**: Added `GET /command` and `POST /command` endpoints to [`backend/api_server.py`](backend/api_server.py) so the ESP32 OLED display accurately synchronizes its running/idle state with the web portal.
- **Analysis Buffer Alignment**: Extended the backend analysis window from 5.0 seconds to the full **10.0 seconds (1,000 samples at 100 Hz)** to match the ML model's training window.
- **Network Telemetry Alignment**: Identified active local Wi-Fi IP (`192.168.1.247:5000`) on workstation, updating stale static configuration in firmware and [`.env.example`](.env.example).

### 2. Elimination of ML Data Leakage & True Benchmark Publication
- **Strict Leak-Free Record-Level Grouped Splitting**: Replaced window-level random splitting with **`StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`** grouped strictly on patient record identifiers across 354 distinct clinical recordings in [`ml/train_model_v2.py`](ml/train_model_v2.py).
- **Patient Isolation Guarantee**: Zero patient or record overlap between training and testing partitions; preprocessing `StandardScaler` fitted strictly on training partition records.
- **True Uninflated Metrics Published**:
  - Replaced inflated ~82% leakage claims in documentation with verified uninflated cross-validation metrics in [`model/model_metadata.json`](model/model_metadata.json):
    - **5-Fold Cross-Validation Accuracy:** 38.54% ± 3.25% (vs 16.67% random baseline across 6 classes)
    - **5-Fold Cross-Validation Macro-F1:** 0.3468 ± 0.0185 (95% CI: [0.3306, 0.3630])
    - **Held-Out Test Accuracy:** 35.66%, Macro-F1: 0.3181
  - Documented 27 extracted physiological biomarkers and generated clean feature importance and confusion matrix plots.

### 3. Signal Quality Index (SQI) Safety Gating
- Implemented real-time Signal Quality Index safety thresholds in [`backend/api_server.py`](backend/api_server.py):
  - If $\sigma < 0.05$: flags `Sensor Disconnected / Lead Off`.
  - If $SQI < 0.40$: suppresses raw arrhythmia predictions and flags `Signal Insufficient / Motion Artifact (Gated)`.
- Prevents hand movement or sensor liftoff from triggering spurious ventricular tachycardia or asystole alerts.
- Built and ran hardware recording audit script [`scripts/validate_hardware_recordings.py`](scripts/validate_hardware_recordings.py) across 39 physical session CSVs, verifying that clean PPG passes while motion-heavy segments are safely gated.

### 4. Clinical Governance & Risk Engine Refinement
- **Age Boundary Clamping**: Updated [`backend/framingham_risk.py`](backend/framingham_risk.py) to clamp ages outside the 30–74 derivation range with explicit `age_extrapolated: True` flags.
- **South Asian Recalibration Framing**: Explicitly labeled the 1.45× modifier as an exploratory prototype assumption based on Indian epidemiological studies (Bansal et al. 2020; Garg et al. 2017).
- **Conceptual Separation of Risk Tiers**: In [`backend/digital_twin_engine.py`](backend/digital_twin_engine.py), distinctly separated **Baseline 10-Year CVD Risk (%)** from the real-time **Physiological Instability Score (0–100)**.
- **Non-Diagnostic Framing**: Framed all PPG rhythm alerts as observational screening requiring urgent 12-lead ECG review.
- **Treatment Simulator Horizons**: Added explicit 5–10 year sustained adherence time horizon labels to What-If simulator outputs.

### 5. Web Portal Integrity & Transparency
- Removed silent fallback that generated fake synthetic sine waves during sensor disconnection in [`cardiotwin-dashboard/src/App.jsx`](cardiotwin-dashboard/src/App.jsx).
- Added explicit live data source provenance badges (`[LIVE_HARDWARE]`, `[SIMULATION]`, `[STANDBY]`).
- Updated Tile 4 header to "AI RHYTHM SCREENING" with prominent 12-lead ECG clinical review disclaimers.
- Verified clean production compilation with `npm run build` (built in 517ms).

### 6. Automated Test Suite & Codebase Standardization
- Created comprehensive test suite in [`tests/test_cardiotwin.py`](tests/test_cardiotwin.py) containing **17 unit and integration tests** covering:
  - Clinical Framingham calculation and age boundary clamping
  - South Asian multiplier toggling
  - Digital Twin initialization and telemetry updates
  - SQI motion artifact safety gating
  - What-If pharmacological and lifestyle simulation
  - API endpoints (`/`, `/patients`, `/patient/<id>`, `/patient/select`, `/twin/status`, `/twin/simulate`, `/twin/scenario`)
  - Hardware contract routes (`/command`, `/data` with `samples` key, `/data` with `values` key, `/ingest_telemetry`)
  - Recording session lifecycle (`/start`, `/stop`) with clean filesystem teardown
  - Dataset manifest and model metadata integrity
- Resolved circular import issue in root [`api_server.py`](api_server.py) launcher via [`backend/__init__.py`](backend/__init__.py) modular packaging.
- Authored production standards documentation:
  - [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) (Google / Mitchell et al. format)
  - [`docs/DATA_CARD.md`](docs/DATA_CARD.md) (Gebru et al. format)
  - [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (Multimodal systems spec)
  - [`data/dataset_manifest.json`](data/dataset_manifest.json) (Catalog of 2,271 patients / 4,683 windows, updated to v3)
  - [`requirements.txt`](requirements.txt), [`.env.example`](.env.example), and [`LICENSE`](LICENSE) (MIT with clinical research disclaimer).
- All 17 automated tests verified passing (100% success rate in 0.02s).

---

## 📅 Log Entry: October 2, 2026 (Evening) — Real MIMIC-III 2,000-Patient Cohort Acquisition & Multi-Modal Retraining

### 1. Direct Credentialed PhysioNet MIMIC-III Data Ingestion
- Successfully acquired the full **4.92 GB PhysioNet index (`metadata.csv`)** indexing **6,399,754 thirty-second telemetry segments** across **6,189 unique ICU patients**.
- Conducted deep streaming population analysis across all 6.4 million rows:
  - 84.4% of rows exhibit pristine optical quality (`vector_10s_pleth_sqi == [1, 1, 1]`).
  - Documented extensive clinical comorbidity landscape: 44.5% Hypertension (`4019`), 28.8% Hyperlipidemia (`2724`), 27.3% Atrial Fibrillation (`42731`), 25.8% Heart Failure (`4280`), and 24.3% CAD (`41401`).
- Resolved class imbalance by generating a **Clinically Balanced Champion Cohort** ([`data/raw/mimic_ppg/mimic_2000_balanced_cohort.csv`](data/raw/mimic_ppg/mimic_2000_balanced_cohort.csv)):
  - Exactly **2,000 unique patients** (1 segment per patient to guarantee zero patient leakage).
  - Balanced across 5 clinical categories: **400 AFib, 400 Bradycardia, 400 Tachycardia, 400 Cardiac Paced / Conduction Blocks, and 400 Normal controls**.
  - All 2,000 segments maintain 100% pristine `[1, 1, 1]` signal quality.
- Acquired and extracted all **4,000 waveform files (2,000 `.hea` + 2,000 `.dat`)** into [`data/raw/mimic_ppg/mimic_waveforms/`](data/raw/mimic_ppg/mimic_waveforms/) with a 100.0% matching rate.

### 2. Multi-Modal Unified Dataset Compilation
- Updated [`ml/build_clean_dataset.py`](ml/build_clean_dataset.py) to ingest:
  1. **MIMIC-III-Ext-PPG**: 2,000 real ICU patients (AFib, Brady, Tachy, Paced, Normal)
  2. **PhysioNet CinC 2015**: 1,890 verified true ICU alarms (VT, VFib, Asystole)
  3. **BUT PPG v2.0**: 792 expert-annotated smartphone recordings with real optical motion noise
  4. **BIDMC**: Hospital ICU telemetry baseline
- Compiled into [`data/processed/unified_multimodal_dataset.npz`](data/processed/unified_multimodal_dataset.npz) (16.6 MB):
  - **Total windows:** **4,683** standardized 10-second 100 Hz segments.
  - **Total unique clinical patients:** **2,271 unique individuals**.
  - Standardized to 100 Hz (1,000 samples) matching the ESP32 MAX30102 hardware specification.

### 3. Leak-Free Multi-Class Re-Training & Evaluation
- Built dedicated training pipeline [`ml/train_unified_models.py`](ml/train_unified_models.py) using strict **5-Fold `StratifiedGroupKFold` on Patient IDs**.
- Evaluated an 8-class XGBoost classifier across 27 physiological biomarkers:
  - **Out-of-Fold Cross-Validation Accuracy:** **56.97%** (vs 12.5% random guess baseline across 8 classes).
  - **Macro F1-Score:** **46.71%** (zero patient overlap across all folds).
  - High sensitivity on key clinical categories: **Normal F1: 0.7802**, **Bradycardia F1: 0.6542**, **Tachycardia F1: 0.6292**, **AFib F1: 0.5614**.
- Saved validated model artifacts to [`model/`](model/):
  - `model/xgboost_ppg_model.pkl` (investigational screening XGBoost classifier)
  - `model/scaler.pkl` & `model/label_encoder.pkl`
  - `model/confusion_matrix_xgboost.png` & `model/feature_importance_xgboost.png`
  - `model/model_metadata.json` (comprehensive documentation of 2,271 patients, validation scheme, and provenance)
- Verified seamless compatibility with [`backend/api_server.py`](backend/api_server.py) and React web portal.

### 4. Release Consolidation & v3 Single Source of Truth (Oct 2–3 Exit Gate)
- **v3 Authority Enforced**: Standardized all architecture documents, data cards, model cards, manifests, tests, backend contracts, and dashboard labels to **CardioTwin v3**:
  - **8 Rhythm Classes**: `Normal`, `Tachycardia`, `Bradycardia`, `AFib`, `Cardiac_Paced`, `V_Tachycardia`, `V_Flutter_Fib`, `Asystole`.
  - **2,271 Unique Patients** (2,000 from MIMIC-III ICU) and **4,683 Standardized Windows** (10s @ 100 Hz).
  - Out-of-fold metrics: **56.97% Accuracy, 0.4671 Macro-F1, 0.5685 Weighted-F1**.
- **Legacy v2 Safely Isolated**: Archived [`ml/train_model_v2.py`](ml/train_model_v2.py) and redirected its output artifacts to [`model/legacy_v2/`](model/legacy_v2/), preventing accidental overwrite of active v3 artifacts.
- **Regulatory & Prototype Framing**: Eliminated all "production-ready" terminology across the entire repo, consistently framing the system as an **"Investigational Screening Prototype (Non-Diagnostic)"** with mandatory 12-lead ECG review warnings.
- **Frontend Dashboard Synchronization**: Updated [`cardiotwin-dashboard/src/App.jsx`](cardiotwin-dashboard/src/App.jsx) with:
  - Header badge: `v3.0 • Investigational Prototype`
  - Tile 4: `AI RHYTHM SCREENING (v3 - 8 CLASS)` with custom styling for all 8 categories
  - Demo scenario: Added `💓 Atrial Fibrillation` (MIMIC-III cohort trigger)
  - Verified clean production compilation with `npm run build` in 534ms.

### 5. Data-Governance & PhysioNet DUA Hardening (Oct 2–3 Exit Gate)
- **Strict Git Hardening**: Rewrote [`.gitignore`](.gitignore) to explicitly block:
  - `data/raw/` (all raw MIMIC-III waveforms, `.dat`, `.hea`, and 4.92 GB `metadata.csv`)
  - `data/processed/*.npz` (large compiled arrays)
  - `recordings/` (all hardware session dumps)
  - `*.dat`, `*.hea`, `*.mat`, `*.zip`, `.env*`
- **Zero Raw Data Committed**: Verified via `git status -u data/` that **only** the non-identifiable, reproducible [`data/dataset_manifest.json`](data/dataset_manifest.json) is visible to Git.
- **Reproducible Pipeline Launcher**: Authored [`scripts/run_v3_pipeline.py`](scripts/run_v3_pipeline.py) allowing a clean environment with credentialed PhysioNet credentials to rebuild the entire pipeline with one command.

### 6. Hardware Acceptance Testing Risk Analysis & Protocol Definition
- **Identified Primary Technical Risk**: A candid audit of 39 physical MAX30102 session recordings revealed that while the SQI safety gate safely rejects motion artifacts and lead-off states, only **one uninterrupted session exceeded 10 seconds** (yielding a low pulse rate estimate of 39.5 BPM).
- **Correct Non-Diagnostic Stance**: Acknowledged that the physical device prototype cannot yet make confident live-screening claims without systematic empirical validation against a reference standard.
- **Scheduled Oct 5–8 Hardware Acceptance Protocol**:
  - **10 stable 60-second sessions**: Target BPM MAE $\le 5$ BPM against reference pulse oximeter or manual radial pulse count; $\ge 90\%$ accepted windows.
  - **5 deliberate motion sessions**: Verify 100% suppression / gating by SQI.
  - **5 finger-off sessions**: Verify 100% detection of lead-off / sensor disconnected ($\sigma < 0.05$).
  - **Sensor Improvement (Oct 7–9)**: If acceptance testing fails, tune LED current register, optical contact geometry, peak prominence (0.25), distance (0.30s), and SQI threshold.

### 7. Test Suite Verification
- Verified all **17 unit and integration tests** in [`tests/test_cardiotwin.py`](tests/test_cardiotwin.py) passing cleanly (100% OK in 0.025s), validating Framingham boundary clamping, SQI safety gating, What-If simulator, API contracts, manifest integrity, and v3 non-diagnostic metadata.

### 8. Professional Codebase Reorganization & Git Conflict Resolution
- **Resolved Git Submodule Conflict**: The initial repository tracked `ppg-monitor` as an unconfigured Git submodule (`160000 commit`), causing dirty submodule conflicts. Removed the submodule gitlink via `git rm --cached ppg-monitor` and deleted the internal `.git/` folder inside `frontend/mobile/` so all mobile application code (`App.js`, `app.json`, `package.json`, assets) is now cleanly preserved as standard tracked code.
- **Created Unified `frontend/` Hub**:
  - `frontend/web/`: Clinician Decision Support Portal (React 19 + Vite dashboard). Verified `npm run build` passes in 2.04s.
  - `frontend/mobile/`: Patient Wearable Monitor (React Native / Expo app, fully preserved).
- **Created Dedicated `hardware/` Hub**:
  - `hardware/esp32_ppg_sender/`: Contains `esp32_ppg_sender.ino` ready for Arduino IDE flashing.
- **Cleaned and Streamlined `ml/`**:
  - Consolidated historical models into `ml/legacy/` (`train_model_v1.py`, `train_model_v2.py`).
  - Purged redundant one-off generator scripts (`ml/generate_inspector_notebook.py`, `ml/generate_mimic_extractor_notebook.py`, `ml/analyze_real_metadata.py`, `ml/MIMIC_1000_Cohort_Extractor.ipynb`).
  - Preserved `ml/train_unified_models.py`, `ml/build_clean_dataset.py`, and `ml/CardioTwin_1D_CNN_Colab.ipynb`.
- **Eliminated Clutter from Project Root**:
  - Removed duplicate root junctions (`bidmc_ppg`, `physionet_2015`) while keeping raw data safely intact in `data/raw/`.
  - Removed temporary analysis scratch scripts (`scratch/`).
  - Purged `.ipynb_checkpoints/` and all `__pycache__/` directories.
- **Strengthened `.gitignore`**:
  - Added universal build and dependency ignores (`**/node_modules/`, `**/dist/`, `**/.expo/`, `**/.vite/`).
  - Added explicit protection for `metadata.csv`, `PPG_Dataset.csv`, and all raw PhysioNet/MIMIC waveforms.

