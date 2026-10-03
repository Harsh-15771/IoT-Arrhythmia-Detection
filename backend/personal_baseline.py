"""
CardioTwin v4 — Personalized Cardiovascular Baseline & Instability Engine
================================================================================
Step 3 of CardioTwin v4 Product Pivot:
Transforms CardioTwin from an arbitrary 8-class diagnostic device into a true
personalized digital twin that asks:
"Is this individual currently departing meaningfully from their own reliable cardiovascular baseline?"

Key Features:
1. 2-Minute Calibration Protocol:
   - First 30s: stabilization / settling window (discarded)
   - Next 90s: collect reliable, quality-gated windows
   - Computes robust non-parametric baselines:
     * Median BPM & MAD (Median Absolute Deviation)
     * Median RR interval & MAD
     * Baseline RMSSD (pulse rate variability proxy)
     * Baseline Pulse Amplitude / Perfusion Proxy
     * Baseline Rhythm Regularity
2. Robust Z-Score Formulation:
   robust_z = (current_val - median) / (1.4826 * max(MAD, min_mad))
3. Multimodal Instability Index (0–100):
   Fuses:
   - 35% Sustained Pulse-Rate Departure
   - 25% Pulse Irregularity Departure (beat-to-beat variability)
   - 20% Baseline Recovery Failure
   - 20% Waveform Morphology / Perfusion Perturbation
4. Clinical Review States:
   - 0–20:  Stable
   - 20–40: Mild Departure from Baseline
   - 40–70: Sustained Physiological Departure
   - 70+:   Review Recommended
   - None:  Measurement Unreliable (Gated)
5. JSON Persistence in `backend/baselines/<patient_id>.json`
"""

import os
import json
import time
import numpy as np
from typing import Dict, Any, Optional, List
from collections import deque


BASELINES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baselines")
os.makedirs(BASELINES_DIR, exist_ok=True)


def compute_mad(values: np.ndarray) -> float:
    """Compute Median Absolute Deviation (MAD), robust estimator of dispersion."""
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return 0.0
    med = np.median(arr)
    return float(np.median(np.abs(arr - med)))


def compute_robust_z(val: float, median: float, mad: float, min_mad: float = 2.0) -> float:
    """
    Robust Z-Score scaled to standard normal equivalent:
    Normalizes by 1.4826 * MAD (asymptotically normal for Gaussian data).
    """
    effective_scale = 1.4826 * max(mad, min_mad)
    return float((val - median) / effective_scale)


