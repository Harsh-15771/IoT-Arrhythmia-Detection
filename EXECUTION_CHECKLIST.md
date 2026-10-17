# 🫀 CardioTwin Sentinel — Master Upgrade Execution Checklist
**Target Event:** Happiest Health Digital Twin Challenge 2026 (Deadline: Oct 20, 2026, 19:00 IST)  
**Objective:** Transform CardioTwin Sentinel v4.1 into a clinically airtight, proactive, multimodal Digital Twin while maintaining 100% pass rate on all existing unit tests.

---

## Progress Overview
- [x] **Phase 1:** Critical Bug Fixes & Contract Alignment (Zero-Regression Foundation) `[5/5]`
- [x] **Phase 2:** Trial-and-Error ML Fusion & Triage Optimization (Experimental Ablation) `[2/2]`
- [x] **Phase 3:** True Multimodal Stream Fusion & Proactive Horizon Forecasting `[2/2]`
- [x] **Phase 4:** Clinically Intelligent "What-If" Treatment Simulator `[1/1]`
- [x] **Phase 5:** Upgrade Clinician Dashboard (`frontend/web/src/App.jsx` & `index.css`) `[3/3]`
- [x] **Phase 6:** Verification, Submission Packaging & 20-Minute Video Blueprint `[2/2]`

---

## Phase 1: Critical Bug Fixes & Contract Alignment (Zero-Regression Foundation)

- [x] **1.1 Fix Live Hardware Persistence Crash in `backend/api_server.py`**
  - [x] Locate `receive_sensor_data()` (~lines 567–573) in `backend/api_server.py`.
  - [x] Change call to `live_persistence_engine.process_window` to pass `raw_pred_label=raw_pred_label` instead of `predicted_class`.
  - [x] Read `pred_label = consensus_eval["consensus_pattern"]` instead of `consensus_class`.
  - [x] In the gated branch (~line 550 of `backend/api_server.py`), include both `"consensus_pattern": pred_label` and `"consensus_class": pred_label` in `consensus_eval` for backward compatibility.
  - [x] Validate live hardware persistence windowing with mock sensor packets without runtime exception.

- [x] **1.2 Fix What-If Simulator Key Mismatch in `backend/digital_twin_engine.py`**
  - [x] Locate `simulate_treatment()` (~lines 258–270) in `backend/digital_twin_engine.py`.
  - [x] Retain existing keys `original_base_risk` and `projected_base_risk` to ensure `tests/test_cardiotwin.py` passes.
  - [x] Add frontend alias key `"current_baseline_risk": self.base_risk_score`.
  - [x] Add frontend alias key `"simulated_baseline_risk": sim_base_risk`.
  - [x] Add frontend alias key `"projected_risk": sim_base_risk`.
  - [x] Verify frontend reads non-zero simulated risk values.

- [x] **1.3 Fix Biological Vascular Age Key Mismatch in `backend/framingham_risk.py`**
  - [x] Locate `compute_cardiovascular_age()` (~lines 174–185) in `backend/framingham_risk.py`.
  - [x] Retain existing keys `integrated_cardiovascular_age` and `age_gap_years`.
  - [x] Add alias key `"estimated_cv_age": integrated_cv_age`.
  - [x] Add alias key `"age_delta": age_gap`.
  - [x] Confirm both web (`App.jsx`) and mobile (`App.js`) render estimated CV age and delta without `undefined`/`NaN`.

- [x] **1.4 Fix Scenario Injector Missing Instability, Waveform, and Baseline State in `backend/api_server.py`**
  - [x] Locate `trigger_scenario()` (`POST /twin/scenario`, ~lines 332–495) in `backend/api_server.py`.
  - [x] Ensure `live_baseline_manager` is seeded with a valid default empirical baseline if none exists when scenario triggers:
    - `median_bpm: 70.0`
    - `mad_bpm: 2.5`
    - `median_rmssd: 42.0`
    - `mad_rmssd: 4.0`
    - `median_rr_cv: 0.06`
    - `mad_rr_cv: 0.015`
    - `windows_accepted: 6`
  - [x] Call `live_baseline_manager.compute_instability(...)` using scenario `bpm`, `rmssd`, `signal_gate["rr_cv"]`, and `signal_gate["ai_screening_enabled"]`.
  - [x] Attach computed instability result to `sim_vitals["personal_instability"]`.
  - [x] Synthesize 180-sample (1.8s @ 100 Hz) morphologically realistic PPG waveform array `scenario_waveform` for each scenario:
    - [x] `calm_normal`: 72 BPM dicrotic pulse wave (period = 83 samples, systolic peak + dicrotic notch).
    - [x] `stress_tachycardia`: 138 BPM rapid monomorphic pulse wave (period = 43 samples, steep upstroke, low HRV).
    - [x] `afib_episode`: Irregularly irregular pulse intervals (periods varying `[38, 62, 41, 79, 45, 58]`) with varying systolic peak amplitudes (`0.6x` to `1.2x` pulse deficit morphology).
    - [x] `motion_artifact`: High-amplitude baseline wander + clipped saturation spikes (`260000` ceiling).
    - [x] `sensor_liftoff`: Flatline (`0.0` with $\pm 0.5$ quantization noise).
  - [x] Attach `"waveform_preview": scenario_waveform` to `sim_vitals`.
  - [x] Emit `socketio.emit("live_waveform", {"chunk": scenario_waveform, "bpm": sim_vitals["bpm"], "spo2": sim_vitals["spo2"], "data_source": "SIMULATION"})`.
  - [x] Verify UI instability gauge and SVG oscilloscope react instantly to scenario triggers.

