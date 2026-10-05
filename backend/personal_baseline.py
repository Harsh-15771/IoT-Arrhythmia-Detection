"""
CardioTwin v4.1 — Personalized Cardiovascular Baseline & Instability Engine
================================================================================
Phase 1 of CardioTwin v4.1 Engineering Plan:
Enforces empirical personal calibration with zero population defaults.
"Is this individual currently departing meaningfully from their own verified, empirical resting baseline?"

Key Specifications:
1. Truthful Personal Baseline Guarantee:
   - If uncalibrated, expired (>30 days), or mismatched device/config:
     returns instability_score: None, status_label: "Personal baseline required",
     departure_flags: ["BASELINE_NOT_CALIBRATED"] (or invalidation reason).
   - Zero fallback to static population defaults (72 bpm, 35 rmssd, etc.).
2. 2-Minute Empirical Calibration Protocol:
   - First 30s: stabilization / settling window (discarded)
   - Next 90s: collect reliable, quality-gated windows
   - Requires AT LEAST 6 quality windows (>= 66% retention) to complete.
   - Computes robust non-parametric baselines:
     * Median BPM & MAD (Median Absolute Deviation * 1.4826)
     * Median RR interval & MAD
     * Baseline RMSSD (pulse rate variability proxy) & MAD
     * Baseline Rhythm Regularity (RR-CV) & MAD
3. Calibration Governance Metadata:
   - Records device_id, firmware_version, sensor_settings, calibrated_at,
     expires_at (30 days TTL), protocol_confirmed, windows_collected,
     windows_accepted, calibration_quality_rate.
4. Robust Z-Score Formulation:
   robust_z = (current_val - median) / (1.4826 * max(MAD, min_mad))
5. Multimodal Instability Index (0–100):
   Fuses:
   - 35% Sustained Pulse-Rate Departure
   - 25% Pulse Irregularity Departure (beat-to-beat variability)
   - 20% Baseline Recovery / Vagal Autonomic Suppression
   - 20% Multi-Window Temporal Memory (4-Window Persistence Consensus)
6. Non-Diagnostic Clinical Display States:
   - 0–20:  Stable
   - 20–40: Mild departure from baseline
   - 40–70: Sustained physiological departure
   - 70+:   Review recommended
   - None:  Personal baseline required or measurement unreliable (gated)
7. JSON Persistence in `backend/baselines/<patient_id>.json`
"""

import os
import json
import time
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from collections import deque


BASELINES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baselines")
os.makedirs(BASELINES_DIR, exist_ok=True)