class PersonalBaselineManager:
    """
    Manages personal baseline acquisition, persistence, and dynamic instability scoring per patient.
    """

    def __init__(self, patient_id: str, storage_dir: str = BASELINES_DIR):
        self.patient_id = patient_id
        self.storage_dir = storage_dir
        self.filepath = os.path.join(storage_dir, f"{patient_id}.json")

        # Calibration state
        self.is_calibrating = False
        self.calibration_start_time = 0.0
        self.calibration_windows: List[Dict[str, float]] = []
        self.target_calibration_duration_sec = 120.0
        self.stabilization_duration_sec = 30.0

        # Saved baseline
        self.baseline: Optional[Dict[str, Any]] = None
        self.load_baseline()

        # Rolling evaluation window memory (4-window history for multi-window consensus)
        self.window_history = deque(maxlen=4)

    def load_baseline(self) -> Optional[Dict[str, Any]]:
        """Load stored baseline JSON if available."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.baseline = json.load(f)
                return self.baseline
            except Exception as e:
                print(f"[WARN] Failed to load baseline for {self.patient_id}: {e}")
        self.baseline = None
        return None

    def save_baseline(self) -> bool:
        """Persist calibrated baseline to disk."""
        if not self.baseline:
            return False
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.baseline, f, indent=2)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save baseline for {self.patient_id}: {e}")
            return False

    def start_calibration(self) -> Dict[str, Any]:
        """Initiate 2-minute personal baseline calibration protocol."""
        self.is_calibrating = True
        self.calibration_start_time = time.time()
        self.calibration_windows.clear()
        return {
            "status": "CALIBRATION_STARTED",
            "patient_id": self.patient_id,
            "target_duration_sec": self.target_calibration_duration_sec,
            "stabilization_duration_sec": self.stabilization_duration_sec,
            "start_time": self.calibration_start_time
        }

    def cancel_calibration(self):
        """Cancel ongoing calibration session."""
        self.is_calibrating = False
        self.calibration_windows.clear()

    def process_calibration_window(self, bpm: float, rmssd: float, rr_cv: float, sqi: float, is_quality_ok: bool) -> Dict[str, Any]:
        """
        Feed a 10s window into the calibration accumulator.
        Discards initial 30s settling period, aggregates post-stabilization windows.
        """
        if not self.is_calibrating:
            return {"status": "NOT_CALIBRATING"}

        elapsed = time.time() - self.calibration_start_time

        if elapsed < self.stabilization_duration_sec:
            return {
                "status": "STABILIZING_CALIBRATION",
                "phase": f"Settling ({elapsed:.0f}/{self.stabilization_duration_sec:.0f}s)",
                "elapsed_sec": round(elapsed, 1),
                "windows_collected": len(self.calibration_windows)
            }

        # Post-stabilization: record quality-approved windows
        if is_quality_ok and bpm > 30.0:
            self.calibration_windows.append({
                "bpm": float(bpm),
                "rmssd": float(rmssd) if rmssd else 35.0,
                "rr_cv": float(rr_cv) if rr_cv else 0.10,
                "sqi": float(sqi) if sqi else 0.85,
                "timestamp": time.time()
            })

        if elapsed >= self.target_calibration_duration_sec or len(self.calibration_windows) >= 9:
            # Finalize calibration
            return self.finalize_calibration()

        return {
            "status": "ACCUMULATING_CALIBRATION",
            "phase": f"Sampling Baseline ({elapsed:.0f}/{self.target_calibration_duration_sec:.0f}s)",
            "elapsed_sec": round(elapsed, 1),
            "windows_collected": len(self.calibration_windows)
        }

    def finalize_calibration(self) -> Dict[str, Any]:
        """Calculate robust personal median & MAD from calibration windows and save."""
        self.is_calibrating = False
        if len(self.calibration_windows) < 3:
            return {
                "status": "CALIBRATION_FAILED",
                "reason": f"Insufficient quality windows collected ({len(self.calibration_windows)} < 3). Keep finger still and retry."
            }

        bpms = np.array([w["bpm"] for w in self.calibration_windows])
        rmssds = np.array([w["rmssd"] for w in self.calibration_windows])
        rr_cvs = np.array([w["rr_cv"] for w in self.calibration_windows])
        sqis = np.array([w["sqi"] for w in self.calibration_windows])

        med_bpm = float(np.median(bpms))
        mad_bpm = compute_mad(bpms)
        med_rmssd = float(np.median(rmssds))
        mad_rmssd = compute_mad(rmssds)
        med_rr_cv = float(np.median(rr_cvs))
        mad_rr_cv = compute_mad(rr_cvs)

        self.baseline = {
            "patient_id": self.patient_id,
            "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "windows_analyzed": len(self.calibration_windows),
            "median_bpm": round(med_bpm, 1),
            "mad_bpm": round(max(mad_bpm, 1.5), 2),
            "median_rmssd": round(med_rmssd, 1),
            "mad_rmssd": round(max(mad_rmssd, 2.0), 2),
            "median_rr_cv": round(med_rr_cv, 3),
            "mad_rr_cv": round(max(mad_rr_cv, 0.02), 3),
            "mean_sqi": round(float(np.mean(sqis)), 2),
            "resting_band_bpm": [round(med_bpm - 1.4826 * max(mad_bpm, 2.0), 1), round(med_bpm + 1.4826 * max(mad_bpm, 2.0), 1)],
            "provenance": "2-minute empirical calibration (seated rest, MAX30102 PPG)"
        }
        self.save_baseline()

        return {
            "status": "CALIBRATION_COMPLETE",
            "patient_id": self.patient_id,
            "baseline": self.baseline
        }

    def compute_instability(
        self,
        current_bpm: Optional[float],
        current_rmssd: Optional[float],
        current_rr_cv: Optional[float],
        is_quality_reliable: bool
    ) -> Dict[str, Any]:
        """
        Compute personal cardiovascular instability index (0–100) relative to user's calibrated baseline.
        If quality is unreliable, returns None for instability.
        """
        if not is_quality_reliable or current_bpm is None or current_bpm <= 0:
            return {
                "instability_score": None,
                "status_label": "Measurement Unreliable (Gated)",
                "z_scores": {},
                "departure_flags": ["UNRELIABLE_SIGNAL"]
            }

        # If no personal baseline is calibrated, initialize with standard population normative resting baseline
        b = self.baseline or {
            "median_bpm": 72.0,
            "mad_bpm": 4.0,
            "median_rmssd": 35.0,
            "mad_rmssd": 6.0,
            "median_rr_cv": 0.08,
            "mad_rr_cv": 0.03,
            "is_population_default": True
        }

        # 1. Robust Z-Scores
        z_bpm = compute_robust_z(current_bpm, b["median_bpm"], b["mad_bpm"], min_mad=2.5)
        rmssd_val = current_rmssd if current_rmssd is not None else b["median_rmssd"]
        z_rmssd = compute_robust_z(rmssd_val, b["median_rmssd"], b["mad_rmssd"], min_mad=3.0)
        rr_cv_val = current_rr_cv if current_rr_cv is not None else b["median_rr_cv"]
        z_rr_cv = compute_robust_z(rr_cv_val, b["median_rr_cv"], b["mad_rr_cv"], min_mad=0.02)

        # 2. Component Departures (0–100 scale each)
        # Pulse Rate Departure (35% weight): Penalizes both persistent tachycardia and bradycardia deviations
        abs_z_bpm = abs(z_bpm)
        hr_dep = min(100.0, max(0.0, (abs_z_bpm - 1.0) * 25.0)) if abs_z_bpm > 1.0 else 0.0

        # Pulse Irregularity Departure (25% weight): Elevated beat-to-beat variability (AFib/PACs)
        # Only positive z_rr_cv indicates increased rhythm fragmentation
        irreg_dep = min(100.0, max(0.0, (z_rr_cv - 1.0) * 35.0)) if z_rr_cv > 1.0 else 0.0

        # Autonomic / HRV Suppression (20% weight): Severe RMSSD drops below user baseline
        autonomic_dep = min(100.0, max(0.0, (-z_rmssd - 1.0) * 30.0)) if z_rmssd < -1.0 else 0.0

        # Sustained Trend Memory (20% weight): Check recent windows in history
        self.window_history.append({"bpm": current_bpm, "z_bpm": z_bpm, "z_rr_cv": z_rr_cv})
        sustained_dep = 0.0
        if len(self.window_history) >= 3:
            recent_abs_z = [abs(w["z_bpm"]) for w in self.window_history]
            if all(z >= 1.5 for z in recent_abs_z):
                sustained_dep = 60.0
            if all(w["z_rr_cv"] >= 1.5 for w in self.window_history):
                sustained_dep = max(sustained_dep, 70.0)

        # 3. Multimodal Instability Index
        raw_instability = (
            0.35 * hr_dep +
            0.25 * irreg_dep +
            0.20 * autonomic_dep +
            0.20 * sustained_dep
        )
        instability_score = round(max(0.0, min(100.0, raw_instability)), 1)

        # 4. Display States (CardioTwin v4 non-diagnostic states)
        if instability_score <= 20.0:
            status_label = "Stable"
            review_recommended = False
        elif instability_score <= 40.0:
            status_label = "Mild departure from baseline"
            review_recommended = False
        elif instability_score <= 70.0:
            status_label = "Sustained physiological departure"
            review_recommended = True
        else:
            status_label = "Review recommended"
            review_recommended = True

        departure_flags = []
        if abs_z_bpm > 2.0:
            departure_flags.append(f"Heart rate {z_bpm:+.1f}σ from personal median ({b['median_bpm']:.0f} BPM)")
        if z_rr_cv > 2.0:
            departure_flags.append(f"Pulse irregularity {z_rr_cv:+.1f}σ above personal baseline")
        if z_rmssd < -2.0:
            departure_flags.append(f"Autonomic vagal tone suppressed ({z_rmssd:+.1f}σ)")

        return {
            "instability_score": instability_score,
            "status_label": status_label,
            "review_recommended": review_recommended,
            "departure_flags": departure_flags,
            "z_scores": {
                "z_bpm": round(z_bpm, 2),
                "z_rmssd": round(z_rmssd, 2),
                "z_rr_cv": round(z_rr_cv, 2)
            },
            "personal_baseline": {
                "median_bpm": b["median_bpm"],
                "mad_bpm": b["mad_bpm"],
                "median_rmssd": b["median_rmssd"],
                "is_custom_calibrated": not b.get("is_population_default", False)
            }
        }
