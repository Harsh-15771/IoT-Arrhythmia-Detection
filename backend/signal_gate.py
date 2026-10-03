"""
CardioTwin - Separated Signal Quality Gate & Physiological Observation Engine
================================================================================
Architecture (Step 2 of CardioTwin v4 Product Pivot):
Separates signal reliability assessment into two independent axes:
  1. Signal Quality Gate (May block AI):
     - Sensor contact & optical amplitude (flatline, finger liftoff)
     - ADC clipping & saturation (transimpedance amp ceiling)
     - Sample timing jitter & dropped hardware packets
     - Pulse morphology (minimum 3 detectable systolic peaks)
     -> Strictly blocks AI when hardware or optical contact fails.
  2. Physiological Observation (NEVER blocks AI screening):
     - Beat-to-beat pulse irregularity (RR CV > 0.35 -> IRREGULAR_PULSE_OBSERVATION)
     - Pulse rate extremes (BPM < 40 or > 180 -> RECHECK_REQUIRED tag)
     -> Surfaces observed physiological patterns to screening models rather
        than discarding genuine arrhythmias (AFib, severe bradycardia) as noise!

Authoritative 5 metrics:
  - sample_rate_estimate = 1 / median(timestamp_difference)
  - bpm = 60 / median(valid_peak_intervals)
  - peak_coverage = valid_peak_intervals_total_time / window_duration
  - rr_cv = std(rr) / mean(rr)
  - clipping_ratio = count(raw_value >= max_limit or raw_value <= min_limit) / window_samples
"""

import numpy as np
from scipy.signal import find_peaks, butter, filtfilt
from scipy.stats import kurtosis


def bandpass_filter(signal: np.ndarray, lowcut: float = 0.5, highcut: float = 8.0, fs: float = 100.0, order: int = 4) -> np.ndarray:
    """4th-order Butterworth bandpass filter isolating arterial pulse bandwidth (0.5 - 8.0 Hz)."""
    nyq = 0.5 * fs
    low = max(0.001, lowcut / nyq)
    high = min(0.999, highcut / nyq)
    if low >= high or len(signal) < 15:
        return signal
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)


