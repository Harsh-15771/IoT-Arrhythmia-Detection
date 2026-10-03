"""
CardioTwin - Automated Test & Submission Verification Suite
Tests:
  1. Clinical Framingham Risk Engine & Age Boundary Clamping
  2. Digital Twin Multimodal Fusion & SQI Gating
  3. API Server Endpoints & Hardware Integration Contract (dual keys: values/samples)
  4. Device Command Synchronization (/command)
  5. Leak-Free Model Artifacts & Metadata Integrity
"""

import os
import sys
import json
import unittest
import numpy as np
import time

# Add project root and backend to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from framingham_risk import calculate_framingham_cvd_risk
from digital_twin_engine import CardioTwin
from signal_gate import SignalReliabilityGate
from dual_engine import DualModalityPredictor
from pulse_rules import PhysiologicalPulseRules, MultiWindowPersistenceEngine
import api_server

class TestCardioTwinClinicalEngine(unittest.TestCase):
    def test_standard_framingham_calculation(self):
        # 55-year old Indian male smoker with hypertension
        res = calculate_framingham_cvd_risk(
            age=55, gender="male", systolic_bp=145, bp_treated=True,
            total_cholesterol=230, hdl_cholesterol=38, smoker=True,
            diabetes=True, is_south_asian=True
        )
        self.assertIn("base_10yr_risk_pct", res)
        self.assertIn("recalibrated_risk_pct", res)
        self.assertGreater(res["recalibrated_risk_pct"], res["base_10yr_risk_pct"])
        self.assertEqual(res["risk_category"], "High")
        self.assertFalse(res["age_extrapolated"])
        self.assertEqual(res["exploratory_factor_value"], 1.45)

    def test_age_boundary_handling_young(self):
        # Age 25 (below derivation cohort 30-74)
        res = calculate_framingham_cvd_risk(
            age=25, gender="female", systolic_bp=118, bp_treated=False,
            total_cholesterol=170, hdl_cholesterol=55, smoker=False,
            diabetes=False, is_south_asian=True
        )
        self.assertTrue(res["age_extrapolated"])
        self.assertTrue(any("below Framingham derivation cohort" in c for c in res["clinical_caveats"]))
        self.assertLess(res["recalibrated_risk_pct"], 15.0)

    def test_age_boundary_handling_elderly(self):
        # Age 80 (above derivation cohort 30-74)
        res = calculate_framingham_cvd_risk(
            age=80, gender="male", systolic_bp=150, bp_treated=True,
            total_cholesterol=210, hdl_cholesterol=42, smoker=False,
            diabetes=True, is_south_asian=True
        )
        self.assertTrue(res["age_extrapolated"])
        self.assertTrue(any("above Framingham derivation cohort" in c for c in res["clinical_caveats"]))


class TestDigitalTwinStateAndGating(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(BACKEND_DIR, "synthetic_patients.json"), "r") as f:
            patients = json.load(f)
        self.twin = CardioTwin(patients[0])

    def test_risk_separation(self):
        status = self.twin.get_status()
        self.assertIn("baseline_10yr_cvd_risk_pct", status)
        self.assertIn("physiological_instability_score", status)
        self.assertIn("clinical_disclaimer", status)

    def test_sqi_gating_suppresses_false_alarms(self):
        # Feed high-noise / low-quality data (SQI: 0.15)
        initial_alerts_len = len(self.twin.alert_log)
        update_result = self.twin.update_telemetry({
            "bpm": 150, "rmssd": 8.0, "spo2": 96, "signal_quality": 0.15,
            "arrhythmia_predicted": "V_Tachycardia" # Raw classifier mistake during motion
        })
        # Verify that critical rhythm alert was NOT logged due to SQI gating
        critical_alerts = [a for a in self.twin.alert_log if a.get("category") == "RHYTHM"]
        self.assertEqual(len(critical_alerts), 0)
        # Verify signal quality warning was recorded
        sq_alerts = [a for a in self.twin.alert_log if a.get("category") == "SIGNAL_QUALITY"]
        self.assertGreaterEqual(len(sq_alerts), 1)

    def test_what_if_simulator(self):
        sim = self.twin.simulate_treatment({
            "add_medications": ["Metoprolol", "Atorvastatin"],
            "systolic_bp": 125,
            "smoker": False
        })
        self.assertIn("time_horizon", sim)
        self.assertIn("absolute_risk_reduction", sim)
        self.assertGreater(sim["absolute_risk_reduction"], 0.0)