- [x] **1.5 Add Missing Documented Endpoints (`/fhir/export` and `/baseline/status`) in `backend/api_server.py`**
  - [x] Implement `GET /baseline/status` returning active patient baseline state (`has_calibrated_baseline`, `baseline`, `is_calibrating`).
  - [x] Implement `GET /fhir/export` returning valid HL7 FHIR R4 Bundle (`resourceType: "Bundle"`, `type: "collection"`):
    - [x] `Patient` resource with ABHA ID (`identifier.system = "https://healthid.abdm.gov.in"`).
    - [x] `Device` resource (`cardiotwin-esp32-01`, Firmware `v4.1.0`).
    - [x] `Observation` resources (`LOINC 8867-4`: Heart Rate, `LOINC 80404-7`: RMSSD, `SNOMED 361137007`: Pulse Rhythm Finding, `CARDIOTWIN-INSTABILITY`: Personal Instability Index).
    - [x] `RiskAssessment` resource (`LOINC 79423-0`: 10-Year Recalibrated Framingham CVD Risk + 6-Hour Decompensation Forecast).
  - [x] Preserve `GET /` root response `"version": "3.0.0"` for test compatibility, and add `"release_codename": "v4.1.0-sentinel"`.

---

## Phase 2: Trial-and-Error ML Fusion & Triage Optimization (Experimental Ablation)

- [x] **2.1 Create Experiment Script `scripts/experiment_optimal_fusion.py`**
  - [x] Load saved out-of-fold probability matrices (`model/oof_predictions_classical.npz` and `model/oof_predictions_cnn.npz`).
  - [x] Implement nested 5-fold patient-isolated cross-validation (`StratifiedGroupKFold` on `patient_ids`).
  - [x] Implement & evaluate **Baseline Method A (Global Scalar Late Fusion)**:
    $$\mathbf{P}_{\text{fused}} = w_c \cdot \mathbf{P}_{\text{classical}} + (1 - w_c) \cdot \mathbf{P}_{\text{cnn}}$$
  - [x] Implement & evaluate **Method B (Temperature-Scaled Global Fusion)**:
    $$\mathbf{P}_m(T_m) = \text{softmax}\left(\frac{\log(\mathbf{P}_m + \epsilon)}{T_m}\right)$$
    Optimize $(T_c, T_{\text{cnn}})$ on inner folds.
  - [x] Implement & evaluate **Method C (Class-Specific Dirichlet / Per-Class Reliability Weighting)**:
    Assign class $k \in \{1..8\}$ weight $w_{c,k} \in [0, 1]$ proportional to inner-fold F1 (Tree Ensemble for HRV classes, CNN for morphology classes).
  - [x] Implement & evaluate **Method D (Out-of-Fold Cost-Sensitive Threshold Tuning)**:
    Optimize per-class decision thresholds $\tau_k$ on inner folds.
  - [x] Select winning method by highest leak-free Outer-Fold Macro-F1 (Method B: 54.40% Macro-F1).
  - [x] Promote winning strategy into `DualModalityPredictor.predict_window()` in `backend/dual_engine.py` while preserving existing dictionary contract.

- [x] **2.2 Add 3-Tier Clinical Actionability Benchmark**
  - [x] Calculate triage performance across 3 clinical actionability tiers:
    - **Tier 1 (Normal / Routine Monitoring):** `Normal`
    - **Tier 2 (Actionable Rate / Atrial Anomaly - Non-Emergent ECG Referral):** `AFib`, `Bradycardia`, `Tachycardia`, `Cardiac_Paced`
    - **Tier 3 (Critical Hemodynamic / Ventricular Alarm - Urgent Triage):** `V_Tachycardia`, `V_Flutter_Fib`, `Asystole`
  - [x] Calculate sensitivity, specificity, precision, and F1 score for each tier.
  - [x] Export benchmark metrics to `model/dual_modality_benchmark_v2.json`.
  - [x] Document results in `docs/MODEL_CARD.md`.

---

