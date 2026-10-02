"""
CardioTwin - 5-Part Signal Reliability Gate (Phase 1 Clinical Safety Pipeline)
================================================================================
Replaces single-metric heuristic SQI with an evidence-aware 5-part physiological gate:
  1. Sensor contact / amplitude check (flatline, finger-off, ADC saturation, clipping)
  2. Sample-timing check (timestamp diff near 10ms, dropped sample detection)
  3. Peak regularity check (systolic peak prominence, spacing, and RR interval coverage)
  4. Physiological plausibility check (seated rate 40-180 BPM; outside -> VERIFY_SIGNAL, never false alarm)
  5. Window stability check (requires >= 3 consecutive 10s windows before enabling AI screening)

Computes the 5 authoritative metrics per 10-second window:
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
    Evaluates 10-second PPG windows across 5 sequential physiological gates.
    Tracks state across consecutive windows to enforce baseline stability.
    """

    def __init__(
        self,
        target_fs: float = 100.0,
        window_sec: float = 10.0,
        stability_threshold: int = 3,
        min_bpm: float = 40.0,
        max_bpm: float = 180.0,
        adc_min_limit: float = 200.0,       # Raw MAX30102 optical baseline floor for finger contact
        adc_max_limit: float = 260000.0,   # 18-bit ADC saturation limit
        max_clipping_ratio: float = 0.05,  # Max 5% clipped samples
        max_rr_cv: float = 0.35,           # Max RR interval coefficient of variation for stable rhythm
        min_peak_coverage: float = 0.65,   # Minimum 65% window coverage by valid systolic intervals
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
        Returns a dict containing:
          - 5 core metrics: sample_rate_estimate, bpm, peak_coverage, rr_cv, clipping_ratio
          - gate check pass/fail flags
          - status: FINGER_OFF, SENSOR_SATURATED, POOR_TIMING, POOR_CONTACT, VERIFY_SIGNAL, STABILIZING, RELIABLE
          - ai_screening_enabled: bool (True only when status is RELIABLE)
        """
        self.total_windows_evaluated += 1
        raw_arr = np.asarray(raw_samples, dtype=float)
        n_samples = len(raw_arr)
        window_duration = n_samples / self.target_fs if n_samples > 0 else self.window_sec

        # Default fallback metric values
        sample_rate_estimate = float(self.target_fs)
        bpm = 0.0
        peak_coverage = 0.0
        rr_cv = 1.0
        clipping_ratio = 0.0

        checks = {
            "contact_amplitude": False,
            "sample_timing": False,
            "peak_regularity": False,
            "physiological_plausibility": False,
            "window_stability": False,
        }

        # -------------------------------------------------------------
        # GATE 1: SENSOR CONTACT & AMPLITUDE CHECK
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
                is_pass=False
            )

        raw_std = float(np.std(raw_arr))
        raw_ptp = float(np.ptp(raw_arr))
        raw_median = float(np.median(raw_arr))

        # Check clipping / ADC saturation FIRST
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
                is_pass=False
            )

        if raw_std < 0.05 or raw_ptp < 1.0 or raw_median < self.adc_min_limit:
            self.consecutive_good_windows = 0
            return self._build_result(
                status="FINGER_OFF",
                reason="Sensor liftoff or flatline detected (amplitude below optical threshold)",
                checks=checks,
                metrics={
                    "sample_rate_estimate": sample_rate_estimate,
                    "bpm": 0.0,
                    "peak_coverage": 0.0,
                    "rr_cv": 1.0,
                    "clipping_ratio": clipping_ratio,
                    "sqi": 0.0,
                },
                is_pass=False
            )

        checks["contact_amplitude"] = True

        # -------------------------------------------------------------
        # GATE 2: SAMPLE-TIMING CHECK
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
                        is_pass=False
                    )

        checks["sample_timing"] = True

        # -------------------------------------------------------------
        # GATE 3: PEAK REGULARITY CHECK
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
                is_pass=False
            )

        rr_sec = np.diff(peaks) / sample_rate_estimate
        median_rr = float(np.median(rr_sec)) if len(rr_sec) > 0 else 0.0
        raw_bpm = float(60.0 / median_rr) if median_rr > 0 else 0.0
        raw_rr_cv = float(np.std(rr_sec) / (np.mean(rr_sec) + 1e-6)) if len(rr_sec) > 0 else 1.0

        sig_kurt = float(kurtosis(norm_sig))
        peak_amps = norm_sig[peaks]
        peak_amp_cv = float(np.std(peak_amps) / (abs(np.mean(peak_amps)) + 1e-6))
        sqi = float(max(0.0, min(1.0, (abs(sig_kurt) / 6.0) * (1.0 / (peak_amp_cv + 0.5)))))

        # -------------------------------------------------------------
        # GATE 4: PHYSIOLOGICAL PLAUSIBILITY CHECK
        # -------------------------------------------------------------
        # For a normal seated demo, accept pulse rate only between 40-180 BPM.
        # Outside that range, mark the reading as VERIFY_SIGNAL, never an arrhythmia!
        if raw_bpm < self.min_bpm or raw_bpm > self.max_bpm:
            self.consecutive_good_windows = 0
            coverage_val = float(min(1.0, np.sum(rr_sec) / window_duration))
            return self._build_result(
                status="VERIFY_SIGNAL",
                reason=f"Pulse rate ({raw_bpm:.1f} BPM) outside plausible resting range [{self.min_bpm:.0f}, {self.max_bpm:.0f}]. Verify probe position.",
                checks=checks,
                metrics={
                    "sample_rate_estimate": round(sample_rate_estimate, 1),
                    "bpm": round(raw_bpm, 1),
                    "peak_coverage": round(coverage_val, 3),
                    "rr_cv": round(raw_rr_cv, 3),
                    "clipping_ratio": round(clipping_ratio, 3),
                    "sqi": round(sqi, 3),
                },
                is_pass=False
            )

        checks["physiological_plausibility"] = True

        # Check peak coverage and regularity for resting range
        min_rr_sec = 60.0 / self.max_bpm
        max_rr_sec = 60.0 / self.min_bpm
        valid_mask = (rr_sec >= min_rr_sec * 0.85) & (rr_sec <= max_rr_sec * 1.15)
        valid_rr = rr_sec[valid_mask]

        if len(valid_rr) >= 2:
            bpm = float(60.0 / np.median(valid_rr))
            valid_duration = float(np.sum(valid_rr))
            peak_coverage = float(min(1.0, valid_duration / window_duration))
            rr_cv = float(np.std(valid_rr) / (np.mean(valid_rr) + 1e-6))
        else:
            bpm = raw_bpm
            peak_coverage = 0.0
            rr_cv = raw_rr_cv

        if peak_coverage < self.min_peak_coverage or rr_cv > self.max_rr_cv:
            self.consecutive_good_windows = 0
            reason_msg = (
                f"Low pulse regularity (Coverage: {peak_coverage*100:.1f}% < {self.min_peak_coverage*100:.0f}%, "
                f"RR CV: {rr_cv:.2f} > {self.max_rr_cv:.2f})"
            )
            return self._build_result(
                status="POOR_REGULARITY",
                reason=reason_msg,
                checks=checks,
                metrics={
                    "sample_rate_estimate": round(sample_rate_estimate, 1),
                    "bpm": round(bpm, 1),
                    "peak_coverage": round(peak_coverage, 3),
                    "rr_cv": round(rr_cv, 3),
                    "clipping_ratio": round(clipping_ratio, 3),
                    "sqi": round(sqi, 3),
                },
                is_pass=False
            )

        checks["peak_regularity"] = True

        # -------------------------------------------------------------
        # GATE 4: PHYSIOLOGICAL PLAUSIBILITY CHECK
        # -------------------------------------------------------------
        if bpm < self.min_bpm or bpm > self.max_bpm:
            self.consecutive_good_windows = 0
            return self._build_result(
                status="VERIFY_SIGNAL",
                reason=f"Pulse rate ({bpm:.1f} BPM) outside plausible resting range [40, 180]. Verify probe position.",
                checks=checks,
                metrics={
                    "sample_rate_estimate": round(sample_rate_estimate, 1),
                    "bpm": round(bpm, 1),
                    "peak_coverage": round(peak_coverage, 3),
                    "rr_cv": round(rr_cv, 3),
                    "clipping_ratio": round(clipping_ratio, 3),
                    "sqi": round(sqi, 3),
                },
                is_pass=False
            )

        checks["physiological_plausibility"] = True

        # -------------------------------------------------------------
        # GATE 5: WINDOW STABILITY CHECK
        # -------------------------------------------------------------
        self.consecutive_good_windows += 1

        if self.consecutive_good_windows < self.stability_threshold:
            checks["window_stability"] = False
            return self._build_result(
                status=f"STABILIZING",
                reason=f"Acquiring stable baseline (Window {self.consecutive_good_windows}/{self.stability_threshold})",
                checks=checks,
                metrics={
                    "sample_rate_estimate": round(sample_rate_estimate, 1),
                    "bpm": round(bpm, 1),
                    "peak_coverage": round(peak_coverage, 3),
                    "rr_cv": round(rr_cv, 3),
                    "clipping_ratio": round(clipping_ratio, 3),
                    "sqi": round(sqi, 3),
                },
                is_pass=False,
                consecutive=self.consecutive_good_windows
            )

        checks["window_stability"] = True
        return self._build_result(
            status="RELIABLE",
            reason=f"Signal validated across {self.consecutive_good_windows} consecutive windows",
            checks=checks,
            metrics={
                "sample_rate_estimate": round(sample_rate_estimate, 1),
                "bpm": round(bpm, 1),
                "peak_coverage": round(peak_coverage, 3),
                "rr_cv": round(rr_cv, 3),
                "clipping_ratio": round(clipping_ratio, 3),
                "sqi": round(sqi, 3),
            },
            is_pass=True,
            consecutive=self.consecutive_good_windows
        )

    def _build_result(
        self,
        status: str,
        reason: str,
        checks: dict,
        metrics: dict,
        is_pass: bool,
        consecutive: int = None
    ) -> dict:
        consec = consecutive if consecutive is not None else self.consecutive_good_windows
        result = {
            "status": status,
            "reason": reason,
            "passed": is_pass or (status in ("RELIABLE", "STABILIZING")),
            "ai_screening_enabled": is_pass and (consec >= self.stability_threshold),
            "consecutive_good_windows": consec,
            "stability_threshold": self.stability_threshold,
            "checks": checks,
            "metrics": metrics,
        }
        self.history.append(result)
        return result