class TestAPIServerContract(unittest.TestCase):
    def setUp(self):
        api_server.app.testing = True
        self.client = api_server.app.test_client()
        with api_server.state_lock:
            api_server.state["is_recording"] = False
            if api_server.state.get("csv_file"):
                try:
                    api_server.state["csv_file"].close()
                except Exception:
                    pass
                api_server.state["csv_file"] = None

    def tearDown(self):
        with api_server.state_lock:
            if api_server.state.get("is_recording"):
                api_server.state["is_recording"] = False
            if api_server.state.get("csv_file"):
                try:
                    api_server.state["csv_file"].close()
                except Exception:
                    pass
                api_server.state["csv_file"] = None


    def test_index_route(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["version"], "3.0.0")
        self.assertEqual(data["status"], "Investigational Screening Prototype (Non-Diagnostic)")

    def test_device_command_polling(self):
        # GET /command
        res = self.client.get("/command")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("run", data)
        self.assertIn("status", data)

        # POST /command (toggle state)
        post_res = self.client.post("/command", json={"run": True})
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.get_json()["run"])

    def test_data_ingest_samples_key(self):
        # ESP32 firmware sends {"samples": [...]}
        payload = {"samples": [100.0, 102.0, 104.0, 101.0], "bpm": 74, "spo2": 98}
        res = self.client.post("/data", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["samples_received"], 4)

    def test_data_ingest_values_key(self):
        # Web / API client sends {"values": [...]}
        payload = {"values": [95.0, 96.0, 97.0, 95.5], "bpm": 72, "spo2": 99}
        res = self.client.post("/data", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["samples_received"], 4)

    def test_ingest_telemetry_alias(self):
        # Alternative alias endpoint
        payload = {"samples": [110.0, 112.0], "bpm": 80}
        res = self.client.post("/ingest_telemetry", json=payload)
        self.assertEqual(res.status_code, 200)

    def test_truthful_telemetry_hardware_contract(self):
        # Hardware sends sequence, first_sample_ms, device_bpm, no fake SpO2
        payload = {
            "device_id": "cardiotwin-esp32-01",
            "sequence": 142,
            "first_sample_ms": 105432,
            "sample_interval_us": 10000,
            "values": [82000.0, 82100.0, 82050.0],
            "device_bpm": None
        }
        res = self.client.post("/data", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["samples_received"], 3)
        self.assertEqual(body["last_accepted_seq"], 142)

        # Check twin telemetry did NOT fabricate SpO2
        twin_res = self.client.get("/twin/status")
        vitals = twin_res.get_json()["current_vitals"]
        self.assertIsNone(vitals.get("spo2"))
        self.assertEqual(vitals.get("spo2_status"), "UNAVAILABLE_NO_RED_CHANNEL")

    def test_scenario_explicit_provenance(self):
        res = self.client.post("/twin/scenario", json={"scenario": "calm_normal"})
        self.assertEqual(res.status_code, 200)
        status = res.get_json()["updated_status"]
        self.assertEqual(status["data_source"], "SIMULATION")

    def test_patients_cohort_endpoints(self):
        res = self.client.get("/patients")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("patients", data)
        self.assertEqual(data["total"], 100)

        # Detail endpoint
        det = self.client.get("/patient/PAT001")
        self.assertEqual(det.status_code, 200)
        self.assertEqual(det.get_json()["id"], "PAT001")

        # Select patient
        sel = self.client.post("/patient/select", json={"patient_id": "PAT002"})
        self.assertEqual(sel.status_code, 200)
        self.assertTrue(sel.get_json()["success"])

    def test_twin_status_and_simulation_endpoints(self):
        status_res = self.client.get("/twin/status")
        self.assertEqual(status_res.status_code, 200)
        status = status_res.get_json()
        self.assertIn("patient_id", status)
        self.assertIn("baseline_10yr_cvd_risk_pct", status)
        self.assertIn("physiological_instability_score", status)

        # Simulation endpoint
        sim_res = self.client.post("/twin/simulate", json={
            "add_medications": ["Atorvastatin"],
            "systolic_bp": 130
        })
        self.assertEqual(sim_res.status_code, 200)
        sim_data = sim_res.get_json()
        self.assertTrue(sim_data["success"])
        self.assertIn("absolute_risk_reduction", sim_data["simulation"])

    def test_recording_control_endpoints(self):
        start_res = self.client.post("/start")
        self.assertEqual(start_res.status_code, 200)
        self.assertEqual(start_res.get_json()["status"], "started")

        stop_res = self.client.post("/stop")
        self.assertEqual(stop_res.status_code, 200)
        stop_data = stop_res.get_json()
        self.assertEqual(stop_data["status"], "stopped")
        saved_file = stop_data.get("saved_to")
        if saved_file and os.path.exists(saved_file):
            try:
                os.remove(saved_file)
            except Exception:
                pass