## Phase 3: True Multimodal Stream Fusion & Proactive Horizon Forecasting ("The Digital Twin Core")

- [x] **3.1 EHR-Conditioned Hemodynamic Coupling (`backend/digital_twin_engine.py`)**
  - [x] Implement `_compute_ehr_vulnerability_coupling(self, bpm, rmssd, rr_cv, pred_rhythm)` in `CardioTwin`.
  - [x] Implement **Pharmacological Beta-Blockade Escape Detection**:
    - [x] Check if `patient_ehr["clinical_history"]["medications"]` contains `"Beta-Blocker"` (`Metoprolol`, `Bisoprolol`).
    - [x] If `True` and `bpm >= 90.0` (or `bpm >= resting_hr + 18.0`), trigger flag `"BETA_BLOCKADE_ESCAPE"`.
  - [x] Implement **Disease-Specific Rhythm Amplification**:
    - [x] If EHR conditions include `"Paroxysmal Atrial Fibrillation"` and live `rr_cv >= 0.18`, trigger `"SUBCLINICAL_AFIB_PRODROME"`.
    - [x] If EHR conditions include `"Coronary Artery Disease"` or `"Type 2 Diabetes Mellitus"` (`hba1c >= 7.0`) and `rmssd < 22.0`, trigger `"AUTONOMIC_VAGAL_WITHDRAWAL"`.
  - [x] Calculate **EHR Substrate Multiplier** ($M_{\text{EHR}} \in [1.00, 1.40]$):
    $$M_{\text{EHR}} = 1.0 + 0.10 \cdot \mathbb{I}(\text{CAD or Post-PCI}) + 0.08 \cdot \mathbb{I}(\text{HbA1c} \ge 7.0) + 0.08 \cdot \mathbb{I}(\text{hs-CRP} > 2.0) + 0.14 \cdot \mathbb{I}(\text{Beta-Blockade Escape})$$
  - [x] Compute **EHR-Coupled Twin Risk Index** while leaving `personal_instability.instability_score` untouched for unit test compliance.

- [x] **3.2 7-Day Wearable Trend & 6-Hour Proactive Adverse Event Forecaster (`backend/digital_twin_engine.py`)**
  - [x] Implement `compute_proactive_forecast(self)` in `CardioTwin` and attach to `get_status()`.
  - [x] Incorporate **7-Day Longitudinal Wearable Context (`wearable_7d_summary`)**:
    - [x] `daily_resting_hr_7d`: 7-day resting HR trend array.
    - [x] `nocturnal_rmssd_7d`: 7-day sleep HRV RMSSD array (ms).
    - [x] `sleep_efficiency_pct_7d`: 7-day sleep efficiency array (%).
    - [x] `daily_steps_7d`: 7-day activity step counts.
  - [x] Implement **Short-Horizon (2-Hour & 6-Hour) State-Space Extrapolation**:
    - [x] Compute acute instability velocity $\frac{dI}{dt}$ and vagal withdrawal $\frac{d(\text{RMSSD})}{dt}$ from rolling buffer + 7-day nocturnal slope:
      $$\hat{I}_{t + \Delta t} = \text{clip}\left(I_t + \left(\beta_{\text{acute}} \cdot \Delta I_{\text{recent}} + \beta_{\text{7d}} \cdot \text{Slope}_{\text{7d}}\right) \cdot M_{\text{EHR}}, \, 0, \, 100\right)$$
    - [x] Output `predicted_instability_2h`: float (0–100).
    - [x] Output `predicted_instability_6h`: float (0–100).
    - [x] Output `adverse_event_horizon_status`: `"STABLE_HORIZON"` | `"EARLY_PRODROMAL_DRIFT"` | `"HIGH_RISK_WITHIN_6H"` | `"IMMINENT_DECOMPENSATION_2H"`.
    - [x] Output `estimated_time_to_threshold_hrs`: float or `null` (hours until instability crosses 70.0).
    - [x] Output `forecast_narrative`: Synthesized clinical explanation combining EHR, 7-day sleep/HRV, and live PPG.

---

## Phase 4: Clinically Intelligent "What-If" Treatment Simulator

- [x] **4.1 Upgrade `simulate_treatment()` in `backend/digital_twin_engine.py`**
  - [x] Inspect `self.patient["clinical_history"]["medications"]` to distinguish existing EHR therapies from new interventions.
  - [x] Label existing medication modifications as **"Adherence & Dose Optimization"** instead of naive initial prescriptions.
  - [x] Add simulation support for:
    - [x] SGLT2 Inhibitor (`Dapagliflozin 10mg`: -18% CVD risk in T2DM/CAD).
    - [x] Glycemic Optimization (`HbA1c < 6.5%`).
  - [x] Structure **Dual-Horizon Simulation Output**:
    - [x] **Long-Term Horizon (10-Year Framingham ASCVD Risk):** `current_baseline_risk` $\to$ `simulated_baseline_risk`, `projected_vascular_age`.
    - [x] **Short-Term Horizon (24-Hour Hemodynamic Twin Response):** `current_hr` $\to$ `simulated_heart_rate`, `projected_rmssd_gain_ms` (+8 to +14 ms vagal recovery), `projected_instability_score`.

