"""
CardioTwin v4.1 — Target Product Instability Validation Suite
================================================================================
Phase 5 of CardioTwin v4.1 Engineering Plan:
Validates the actual v4 product target: Personalized Cardiovascular Instability Engine
against the controlled physiological and hardware test protocol matrix:

Test condition                     Expected System Response
--------------------------------------------------------------------------------
1. Quiet seated baseline           Stable (Instability 0–20, flags: [])
2. Finger off                      Measurement unreliable (Gated, score: null)
3. Hand movement (motion)          Measurement unreliable (Gated, score: null)
4. Standing transition             Mild temporary departure (Instability 20–40)
5. Post-standing recovery          Return toward baseline (Decays to < 20)
6. Sustained high pulse            Sustained departure / review (Instability 40–100)
7. Irregular pulse (AFib pattern)  Sustained departure (Instability >= 40, review)
"""

import os
import time
import unittest
import numpy as np
from backend.personal_baseline import PersonalBaselineManager, BASELINES_DIR
from backend.signal_gate import SignalReliabilityGate


class TestCardioTwinTargetValidation(unittest.TestCase):
    def setUp(self):
        self.patient_id = "TARGET_VAL_P001"
        self.manager = PersonalBaselineManager(self.patient_id)
        self.gate = SignalReliabilityGate(target_fs=100.0, window_sec=10.0)
        self.test_json = os.path.join(BASELINES_DIR, f"{self.patient_id}.json")

        # Establish standardized empirical resting baseline (70 BPM, MAD 3.0, RMSSD 40.0, RR-CV 0.08)
        now_ts = time.time()
        self.manager.baseline = {
            "patient_id": self.patient_id,
            "device_id": "cardiotwin-esp32-01",
            "firmware_version": "4.1.0",
            "sensor_settings": {"led_current_ma": 6.0, "sample_rate_hz": 100},
            "calibrated_at_ts": now_ts,
            "expires_at_ts": now_ts + (30 * 86400),
            "windows_accepted": 6,
            "median_bpm": 70.0,
            "mad_bpm": 3.0,
            "median_rmssd": 40.0,
            "mad_rmssd": 5.0,
            "median_rr_cv": 0.08,
            "mad_rr_cv": 0.02
        }

    def tearDown(self):
        if os.path.exists(self.test_json):
            try:
                os.remove(self.test_json)
            except Exception:
                pass

    def test_condition_1_quiet_seated_baseline(self):
        """Condition 1: Quiet seated baseline -> Stable (0–20)."""
        res = self.manager.compute_instability(
            current_bpm=71.0, current_rmssd=39.5, current_rr_cv=0.08, is_quality_reliable=True
        )
        self.assertIsNotNone(res["instability_score"])
        self.assertLessEqual(res["instability_score"], 20.0)
        self.assertEqual(res["status_label"], "Stable")
        self.assertFalse(res["review_recommended"])
        self.assertEqual(len(res["departure_flags"]), 0)

    def test_condition_2_finger_off_sensor(self):
        """Condition 2: Finger off -> Measurement unreliable (Gated)."""
        # Flatline optical signal
        flatline = np.zeros(1000)
        gate_res = self.gate.evaluate_window(flatline)
        self.assertFalse(gate_res["signal_quality"]["screening_allowed"])
        self.assertEqual(gate_res["status"], "FINGER_OFF")

        # Instability engine response
        instability_res = self.manager.compute_instability(
            current_bpm=None, current_rmssd=None, current_rr_cv=None, is_quality_reliable=False
        )
        self.assertIsNone(instability_res["instability_score"])
        self.assertIn("Measurement Unreliable", instability_res["status_label"])
        self.assertIn("UNRELIABLE_SIGNAL", instability_res["departure_flags"])

    def test_condition_3_hand_movement_artifact(self):
        """Condition 3: Hand movement -> Measurement unreliable (Gated)."""
        # Motion artifact creating transimpedance amplifier saturation (>5% samples clipped at 18-bit ceiling)
        motion_sig = 120000.0 + 40000.0 * np.sin(2 * np.pi * 1.2 * np.linspace(0, 10, 1000))
        motion_sig[150:250] = 265000.0  # 10% samples saturate ADC ceiling (260k limit)

        gate_res = self.gate.evaluate_window(motion_sig)
        self.assertFalse(gate_res["signal_quality"]["screening_allowed"])
        self.assertEqual(gate_res["status"], "SENSOR_SATURATED")

        # Instability engine response when gated
        instability_res = self.manager.compute_instability(
            current_bpm=142.0, current_rmssd=88.0, current_rr_cv=0.44, is_quality_reliable=False
        )
        self.assertIsNone(instability_res["instability_score"])
        self.assertIn("Measurement Unreliable", instability_res["status_label"])

    def test_condition_4_standing_transition(self):
        """Condition 4: Standing transition -> Mild temporary departure (20–40)."""
        # Orthostatic rise: BPM +18, mild RMSSD decrease, clean optical contact
        res = self.manager.compute_instability(
            current_bpm=88.0, current_rmssd=28.0, current_rr_cv=0.09, is_quality_reliable=True
        )
        self.assertIsNotNone(res["instability_score"])
        self.assertGreaterEqual(res["instability_score"], 20.0)
        self.assertLessEqual(res["instability_score"], 40.0)
        self.assertEqual(res["status_label"], "Mild departure from baseline")
        self.assertFalse(res["review_recommended"])

    def test_condition_5_post_standing_recovery(self):
        """Condition 5: Post-standing recovery -> Return toward baseline (< 20)."""
        # First trigger mild departure
        self.manager.compute_instability(current_bpm=88.0, current_rmssd=28.0, current_rr_cv=0.09, is_quality_reliable=True)

        # Feed 3 recovery windows approaching baseline
        self.manager.compute_instability(current_bpm=76.0, current_rmssd=34.0, current_rr_cv=0.08, is_quality_reliable=True)
        self.manager.compute_instability(current_bpm=72.0, current_rmssd=38.0, current_rr_cv=0.08, is_quality_reliable=True)
        res_recovered = self.manager.compute_instability(
            current_bpm=70.5, current_rmssd=40.0, current_rr_cv=0.075, is_quality_reliable=True
        )
        self.assertIsNotNone(res_recovered["instability_score"])
        self.assertLessEqual(res_recovered["instability_score"], 20.0)
        self.assertEqual(res_recovered["status_label"], "Stable")

    def test_condition_6_sustained_high_pulse(self):
        """Condition 6: Sustained high pulse simulation -> Sustained departure / review (40–100)."""
        # Feed 4 consecutive windows of high tachycardia (+35 BPM)
        for _ in range(3):
            self.manager.compute_instability(current_bpm=106.0, current_rmssd=16.0, current_rr_cv=0.14, is_quality_reliable=True)

        res_sustained = self.manager.compute_instability(
            current_bpm=108.0, current_rmssd=14.0, current_rr_cv=0.15, is_quality_reliable=True
        )
        self.assertIsNotNone(res_sustained["instability_score"])
        self.assertGreaterEqual(res_sustained["instability_score"], 40.0)
        self.assertTrue(res_sustained["review_recommended"])
        self.assertTrue("Sustained" in res_sustained["status_label"] or "Review" in res_sustained["status_label"])

    def test_condition_7_irregular_pulse_afib(self):
        """Condition 7: Irregular pulse pattern -> Sustained departure / review."""
        # Clean amplitude, high beat-to-beat variability (RR-CV 0.38)
        res_afib = self.manager.compute_instability(
            current_bpm=115.0, current_rmssd=68.0, current_rr_cv=0.38, is_quality_reliable=True
        )
        self.assertIsNotNone(res_afib["instability_score"])
        self.assertGreaterEqual(res_afib["instability_score"], 40.0)
        self.assertTrue(res_afib["review_recommended"])
        self.assertTrue(any("Pulse irregularity" in flag for flag in res_afib["departure_flags"]))


if __name__ == "__main__":
    unittest.main()