class TestSignalReliabilityGate(unittest.TestCase):
    def setUp(self):
        self.gate = SignalReliabilityGate(
            target_fs=100.0,
            window_sec=10.0,
            stability_threshold=3,
            min_bpm=40.0,
            max_bpm=180.0
        )

    def test_finger_off_detection(self):
        # Flatline / zero amplitude
        flat_signal = np.zeros(1000)
        res = self.gate.evaluate_window(flat_signal)
        self.assertEqual(res["status"], "FINGER_OFF")
        self.assertFalse(res["ai_screening_enabled"])
        self.assertEqual(res["metrics"]["bpm"], 0.0)

    def test_adc_saturation_detection(self):
        # Clipped / saturated raw samples
        saturated_signal = np.full(1000, 262143.0)
        res = self.gate.evaluate_window(saturated_signal)
        self.assertEqual(res["status"], "SENSOR_SATURATED")
        self.assertFalse(res["ai_screening_enabled"])

    def test_sample_timing_drop_detection(self):
        # High jitter / dropped samples (40ms gaps instead of 10ms)
        t = np.linspace(0, 10, 1000)
        clean_pulse = 2000.0 + 300.0 * np.sin(2 * np.pi * 1.2 * t)
        jittery_timestamps = np.cumsum(np.random.choice([10.0, 45.0], size=1000, p=[0.7, 0.3]))
        res = self.gate.evaluate_window(clean_pulse, timestamps_ms=jittery_timestamps)
        self.assertEqual(res["status"], "POOR_TIMING")
        self.assertFalse(res["ai_screening_enabled"])

    def test_physiological_plausibility_verify_signal(self):
        # Pulse at 240 BPM (4 Hz) -> exceeds 180 BPM resting bound
        t = np.linspace(0, 10, 1000)
        tachy_pulse = 2000.0 + 300.0 * np.sin(2 * np.pi * 4.0 * t)
        ts = np.linspace(0, 10000, 1000)
        
        # Window 1: quality ok, marked for recheck
        res1 = self.gate.evaluate_window(tachy_pulse, timestamps_ms=ts)
        self.assertTrue(res1["signal_quality"]["screening_allowed"])
        self.assertTrue(res1["physiological_observation"]["recheck_recommended"])
        self.assertEqual(res1["physiological_observation"]["rate_state"], "EXTREME_HIGH")
        
        # Stabilize to 3 windows -> RECHECK_REQUIRED with AI screening enabled (does NOT block pathology!)
        self.gate.evaluate_window(tachy_pulse, timestamps_ms=ts)
        res3 = self.gate.evaluate_window(tachy_pulse, timestamps_ms=ts)
        self.assertEqual(res3["status"], "RECHECK_REQUIRED")
        self.assertTrue(res3["ai_screening_enabled"])
        self.assertIn("outside resting range", res3["reason"])

    def test_synthetic_afib_passes_quality_gate(self):
        # Synthetic irregular rhythm (AFib): variable RR intervals -> RR CV > 0.35
        # Must NOT be blocked as noise; must pass quality gate and reach the screening model!
        self.gate.reset()
        t = np.linspace(0, 10, 1000)
        peak_times = [0.5, 0.9, 1.8, 2.2, 3.5, 3.9, 5.2, 5.6, 7.0, 7.5, 8.8, 9.3]
        irregular_pulse = np.full(1000, 2000.0)
        for pt in peak_times:
            irregular_pulse += 350.0 * np.exp(-((t - pt)**2) / (2 * (0.05**2)))
        ts = np.linspace(0, 10000, 1000)

        self.gate.evaluate_window(irregular_pulse, timestamps_ms=ts)
        self.gate.evaluate_window(irregular_pulse, timestamps_ms=ts)
        res = self.gate.evaluate_window(irregular_pulse, timestamps_ms=ts)

        self.assertTrue(res["signal_quality"]["screening_allowed"])
        self.assertTrue(res["ai_screening_enabled"])
        self.assertEqual(res["status"], "IRREGULAR_RHYTHM")
        self.assertEqual(res["physiological_observation"]["irregularity_state"], "IRREGULAR_PULSE_OBSERVATION")
        self.assertGreater(res["metrics"]["rr_cv"], 0.35)

    def test_synthetic_bradycardia_passes_quality_gate(self):
        # Synthetic 38 BPM pulse (0.633 Hz) -> below 40 BPM resting bound
        # Must pass quality gate and reach screening model with RECHECK_REQUIRED tag
        self.gate.reset()
        t = np.linspace(0, 10, 1000)
        brady_pulse = 2000.0 + 400.0 * np.sin(2 * np.pi * 0.633 * t)
        ts = np.linspace(0, 10000, 1000)

        self.gate.evaluate_window(brady_pulse, timestamps_ms=ts)
        self.gate.evaluate_window(brady_pulse, timestamps_ms=ts)
        res = self.gate.evaluate_window(brady_pulse, timestamps_ms=ts)

        self.assertTrue(res["signal_quality"]["screening_allowed"])
        self.assertTrue(res["ai_screening_enabled"])
        self.assertEqual(res["status"], "RECHECK_REQUIRED")
        self.assertEqual(res["physiological_observation"]["rate_state"], "EXTREME_LOW")

    def test_window_stability_escalation(self):
        # Clean 72 BPM pulse (1.2 Hz) across 3 consecutive windows
        t = np.linspace(0, 10, 1000)
        clean_pulse = 2000.0 + 400.0 * np.sin(2 * np.pi * 1.2 * t)
        ts = np.linspace(0, 10000, 1000)

        # Window 1: STABILIZING (1/3)
        res1 = self.gate.evaluate_window(clean_pulse, timestamps_ms=ts)
        self.assertEqual(res1["status"], "STABILIZING")
        self.assertFalse(res1["ai_screening_enabled"])
        self.assertEqual(res1["consecutive_good_windows"], 1)

        # Window 2: STABILIZING (2/3)
        res2 = self.gate.evaluate_window(clean_pulse, timestamps_ms=ts)
        self.assertEqual(res2["status"], "STABILIZING")
        self.assertFalse(res2["ai_screening_enabled"])
        self.assertEqual(res2["consecutive_good_windows"], 2)

        # Window 3: RELIABLE (3/3) -> AI SCREENING ENABLED!
        res3 = self.gate.evaluate_window(clean_pulse, timestamps_ms=ts)
        self.assertEqual(res3["status"], "RELIABLE")
        self.assertTrue(res3["ai_screening_enabled"])
        self.assertEqual(res3["consecutive_good_windows"], 3)

        # Verify all 5 core metrics present
        m = res3["metrics"]
        self.assertIn("sample_rate_estimate", m)
        self.assertIn("bpm", m)
        self.assertIn("peak_coverage", m)
        self.assertIn("rr_cv", m)
        self.assertIn("clipping_ratio", m)
        self.assertAlmostEqual(m["sample_rate_estimate"], 100.0, delta=2.0)
        self.assertAlmostEqual(m["bpm"], 72.0, delta=5.0)
        self.assertGreater(m["peak_coverage"], 0.70)
        self.assertLess(m["rr_cv"], 0.20)
        self.assertEqual(m["clipping_ratio"], 0.0)

    def test_signal_gate_rest_endpoint(self):
        client = api_server.app.test_client()
        res = client.get("/signal/gate")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("status", data)
        self.assertIn("metrics", data)
        self.assertIn("sample_rate_estimate", data["metrics"])