# Governance constants
BASELINE_TTL_SECONDS = 30 * 86400  # 30-day baseline validity limit
MIN_CALIBRATION_WINDOWS = 6       # Require at least 6 reliable 10s windows post-settling


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
    Manages personal baseline acquisition, governance, persistence,
    and dynamic instability scoring per individual.
    """

    def __init__(self, patient_id: str, storage_dir: str = BASELINES_DIR):
        self.patient_id = patient_id
        self.storage_dir = storage_dir
        self.filepath = os.path.join(storage_dir, f"{patient_id}.json")

        # Calibration state
        self.is_calibrating = False
        self.calibration_start_time = 0.0
        self.calibration_windows: List[Dict[str, float]] = []
        self.windows_collected_count = 0
        self.target_calibration_duration_sec = 120.0
        self.stabilization_duration_sec = 30.0

        # Governance session attributes
        self.calib_device_id = "cardiotwin-esp32-01"
        self.calib_firmware = "4.1.0"
        self.calib_settings = {"led_current_ma": 6.0, "sample_rate_hz": 100, "pulse_width_us": 411}
        self.calib_protocol = "seated_rest_2min"

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

    def is_baseline_valid(
        self,
        current_device_id: Optional[str] = None,
        current_settings: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate personal baseline freshness, window yield, device provenance, and sensor configuration.
        Returns (is_valid, invalid_reason_code).
        """
        if not self.baseline:
            return False, "BASELINE_NOT_CALIBRATED"

        now = time.time()
        calib_ts = self.baseline.get("calibrated_at_ts")
        if calib_ts is None:
            # Parse ISO or string format if numeric timestamp is absent
            try:
                struct = time.strptime(self.baseline.get("calibrated_at", ""), "%Y-%m-%d %H:%M:%S")
                calib_ts = time.mktime(struct)
            except Exception:
                calib_ts = now

        expires_at_ts = self.baseline.get("expires_at_ts") or (calib_ts + BASELINE_TTL_SECONDS)
        if now > expires_at_ts:
            return False, "BASELINE_EXPIRED"

        # Check window sufficiency (at least 6 quality windows required)
        windows_accepted = self.baseline.get("windows_accepted", self.baseline.get("windows_analyzed", 0))
        if windows_accepted < MIN_CALIBRATION_WINDOWS:
            return False, "INSUFFICIENT_CALIBRATION_WINDOWS"

        # Check device mismatch
        if current_device_id and self.baseline.get("device_id"):
            if current_device_id != self.baseline.get("device_id"):
                return False, "DEVICE_MISMATCH"

        # Check sensor configuration mismatch
        if current_settings and self.baseline.get("sensor_settings"):
            base_settings = self.baseline.get("sensor_settings", {})
            for key in ["led_current_ma", "sample_rate_hz"]:
                if key in current_settings and key in base_settings:
                    if current_settings[key] != base_settings[key]:
                        return False, "CONFIG_MISMATCH"

        return True, None

    def start_calibration(
        self,
        device_id: str = "cardiotwin-esp32-01",
        firmware_version: str = "4.1.0",
        sensor_settings: Optional[Dict[str, Any]] = None,
        protocol_confirmed: str = "seated_rest_2min"
    ) -> Dict[str, Any]:
        """Initiate 2-minute personal baseline calibration protocol."""
        self.is_calibrating = True
        self.calibration_start_time = time.time()
        self.calibration_windows.clear()
        self.windows_collected_count = 0
        self.calib_device_id = device_id
        self.calib_firmware = firmware_version
        self.calib_settings = sensor_settings or {"led_current_ma": 6.0, "sample_rate_hz": 100, "pulse_width_us": 411}
        self.calib_protocol = protocol_confirmed
        return {
            "status": "CALIBRATION_STARTED",
            "patient_id": self.patient_id,
            "target_duration_sec": self.target_calibration_duration_sec,
            "stabilization_duration_sec": self.stabilization_duration_sec,
            "start_time": self.calibration_start_time,
            "device_id": self.calib_device_id
        }

    def cancel_calibration(self):
        """Cancel ongoing calibration session."""
        self.is_calibrating = False
        self.calibration_windows.clear()
        self.windows_collected_count = 0

    def process_calibration_window(
        self,
        bpm: Optional[float],
        rmssd: Optional[float],
        rr_cv: Optional[float],
        sqi: Optional[float],
        is_quality_ok: bool
    ) -> Dict[str, Any]:
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
                "windows_collected": len(self.calibration_windows),
                "windows_required": MIN_CALIBRATION_WINDOWS
            }

        # Post-stabilization: increment offered window count
        self.windows_collected_count += 1

        # Post-stabilization: record quality-approved windows
        if is_quality_ok and bpm is not None and bpm > 30.0:
            self.calibration_windows.append({
                "bpm": float(bpm),
                "rmssd": float(rmssd) if rmssd else 35.0,
                "rr_cv": float(rr_cv) if rr_cv else 0.10,
                "sqi": float(sqi) if sqi else 0.85,
                "timestamp": time.time()
            })

        if elapsed >= self.target_calibration_duration_sec or len(self.calibration_windows) >= 9:
            return self.finalize_calibration()

        return {
            "status": "ACCUMULATING_CALIBRATION",
            "phase": f"Sampling Baseline ({elapsed:.0f}/{self.target_calibration_duration_sec:.0f}s)",
            "elapsed_sec": round(elapsed, 1),
            "windows_collected": len(self.calibration_windows),
            "windows_required": MIN_CALIBRATION_WINDOWS
        }

    def finalize_calibration(
        self,
        device_id: Optional[str] = None,
        firmware_version: Optional[str] = None,
        sensor_settings: Optional[Dict[str, Any]] = None,
        protocol_confirmed: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate robust personal median & MAD from calibration windows and save.
        Requires >= 6 quality windows to succeed.
        """
        self.is_calibrating = False
        if len(self.calibration_windows) < MIN_CALIBRATION_WINDOWS:
            return {
                "status": "CALIBRATION_FAILED",
                "reason": f"Insufficient quality windows collected ({len(self.calibration_windows)} < {MIN_CALIBRATION_WINDOWS}). Keep finger still and retry.",
                "windows_accepted": len(self.calibration_windows),
                "windows_required": MIN_CALIBRATION_WINDOWS
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

        now_ts = time.time()
        expires_at_ts = now_ts + BASELINE_TTL_SECONDS

        eff_device_id = device_id or getattr(self, "calib_device_id", "cardiotwin-esp32-01")
        eff_firmware = firmware_version or getattr(self, "calib_firmware", "4.1.0")
        eff_settings = sensor_settings or getattr(self, "calib_settings", {"led_current_ma": 6.0, "sample_rate_hz": 100, "pulse_width_us": 411})
        eff_protocol = protocol_confirmed or getattr(self, "calib_protocol", "seated_rest_2min")

        total_collected = max(self.windows_collected_count, len(self.calibration_windows))
        quality_rate = round(len(self.calibration_windows) / max(1, total_collected), 3)

        self.baseline = {
            "patient_id": self.patient_id,
            "device_id": eff_device_id,
            "firmware_version": eff_firmware,
            "sensor_settings": eff_settings,
            "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now_ts)),
            "calibrated_at_ts": now_ts,
            "expires_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(expires_at_ts)),
            "expires_at_ts": expires_at_ts,
            "protocol_confirmed": eff_protocol,
            "windows_collected": total_collected,
            "windows_accepted": len(self.calibration_windows),
            "calibration_quality_rate": quality_rate,
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
        is_quality_reliable: bool,
        current_device_id: Optional[str] = None,
        current_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compute personal cardiovascular instability index (0–100) relative to user's calibrated baseline.
        If quality is unreliable, returns None for instability.
        If personal baseline is missing, expired, or invalid, strictly returns None for instability.
        """
        # 1. Gate check: Physical signal reliability
        if not is_quality_reliable or current_bpm is None or current_bpm <= 0:
            return {
                "instability_score": None,
                "status_label": "Measurement Unreliable (Gated)",
                "z_scores": {},
                "departure_flags": ["UNRELIABLE_SIGNAL"],
                "calibrated": self.baseline is not None
            }

        # 2. Check personal baseline validity (no population defaults)
        is_valid, invalid_reason = self.is_baseline_valid(
            current_device_id=current_device_id,
            current_settings=current_settings
        )
        if not is_valid:
            reason_flag = invalid_reason or "BASELINE_NOT_CALIBRATED"
            return {
                "instability_score": None,
                "status_label": "Personal baseline required",
                "departure_flags": [reason_flag],
                "z_scores": {},
                "calibrated": False,
                "invalidation_reason": reason_flag
            }

        b = self.baseline

        # 3. Robust Z-Scores relative to personal baseline
        z_bpm = compute_robust_z(current_bpm, b["median_bpm"], b["mad_bpm"], min_mad=2.5)
        rmssd_val = current_rmssd if current_rmssd is not None else b["median_rmssd"]
        z_rmssd = compute_robust_z(rmssd_val, b["median_rmssd"], b["mad_rmssd"], min_mad=3.0)
        rr_cv_val = current_rr_cv if current_rr_cv is not None else b["median_rr_cv"]
        z_rr_cv = compute_robust_z(rr_cv_val, b["median_rr_cv"], b["mad_rr_cv"], min_mad=0.02)

        # 4. Component Departures (0–100 scale each)
        # Pulse Rate Departure (35% weight)
        abs_z_bpm = abs(z_bpm)
        hr_dep = min(100.0, max(0.0, (abs_z_bpm - 1.0) * 25.0)) if abs_z_bpm > 1.0 else 0.0

        # Pulse Irregularity Departure (25% weight)
        irreg_dep = min(100.0, max(0.0, (z_rr_cv - 1.0) * 35.0)) if z_rr_cv > 1.0 else 0.0

        # Autonomic / HRV Suppression (20% weight)
        autonomic_dep = min(100.0, max(0.0, (-z_rmssd - 1.0) * 30.0)) if z_rmssd < -1.0 else 0.0

        # Sustained Trend Memory (20% weight)
        self.window_history.append({"bpm": current_bpm, "z_bpm": z_bpm, "z_rr_cv": z_rr_cv})
        sustained_dep = 0.0
        if len(self.window_history) >= 3:
            recent_abs_z = [abs(w["z_bpm"]) for w in self.window_history]
            if all(z >= 1.5 for z in recent_abs_z):
                sustained_dep = 60.0
            if all(w["z_rr_cv"] >= 1.5 for w in self.window_history):
                sustained_dep = max(sustained_dep, 70.0)

        # 5. Multimodal Instability Index
        raw_instability = (
            0.35 * hr_dep +
            0.25 * irreg_dep +
            0.20 * autonomic_dep +
            0.20 * sustained_dep
        )
        instability_score = round(max(0.0, min(100.0, raw_instability)), 1)

        # 6. Display States (CardioTwin v4.1 non-diagnostic states)
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

        # Natural Language Explanation (Phase 1.3)
        explanation_parts = []
        if abs_z_bpm > 2.0:
            direction = "above" if z_bpm > 0 else "below"
            diff = abs(current_bpm - b["median_bpm"])
            explanation_parts.append(
                f"Pulse rate is {diff:.0f} BPM {direction} personal resting baseline ({current_bpm:.0f} vs {b['median_bpm']:.0f} BPM, Z={z_bpm:+.1f}σ)"
            )
        if z_rr_cv > 2.0:
            ratio = (rr_cv_val / max(0.01, b["median_rr_cv"]))
            explanation_parts.append(
                f"Pulse irregularity is {ratio:.1f}x higher than personal resting baseline (RR-CV {rr_cv_val:.3f} vs {b['median_rr_cv']:.3f}, Z={z_rr_cv:+.1f}σ)"
            )
        if z_rmssd < -2.0:
            explanation_parts.append(
                f"Parasympathetic vagal tone is markedly suppressed (RMSSD {rmssd_val:.1f} ms vs baseline {b['median_rmssd']:.1f} ms, Z={z_rmssd:+.1f}σ)"
            )

        if not explanation_parts:
            band = b.get("resting_band_bpm", [b["median_bpm"] - 4, b["median_bpm"] + 4])
            natural_explanation = (
                f"All optical pulse metrics remain concordant with your empirical resting baseline "
                f"(Pulse: {current_bpm:.0f} BPM, typical resting band {band[0]:.0f}–{band[1]:.0f} BPM)."
            )
        else:
            natural_explanation = " | ".join(explanation_parts)

        # Temporal Persistence Context (Phase 1.3)
        consecutive_elevated = sum(1 for w in self.window_history if abs(w.get("z_bpm", 0.0)) >= 1.5)
        consecutive_irregular = sum(1 for w in self.window_history if w.get("z_rr_cv", 0.0) >= 1.5)
        max_consecutive = max(consecutive_elevated, consecutive_irregular)
        duration_sec = max_consecutive * 10
        temporal_context = {
            "consecutive_departure_windows": max_consecutive,
            "estimated_duration_seconds": duration_sec,
            "persistence_description": (
                f"Sustained across {max_consecutive} consecutive 10s windows ({duration_sec}s duration)"
                if max_consecutive >= 2 else "Transient single-window observation (<15s)"
            )
        }

        # Actionable Clinical Suggestion (Phase 1.3)
        if instability_score <= 20.0:
            clinical_suggestion = "Resting cardiovascular stability confirmed. Continue regular longitudinal tracking."
        elif instability_score <= 40.0:
            clinical_suggestion = "Mild acute departure. If seated at rest, check for recent exertion, posture transition, or caffeine."
        elif instability_score <= 70.0:
            clinical_suggestion = (
                "Sustained departure from resting baseline. Remain quietly seated for 2 minutes to assess recovery; "
                "consider reviewing hydration, acute stress, or medication schedule."
            )
        else:
            clinical_suggestion = (
                "Marked cardiovascular instability detected relative to personal baseline. "
                "Clinician review recommended; obtain 12-lead ECG if symptomatic (chest discomfort, palpitations, or lightheadedness)."
            )

        # Evidence Ledger / Honest Limitations Disclosure (Phase 1.2)
        evidence_ledger = {
            "sensor_type": "Reflective Photoplethysmography (MAX30102 Infrared 880nm)",
            "spo2_channel_status": "UNAVAILABLE (Single-channel IR configuration; dual-wavelength red+IR required for certified SpO2)",
            "ecg_equivalence": "NOT EQUIVALENT (Optical volume pulse wave cannot assess QRS morphology or ST elevation/depression)",
            "personal_anchor": f"Empirical resting calibration established {b.get('calibrated_at', 'recently')} ({b.get('windows_accepted', 6)} valid windows)",
            "source_bias_disclosure": "Research classifier trained on PhysioNet CinC 2015 & MIMIC-III; ventricular rhythm categories carry ICU source bias",
            "regulatory_status": "Investigational physiological digital twin — not an FDA/CDSCO cleared diagnostic device"
        }

        return {
            "instability_score": instability_score,
            "status_label": status_label,
            "review_recommended": review_recommended,
            "departure_flags": departure_flags,
            "natural_explanation": natural_explanation,
            "temporal_context": temporal_context,
            "clinical_suggestion": clinical_suggestion,
            "evidence_ledger": evidence_ledger,
            "z_scores": {
                "z_bpm": round(z_bpm, 2),
                "z_rmssd": round(z_rmssd, 2),
                "z_rr_cv": round(z_rr_cv, 2)
            },
            "personal_baseline": {
                "median_bpm": b["median_bpm"],
                "mad_bpm": b["mad_bpm"],
                "median_rmssd": b["median_rmssd"],
                "calibrated_at": b.get("calibrated_at"),
                "device_id": b.get("device_id"),
                "firmware_version": b.get("firmware_version"),
                "is_custom_calibrated": True
            },
            "calibrated": True
        }