---

## Phase 5: Upgrade Clinician Dashboard (`frontend/web/src/App.jsx` & `index.css`)

- [x] **5.1 `Live check` Tab Upgrades**
  - [x] Synchronize Scenario Waveform: Update `waveformPoints` from `data.updated_status.current_vitals.waveform_preview` upon `runScenario(key)`.
  - [x] Add 4-metric Live Biomarker & HRV Strip below the waveform oscilloscope:
    - [x] `RMSSD` (ms) — Parasympathetic vagal tone
    - [x] `SDNN` (ms) — Total interval variability
    - [x] `RR-CV` (%) — Beat-to-beat irregularity index
    - [x] `SQI` (0.00–1.00) — Kurtosis-weighted Signal Quality Index
  - [x] Add Dual-Modality AI Screening & Persistence Panel:
    - [x] Display active 8-class rhythm screening output (`arrhythmia_predicted`) & confidence percentage.
    - [x] Display Modality Split breakdown (e.g., Classical Tree Ensemble vs Inception-1D CNN).
    - [x] Display Multi-Window Persistence consensus status (e.g., `Consensus: 3/4 Windows`).
  - [x] Add Proactive 2h / 6h Early Warning Banner:
    - [x] Display `proactive_forecast.forecast_narrative`.
    - [x] Display `predicted_instability_2h` and `predicted_instability_6h`.
    - [x] Display active `ehr_coupling_flags` (such as `BETA_BLOCKADE_ESCAPE`).

- [x] **5.2 `Your twin` Tab Upgrades**
  - [x] Add Complete EHR Clinical & Lab Card:
    - [x] Display patient lab panel: Total Cholesterol, LDL-C, HDL-C, Triglycerides, Fasting Glucose, HbA1c (%), hs-CRP (mg/L).
    - [x] Highlight abnormal lab values with red/amber badges.
    - [x] Render Active Medications List (`name`, `dosage`, `class`, `hr_effect`, `bp_effect`).
  - [x] Add 7-Day Wearable Sleep & HRV Longitudinal Sparkline Card:
    - [x] Render 7-day trajectories for Resting HR, Nocturnal RMSSD (ms), Sleep Efficiency (%), Daily Steps.
  - [x] Add ABDM HL7 FHIR R4 Export Button:
    - [x] Add "Export ABDM FHIR R4 Bundle" button fetching `GET /fhir/export`.
    - [x] Trigger download of formatted `cardiotwin_fhir_r4_<patient_id>.json`.

- [x] **5.3 `Explore changes` (What-If) Tab Upgrades**
  - [x] Display active EHR medications vs additional/optimized interventions (including Dapagliflozin 10mg SGLT2i).
  - [x] Display side-by-side outcomes:
    - [x] 10-Year CVD Event Risk Reduction (`current_baseline_risk` $\to$ `simulated_baseline_risk`).
    - [x] Projected Biological Vascular Age Shift (`vascular_age` $\to$ `projected_vascular_age`).
    - [x] Simulated Hemodynamic Twin Response (`Resting HR` and `Projected Systolic BP`).

---

## Phase 6: Verification, Submission Packaging & 20-Minute Video Blueprint

- [x] **6.1 Automated Test Suite Verification**
  - [x] Run full test suite: `python -m unittest discover -s tests -p "test_*.py" -v`.
  - [x] Add test for `GET /fhir/export` verifying valid HL7 FHIR R4 Bundle (`resourceType == "Bundle"`).
  - [x] Add test for `proactive_forecast` and `ehr_coupling` presence in `/twin/status`.
  - [x] Add test for `simulate_treatment` returning both `projected_base_risk` and `simulated_baseline_risk`.
  - [x] Add test for `compute_cardiovascular_age` returning both `integrated_cardiovascular_age` and `estimated_cv_age`.
  - [x] Add test for `POST /twin/scenario` populating `personal_instability` and `waveform_preview`.
  - [x] Ensure 100% pass rate across all automated unit tests (54/54 passing, zero regression).

- [x] **6.2 README & Documentation Synchronization**
  - [x] Update `README.md` step 4 to identify `PAT001` as Praveen Choudhury (63M, Post-PCI CAD) in alignment with `backend/synthetic_patients.json`.
  - [x] Ensure submission archive folder naming matches `Root Access_Visvesvaraya National Institute of Technology Nagpur`.
  - [x] Structure and record 20+ minute demonstration video ($\ge 20:30$) covering hardware, twin math, proactive forecasting, and What-If simulation.