class TestModelArtifactsAndManifest(unittest.TestCase):
    def test_dataset_manifest_exists(self):
        manifest_path = os.path.join(ROOT_DIR, "data", "dataset_manifest.json")
        self.assertTrue(os.path.exists(manifest_path))
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["total_patients"], 2271)
        self.assertEqual(manifest["total_windows"], 4683)
        self.assertEqual(len(manifest["classes"]), 8)
        self.assertIn("AFib", manifest["classes"])
        self.assertIn("Cardiac_Paced", manifest["classes"])
        self.assertEqual(manifest["status"], "Investigational Screening Prototype (Non-Diagnostic)")

    def test_model_metadata_rigor(self):
        metadata_path = os.path.join(ROOT_DIR, "model", "model_metadata.json")
        self.assertTrue(os.path.exists(metadata_path))
        with open(metadata_path, "r") as f:
            meta = json.load(f)
        self.assertEqual(meta["num_features"], 27)
        self.assertEqual(meta["total_patients"], 2271)
        self.assertEqual(meta["total_windows"], 4683)
        self.assertEqual(len(meta["classes"]), 8)
        self.assertIn("AFib", meta["classes"])
        self.assertIn("Cardiac_Paced", meta["classes"])
        self.assertNotIn("Production-Ready", meta.get("status", ""))
        self.assertEqual(meta["status"], "Investigational Screening Prototype (Non-Diagnostic)")
        self.assertIn("evaluation_protocol", meta)
        self.assertIn("cv_5fold_macro_f1_mean", meta)
        self.assertIn("leak_free_verification", meta)
        self.assertIn("ci_95_macro_f1", meta)