class SignalReliabilityGate:
    """
    Evaluates 10-second PPG telemetry windows across decoupled Signal Quality and Physiological Observation axes.
    """

    def __init__(
        self,
        target_fs: float = 100.0,
        window_sec: float = 10.0,
        stability_threshold: int = 3,
        min_bpm: float = 40.0,
        max_bpm: float = 180.0,
        adc_min_limit: float = 200.0,       # Optical baseline floor for finger contact
        adc_max_limit: float = 260000.0,   # 18-bit ADC saturation limit
        max_clipping_ratio: float = 0.05,  # Max 5% clipped samples
        max_rr_cv: float = 0.35,           # Irregularity threshold
        min_peak_coverage: float = 0.65,   # Minimum 65% window coverage
    ):
        self.target_fs = target_fs
        self.window_sec = window_sec
        self.window_samples = int(target_fs * window_sec)
        self.stability_threshold = stability_threshold
        self.min_bpm = min_bpm
        self.max_bpm = max_bpm
        self.adc_min_limit = adc_min_limit
        self.adc_max_limit = adc_max_limit
        self.max_clipping_ratio = max_clipping_ratio
        self.max_rr_cv = max_rr_cv
        self.min_peak_coverage = min_peak_coverage

        # State tracking across windows
        self.consecutive_good_windows = 0
        self.total_windows_evaluated = 0
        self.history = []

    def reset(self):
        """Reset window stability counter (e.g., when a new patient or session starts)."""
        self.consecutive_good_windows = 0
        self.total_windows_evaluated = 0
        self.history.clear()

    def evaluate_window(
        self,
        raw_samples: np.ndarray,
        timestamps_ms: np.ndarray = None
    ) -> dict:
        """
        Evaluate a single window of PPG telemetry.
        Returns:
          - signal_quality: dict with contact_ok, timing_ok, saturation_ok, pulse_morphology_ok, screening_allowed
          - physiological_observation: dict with pulse_rate, rate_state, rr_cv, irregularity_state, recheck_recommended
          - 5 core metrics: sample_rate_estimate, bpm, peak_coverage, rr_cv, clipping_ratio
          - status: FINGER_OFF, SENSOR_SATURATED, POOR_TIMING, POOR_CONTACT, STABILIZING, RECHECK_REQUIRED, IRREGULAR_RHYTHM, RELIABLE
          - ai_screening_enabled: bool (True when quality is valid and stability threshold reached)
        """
        self.total_windows_evaluated += 1
        raw_arr = np.asarray(raw_samples, dtype=float)
        n_samples = len(raw_arr)
        if timestamps_ms is not None and len(timestamps_ms) == n_samples and n_samples > 1:
            window_duration = max(0.1, (float(timestamps_ms[-1]) - float(timestamps_ms[0])) / 1000.0)
        else:
            window_duration = n_samples / self.target_fs if n_samples > 0 else self.window_sec

        # Default fallback metric values
        sample_rate_estimate = float(self.target_fs)
        clipping_ratio = 0.0

        checks = {
            "contact_amplitude": False,
            "sample_timing": False,
            "peak_regularity": False,
            "physiological_plausibility": False,
            "window_stability": False,
        }

        # -------------------------------------------------------------
        # QUALITY GATE 1: WINDOW LENGTH / BUFFERING
        # -------------------------------------------------------------
        if n_samples < int(self.target_fs * 3):
            return self._build_result(
                status="BUFFERING",
                reason=f"Insufficient window length ({n_samples} samples < {int(self.target_fs * 3)})",
                checks=checks,
                metrics={
                    "sample_rate_estimate": sample_rate_estimate,
                    "bpm": 0.0,
                    "peak_coverage": 0.0,
                    "rr_cv": 1.0,
                    "clipping_ratio": 0.0,
                    "sqi": 0.0,
                },
                is_pass=False,
                signal_quality={
                    "contact_ok": False,
                    "timing_ok": False,
                    "saturation_ok": True,
                    "pulse_morphology_ok": False,
                    "screening_allowed": False
                }
            )

        raw_std = float(np.std(raw_arr))
        raw_ptp = float(np.ptp(raw_arr))
        raw_median = float(np.median(raw_arr))

        # -------------------------------------------------------------
        # QUALITY GATE 2: SENSOR SATURATION / CLIPPING
        # -------------------------------------------------------------
        clipping_count = np.sum(raw_arr >= self.adc_max_limit)
        clipping_ratio = float(clipping_count / n_samples)
        if clipping_ratio > self.max_clipping_ratio or raw_median >= self.adc_max_limit:
            self.consecutive_good_windows = 0
            return self._build_result(
                status="SENSOR_SATURATED",
                reason=f"Optical ADC saturation / clipping ({clipping_ratio*100:.1f}% samples clipped)",
                checks=checks,
                metrics={
                    "sample_rate_estimate": sample_rate_estimate,
                    "bpm": 0.0,
                    "peak_coverage": 0.0,
                    "rr_cv": 1.0,
                    "clipping_ratio": max(clipping_ratio, 1.0 if raw_median >= self.adc_max_limit else 0.0),
                    "sqi": 0.0,
                },
                is_pass=False,
                signal_quality={
                    "contact_ok": True,
                    "timing_ok": False,
                    "saturation_ok": False,
                    "pulse_morphology_ok": False,
                    "screening_allowed": False
                }
            )

        # -------------------------------------------------------------
        # QUALITY GATE 3: SENSOR LIFTOFF / FLATLINE / FINGER-OFF
        # -------------------------------------------------------------
        if raw_std < 0.05 or raw_ptp < 1.0 or raw_median < self.adc_min_limit:
            self.consecutive_good_windows = 0
            return self._build_result(
                status="FINGER_OFF",
                reason="Sensor liftoff or flatline detected (amplitude below optical contact threshold)",
                checks=checks,
                metrics={
                    "sample_rate_estimate": sample_rate_estimate,
                    "bpm": 0.0,
                    "peak_coverage": 0.0,
                    "rr_cv": 1.0,
                    "clipping_ratio": clipping_ratio,
                    "sqi": 0.0,
                },
                is_pass=False,
                signal_quality={
                    "contact_ok": False,
                    "timing_ok": False,
                    "saturation_ok": True,
                    "pulse_morphology_ok": False,
                    "screening_allowed": False
                }
            )

        checks["contact_amplitude"] = True

        # -------------------------------------------------------------
        # QUALITY GATE 4: HARDWARE SAMPLE-TIMING & PACKET INTEGRITY
        # -------------------------------------------------------------
        if timestamps_ms is not None and len(timestamps_ms) == n_samples and n_samples > 1:
            ts_diffs = np.diff(np.asarray(timestamps_ms, dtype=float))
            valid_diffs = ts_diffs[ts_diffs > 0]
            if len(valid_diffs) > 0:
                median_dt_ms = float(np.median(valid_diffs))
                if median_dt_ms > 0:
                    sample_rate_estimate = float(1000.0 / median_dt_ms)
                
                expected_dt = 1000.0 / self.target_fs
                dropped_samples = int(np.sum(valid_diffs > 2.5 * expected_dt))

                if abs(sample_rate_estimate - self.target_fs) > 15.0 or dropped_samples > (0.05 * n_samples):
                    self.consecutive_good_windows = 0
                    return self._build_result(
                        status="POOR_TIMING",
                        reason=f"Sampling jitter or packet drop (fs={sample_rate_estimate:.1f}Hz, drops={dropped_samples})",
                        checks=checks,
                        metrics={
                            "sample_rate_estimate": round(sample_rate_estimate, 1),
                            "bpm": 0.0,
                            "peak_coverage": 0.0,
                            "rr_cv": 1.0,
                            "clipping_ratio": round(clipping_ratio, 3),
                            "sqi": 0.2,
                        },
                        is_pass=False,
                        signal_quality={
                            "contact_ok": True,
                            "timing_ok": False,
                            "saturation_ok": True,
                            "pulse_morphology_ok": False,
                            "screening_allowed": False
                        }
                    )

        checks["sample_timing"] = True

        # -------------------------------------------------------------
        # QUALITY GATE 5: PULSE MORPHOLOGY (PEAK DETECTION)
        # -------------------------------------------------------------
        try:
            filtered = bandpass_filter(raw_arr, lowcut=0.5, highcut=8.0, fs=sample_rate_estimate, order=4)
        except Exception:
            filtered = raw_arr

        filt_std = float(np.std(filtered))
        filt_mean = float(np.mean(filtered))
        if filt_std > 1e-4:
            norm_sig = (filtered - filt_mean) / filt_std
        else:
            norm_sig = np.zeros_like(filtered)

        min_peak_dist = max(12, int(sample_rate_estimate * (60.0 / 240.0) * 0.75))
        peaks, _ = find_peaks(norm_sig, distance=min_peak_dist, prominence=0.30)

        if len(peaks) < 3:
            self.consecutive_good_windows = 0
            return self._build_result(
                status="POOR_CONTACT",
                reason=f"Insufficient pulse peaks ({len(peaks)} peaks in {window_duration:.1f}s)",
                checks=checks,
                metrics={
                    "sample_rate_estimate": round(sample_rate_estimate, 1),
                    "bpm": 0.0,
                    "peak_coverage": 0.0,
                    "rr_cv": 1.0,
                    "clipping_ratio": round(clipping_ratio, 3),
                    "sqi": 0.15,
                },
                is_pass=False,
                signal_quality={
                    "contact_ok": True,
                    "timing_ok": True,
                    "saturation_ok": True,
                    "pulse_morphology_ok": False,
                    "screening_allowed": False
                }
            )

        # =============================================================
        # ALL HARDWARE SIGNAL QUALITY CHECKS PASSED!
        # =============================================================
        signal_quality = {
            "contact_ok": True,
            "timing_ok": True,
            "saturation_ok": True,
            "pulse_morphology_ok": True,
            "screening_allowed": True
        }

        # -------------------------------------------------------------
        # AXIS 2: PHYSIOLOGICAL OBSERVATION (DOES NOT BLOCK SCREENING)
        # -------------------------------------------------------------
        if timestamps_ms is not None and len(timestamps_ms) == n_samples and n_samples > 1:
            peak_times_sec = np.asarray(timestamps_ms[peaks], dtype=float) / 1000.0
            rr_sec = np.diff(peak_times_sec)
        else:
            rr_sec = np.diff(peaks) / sample_rate_estimate
        median_rr = float(np.median(rr_sec)) if len(rr_sec) > 0 else 0.0
        raw_bpm = float(60.0 / median_rr) if median_rr > 0 else 0.0
        raw_rr_cv = float(np.std(rr_sec) / (np.mean(rr_sec) + 1e-6)) if len(rr_sec) > 0 else 1.0
        peak_coverage = float(min(1.0, np.sum(rr_sec) / window_duration))

        sig_kurt = float(kurtosis(norm_sig))
        peak_amps = norm_sig[peaks]
        peak_amp_cv = float(np.std(peak_amps) / (abs(np.mean(peak_amps)) + 1e-6))
        sqi = float(max(0.0, min(1.0, (abs(sig_kurt) / 6.0) * (1.0 / (peak_amp_cv + 0.5)))))

        # Rate state classification
        if raw_bpm < self.min_bpm:
            rate_state = "EXTREME_LOW"
            recheck_rate = True
        elif raw_bpm < 50.0:
            rate_state = "LOW"
            recheck_rate = False
        elif raw_bpm <= 100.0:
            rate_state = "TYPICAL"
            recheck_rate = False
        elif raw_bpm <= 120.0:
            rate_state = "ELEVATED"
            recheck_rate = False
        elif raw_bpm <= self.max_bpm:
            rate_state = "SUSTAINED_ELEVATED"
            recheck_rate = False
        else:
            rate_state = "EXTREME_HIGH"
            recheck_rate = True

        # Irregularity state: High RR CV (e.g. AFib) is an observation, NOT blocked noise!
        is_irregular = (raw_rr_cv > self.max_rr_cv)
        irregularity_state = "IRREGULAR_PULSE_OBSERVATION" if is_irregular else "REGULAR_PULSE"
        recheck_recommended = bool(recheck_rate or is_irregular)

        physiological_observation = {
            "pulse_rate": round(raw_bpm, 1),
            "rate_state": rate_state,
            "rr_cv": round(raw_rr_cv, 3),
            "irregularity_state": irregularity_state,
            "recheck_recommended": recheck_recommended
        }

        # Checks dict reflect physiological status
        checks["peak_regularity"] = not is_irregular
        checks["physiological_plausibility"] = not recheck_rate

        metrics = {
            "sample_rate_estimate": round(sample_rate_estimate, 1),
            "bpm": round(raw_bpm, 1),
            "peak_coverage": round(peak_coverage, 3),
            "rr_cv": round(raw_rr_cv, 3),
            "clipping_ratio": round(clipping_ratio, 3),
            "sqi": round(sqi, 3),
        }

        # -------------------------------------------------------------
        # WINDOW STABILITY ACCUMULATION (ON QUALITY-VALID WINDOWS)
        # -------------------------------------------------------------
        self.consecutive_good_windows += 1

        if self.consecutive_good_windows < self.stability_threshold:
            checks["window_stability"] = False
            return self._build_result(
                status="STABILIZING",
                reason=f"Acquiring stable baseline (Window {self.consecutive_good_windows}/{self.stability_threshold})",
                checks=checks,
                metrics=metrics,
                is_pass=False,
                consecutive=self.consecutive_good_windows,
                signal_quality=signal_quality,
                physiological_observation=physiological_observation
            )

        checks["window_stability"] = True

        # Determine finalized status for quality-approved window
        if recheck_rate:
            status = "RECHECK_REQUIRED"
            reason = f"Pulse rate ({raw_bpm:.1f} BPM) outside resting range [{self.min_bpm:.0f}, {self.max_bpm:.0f}]. Screening active with recheck tag."
        elif is_irregular:
            status = "IRREGULAR_RHYTHM"
            reason = f"Irregular beat-to-beat pulse interval observed (RR CV: {raw_rr_cv:.2f} > {self.max_rr_cv:.2f}). Optical screening active."
        else:
            status = "RELIABLE"
            reason = f"Signal validated across {self.consecutive_good_windows} consecutive windows"

        return self._build_result(
            status=status,
            reason=reason,
            checks=checks,
            metrics=metrics,
            is_pass=True,
            consecutive=self.consecutive_good_windows,
            signal_quality=signal_quality,
            physiological_observation=physiological_observation
        )

    def _build_result(
        self,
        status: str,
        reason: str,
        checks: dict,
        metrics: dict,
        is_pass: bool,
        consecutive: int = None,
        signal_quality: dict = None,
        physiological_observation: dict = None
    ) -> dict:
        consec = consecutive if consecutive is not None else self.consecutive_good_windows
        sq = signal_quality if signal_quality is not None else {
            "contact_ok": checks.get("contact_amplitude", False),
            "timing_ok": checks.get("sample_timing", False),
            "saturation_ok": not (status == "SENSOR_SATURATED"),
            "pulse_morphology_ok": not (status in ("POOR_CONTACT", "FINGER_OFF", "BUFFERING")),
            "screening_allowed": is_pass or (status in ("STABILIZING", "RECHECK_REQUIRED", "IRREGULAR_RHYTHM", "RELIABLE"))
        }
        po = physiological_observation if physiological_observation is not None else {
            "pulse_rate": float(metrics.get("bpm", 0.0)),
            "rate_state": "UNVERIFIED" if not is_pass else "TYPICAL",
            "rr_cv": float(metrics.get("rr_cv", 1.0)),
            "irregularity_state": "UNVERIFIED" if not is_pass else "REGULAR_PULSE",
            "recheck_recommended": False
        }
        
        result = {
            "status": status,
            "reason": reason,
            "passed": is_pass or (status in ("RELIABLE", "STABILIZING", "RECHECK_REQUIRED", "IRREGULAR_RHYTHM")),
            "ai_screening_enabled": is_pass and (consec >= self.stability_threshold),
            "screening_allowed": sq["screening_allowed"],
            "consecutive_good_windows": consec,
            "stability_threshold": self.stability_threshold,
            "signal_quality": sq,
            "physiological_observation": po,
            "checks": checks,
            "metrics": metrics,
        }
        self.history.append(result)
        return result
