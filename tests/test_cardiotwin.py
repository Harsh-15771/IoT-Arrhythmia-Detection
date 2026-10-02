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

# Add project root and backend to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from framingham_risk import calculate_framingham_cvd_risk
from digital_twin_engine import CardioTwin
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

if __name__ == "__main__":
    unittest.main()