class TestHierarchicalDecisionArchitecture(unittest.TestCase):
    def setUp(self):
        from backend.pulse_rules import PhysiologicalPulseRules, MultiWindowPersistenceEngine
        self.pulse_rules = PhysiologicalPulseRules(sustained_window_count=3)
        self.persistence = MultiWindowPersistenceEngine(memory_windows=4, consensus_threshold=3)

    def test_deterministic_pulse_rules_low_and_typical(self):
        # Low pulse rate (< 50 BPM)
        res_low = self.pulse_rules.evaluate(bpm=44.0, spo2=98.0, signal_reliable=True)
        self.assertEqual(res_low["pulse_state"], "LOW_PULSE_RATE")
        self.assertIn("LOW_PULSE_RATE", res_low["observation_flags"])

        # Typical resting range (50-100 BPM)
        res_typ = self.pulse_rules.evaluate(bpm=72.0, spo2=98.0, signal_reliable=True)
        self.assertEqual(res_typ["pulse_state"], "TYPICAL_RESTING")
        self.assertEqual(res_typ["observation_flags"], [])

    def test_deterministic_pulse_rules_sustained_elevated(self):
        self.pulse_rules.reset()
        # Window 1: Elevated (not yet sustained)
        r1 = self.pulse_rules.evaluate(bpm=128.0, spo2=98.0, signal_reliable=True)
        self.assertEqual(r1["pulse_state"], "ELEVATED_PULSE_RATE")

        # Window 2: Elevated
        r2 = self.pulse_rules.evaluate(bpm=130.0, spo2=97.0, signal_reliable=True)
        self.assertEqual(r2["pulse_state"], "ELEVATED_PULSE_RATE")

        # Window 3: Sustained Elevated (> 120 for 3 windows)
        r3 = self.pulse_rules.evaluate(bpm=125.0, spo2=98.0, signal_reliable=True)
        self.assertEqual(r3["pulse_state"], "SUSTAINED_ELEVATED")
        self.assertIn("SUSTAINED_ELEVATED_PULSE_RATE", r3["observation_flags"])

    def test_deterministic_oxygenation_review_flag(self):
        self.pulse_rules.reset()
        # 3 consecutive windows under 92% SpO2
        self.pulse_rules.evaluate(bpm=75.0, spo2=90.0, signal_reliable=True)
        self.pulse_rules.evaluate(bpm=75.0, spo2=89.0, signal_reliable=True)
        r3 = self.pulse_rules.evaluate(bpm=75.0, spo2=91.0, signal_reliable=True)
        self.assertEqual(r3["oxygenation_state"], "OXYGENATION_REVIEW_FLAG")
        self.assertIn("OXYGENATION_REVIEW_FLAG", r3["observation_flags"])

    def test_multi_window_persistence_suppresses_transient_spike(self):
        self.persistence.reset()
        probs_vt = {"V_Tachycardia": 0.85, "Normal": 0.10}
        probs_normal = {"Normal": 0.85, "V_Tachycardia": 0.10}

        # Window 1: Normal
        r1 = self.persistence.process_window("Normal", probs_normal, signal_reliable=True)
        self.assertEqual(r1["screening_status"], "STABLE_NORMAL")
        self.assertFalse(r1["is_persistent"])

        # Window 2: Transient single-window VT spike -> MUST BE SUPPRESSED!
        r2 = self.persistence.process_window("V_Tachycardia", probs_vt, signal_reliable=True)
        self.assertEqual(r2["screening_status"], "MONITORING_TRANSIENT")
        self.assertFalse(r2["is_persistent"])
        self.assertIn("Awaiting multi-window persistence", r2["alert_message"])

    def test_multi_window_persistence_triggers_after_consensus(self):
        self.persistence.reset()
        probs_vt = {"V_Tachycardia": 0.85, "Normal": 0.05}

        # Window 1: VT (1/4) -> Transient
        r1 = self.persistence.process_window("V_Tachycardia", probs_vt, signal_reliable=True)
        self.assertFalse(r1["is_persistent"])

        # Window 2: VT (2/4) -> Transient
        r2 = self.persistence.process_window("V_Tachycardia", probs_vt, signal_reliable=True)
        self.assertFalse(r2["is_persistent"])

        # Window 3: VT (3/4) -> CONSENSUS REACHED -> Persistent Alert!
        r3 = self.persistence.process_window("V_Tachycardia", probs_vt, signal_reliable=True)
        self.assertTrue(r3["is_persistent"])
        self.assertEqual(r3["screening_status"], "PERSISTENT_NON_NORMAL")
        self.assertIn("Persistent abnormal pulse pattern detected", r3["alert_message"])
        self.assertIn("Obtain 12-lead ECG review", r3["alert_message"])

    def test_asymmetric_evidentiary_threshold(self):
        self.persistence.reset()
        # VT with low confidence (0.60 < 0.75 threshold) -> demoted from critical alert!
        weak_vt = {"V_Tachycardia": 0.60, "Normal": 0.35}
        r = self.persistence.process_window("V_Tachycardia", weak_vt, signal_reliable=True)
        self.assertNotEqual(r["current_window_label"], "V_Tachycardia")


class TestDualModalityProductionEngine(unittest.TestCase):
    def setUp(self):
        model_dir = os.path.join(ROOT_DIR, "model")
        self.predictor = DualModalityPredictor(model_dir)

    def test_dual_predictor_initialization(self):
        self.assertTrue(self.predictor.classical_loaded or self.predictor.dl_loaded)
        self.assertEqual(len(self.predictor.classes), 8)

    def test_dual_modality_window_fusion(self):
        # 1,000 samples @ 100 Hz
        sig_window = np.sin(np.linspace(0, 10 * 2 * np.pi, 1000))
        dummy_feats = {
            "bpm": 72.0, "rmssd": 35.0, "sdnn": 40.0, "pnn50": 0.15,
            "hrv_cv": 0.05, "ibi_mean": 833.0, "sqi": 0.95
        }
        res = self.predictor.predict_window(sig_window, dummy_feats, w_classical=0.30, w_dl=0.70)
        self.assertIn("predicted_label", res)
        self.assertIn("confidence", res)
        self.assertIn("probabilities", res)
        self.assertEqual(len(res["probabilities"]), 8)
        prob_sum = sum(res["probabilities"].values())
        self.assertAlmostEqual(prob_sum, 1.0, places=2)
        self.assertGreaterEqual(res["confidence"], 0.0)
        self.assertLessEqual(res["confidence"], 1.0)


class TestPersonalBaselineEngine(unittest.TestCase):
    def setUp(self):
        from backend.personal_baseline import PersonalBaselineManager, BASELINES_DIR
        self.patient_id = "TEST_P999"
        self.manager = PersonalBaselineManager(self.patient_id)
        self.test_json = os.path.join(BASELINES_DIR, f"{self.patient_id}.json")

    def tearDown(self):
        if os.path.exists(self.test_json):
            try:
                os.remove(self.test_json)
            except Exception:
                pass

    def test_calibration_and_persistence(self):
        self.manager.start_calibration()
        # Feed 6 quality windows (around 68-72 BPM, 35-40 RMSSD)
        for bpm in [70.0, 72.0, 69.0, 71.0, 70.0, 73.0]:
            self.manager.calibration_windows.append({
                "bpm": bpm, "rmssd": 38.0, "rr_cv": 0.08, "sqi": 0.95, "timestamp": time.time()
            })
        res = self.manager.finalize_calibration()
        self.assertEqual(res["status"], "CALIBRATION_COMPLETE")
        b = res["baseline"]
        self.assertEqual(b["patient_id"], self.patient_id)
        self.assertAlmostEqual(b["median_bpm"], 70.5, delta=1.5)
        self.assertTrue(os.path.exists(self.test_json))

        # Test persistence across restarts
        from backend.personal_baseline import PersonalBaselineManager
        reloaded = PersonalBaselineManager(self.patient_id)
        self.assertIsNotNone(reloaded.baseline)
        self.assertEqual(reloaded.baseline["median_bpm"], b["median_bpm"])

    def test_instability_resting_vs_departure(self):
        # Establish known baseline
        self.manager.baseline = {
            "median_bpm": 70.0,
            "mad_bpm": 3.0,
            "median_rmssd": 40.0,
            "mad_rmssd": 5.0,
            "median_rr_cv": 0.08,
            "mad_rr_cv": 0.02
        }

        # 1. Normal resting -> instability 0–20 (Stable)
        res_stable = self.manager.compute_instability(current_bpm=71.0, current_rmssd=39.0, current_rr_cv=0.08, is_quality_reliable=True)
        self.assertLessEqual(res_stable["instability_score"], 20.0)
        self.assertEqual(res_stable["status_label"], "Stable")

        # 2. 30%+ increase (105 BPM) -> sustained departure (instability 40–70)
        # Feed 3 consecutive high windows to trigger sustained memory
        self.manager.compute_instability(current_bpm=105.0, current_rmssd=20.0, current_rr_cv=0.15, is_quality_reliable=True)
        self.manager.compute_instability(current_bpm=106.0, current_rmssd=18.0, current_rr_cv=0.16, is_quality_reliable=True)
        res_dep = self.manager.compute_instability(current_bpm=104.0, current_rmssd=19.0, current_rr_cv=0.15, is_quality_reliable=True)
        self.assertGreaterEqual(res_dep["instability_score"], 40.0)
        self.assertTrue(res_dep["review_recommended"])

        # 3. Return to baseline -> drops back to Stable within 3 windows
        self.manager.compute_instability(current_bpm=70.0, current_rmssd=38.0, current_rr_cv=0.08, is_quality_reliable=True)
        self.manager.compute_instability(current_bpm=71.0, current_rmssd=40.0, current_rr_cv=0.08, is_quality_reliable=True)
        res_recovered = self.manager.compute_instability(current_bpm=70.0, current_rmssd=39.0, current_rr_cv=0.07, is_quality_reliable=True)
        self.assertLessEqual(res_recovered["instability_score"], 20.0)
        self.assertEqual(res_recovered["status_label"], "Stable")

    def test_unreliable_signal_returns_none(self):
        res = self.manager.compute_instability(current_bpm=72.0, current_rmssd=35.0, current_rr_cv=0.08, is_quality_reliable=False)
        self.assertIsNone(res["instability_score"])
        self.assertIn("Measurement Unreliable", res["status_label"])


if __name__ == "__main__":
    unittest.main()

