"""
CardioTwin - Hierarchical Clinical Decision Architecture (Phase 2)
Implements:
  1. Layer 1: Deterministic Physiological Pulse State Rules (Non-Diagnostic Observations)
  2. Layer 2: Multi-Window Persistence Consensus Engine & Asymmetric Class Thresholds
"""

from collections import deque
import numpy as np


class PhysiologicalPulseRules:
    """
    Layer 1: Deterministic Physiological Pulse State
    Rule-based observations derived from validated resting pulse rate and SpO2.
    Strictly non-diagnostic: outputs observations and review flags rather than disease diagnoses.
    """
    def __init__(self, sustained_window_count=3):
        self.sustained_window_count = sustained_window_count
        self.bpm_history = deque(maxlen=sustained_window_count)
        self.spo2_history = deque(maxlen=sustained_window_count)

    def reset(self):
        self.bpm_history.clear()
        self.spo2_history.clear()

    def evaluate(self, bpm: float, spo2: float = None, signal_reliable: bool = True):
        if not signal_reliable or bpm <= 0:
            return {
                "pulse_state": "UNVERIFIED_SIGNAL",
                "pulse_state_label": "Unverified Signal (Gated)",
                "oxygenation_state": "UNVERIFIED_SIGNAL",
                "oxygenation_label": "Unverified Signal (Gated)",
                "observation_flags": []
            }

        self.bpm_history.append(float(bpm))

        flags = []
        # Pulse Rate Rules
        if bpm < 50.0:
            pulse_state = "LOW_PULSE_RATE"
            pulse_label = f"Low Pulse-Rate Observation ({bpm:.1f} BPM < 50 BPM)"
            flags.append("LOW_PULSE_RATE")
        elif bpm <= 100.0:
            pulse_state = "TYPICAL_RESTING"
            pulse_label = f"Typical Resting Range ({bpm:.1f} BPM)"
        elif bpm <= 120.0:
            pulse_state = "ELEVATED_PULSE_RATE"
            pulse_label = f"Elevated Pulse-Rate Observation ({bpm:.1f} BPM)"
            flags.append("ELEVATED_PULSE_RATE")
        else:
            # Over 120 BPM: Check if sustained across window history
            if len(self.bpm_history) >= self.sustained_window_count and all(b > 120.0 for b in self.bpm_history):
                pulse_state = "SUSTAINED_ELEVATED"
                pulse_label = f"Sustained Elevated Pulse-Rate Observation ({bpm:.1f} BPM > 120 for {self.sustained_window_count} windows)"
                flags.append("SUSTAINED_ELEVATED_PULSE_RATE")
            else:
                pulse_state = "ELEVATED_PULSE_RATE"
                pulse_label = f"Elevated Pulse-Rate Observation ({bpm:.1f} BPM)"
                flags.append("ELEVATED_PULSE_RATE")

        # Oxygenation Rules (SpO2)
        if spo2 is None or spo2 <= 0:
            oxygenation_state = "UNAVAILABLE"
            oxygenation_label = "SpO2 Unavailable (Single IR Channel Telemetry)"
        else:
            self.spo2_history.append(float(spo2))
            if len(self.spo2_history) >= self.sustained_window_count and all(s < 92.0 for s in self.spo2_history):
                oxygenation_state = "OXYGENATION_REVIEW_FLAG"
                oxygenation_label = f"Hypoxia / Oxygenation Review Flag ({spo2:.1f}% < 92% for {self.sustained_window_count} windows)"
                flags.append("OXYGENATION_REVIEW_FLAG")
            elif spo2 < 92.0:
                oxygenation_state = "TRANSIENT_LOW_SPO2"
                oxygenation_label = f"Transient Low SpO2 ({spo2:.1f}%)"
            else:
                oxygenation_state = "TYPICAL_OXYGENATION"
                oxygenation_label = f"Normal Oxygenation ({spo2:.1f}%)"

        return {
            "pulse_state": pulse_state,
            "pulse_state_label": pulse_label,
            "oxygenation_state": oxygenation_state,
            "oxygenation_label": oxygenation_label,
            "observation_flags": flags
        }


class MultiWindowPersistenceEngine:
    """
    Layer 2: Multi-Window Persistence Agreement & Class-Specific Thresholds
    Requires >= 3 of 4 recent 10-second windows in agreement before raising an acute rhythm alert.
    Applies asymmetric confidence thresholds (0.75 for VT/VFib/Asystole vs 0.50 for Sinus rates).
    """
    CRITICAL_CLASSES = {"V_Tachycardia", "V_Flutter_Fib", "Asystole"}
    EVIDENTIARY_THRESHOLDS = {
        "V_Tachycardia": 0.75,
        "V_Flutter_Fib": 0.75,
        "Asystole": 0.75,
        "AFib": 0.55,
        "Cardiac_Paced": 0.50,
        "Tachycardia": 0.50,
        "Bradycardia": 0.50,
        "Normal": 0.40
    }

    def __init__(self, memory_windows=4, consensus_threshold=3):
        self.memory_windows = memory_windows
        self.consensus_threshold = consensus_threshold
        self.history = deque(maxlen=memory_windows)

    def reset(self):
        self.history.clear()

    def process_window(self, raw_pred_label: str, class_probabilities: dict, signal_reliable: bool = True):
        if not signal_reliable:
            self.history.clear()
            return {
                "screening_status": "GATED",
                "consensus_pattern": "Verification Required",
                "consensus_count": 0,
                "recent_history": [],
                "is_persistent": False,
                "current_window_label": "Verification Required",
                "current_window_conf": 0.0,
                "alert_message": "Signal unreliable; rhythm screening suppressed."
            }

        # Step 1: Apply Class-Specific Evidentiary Threshold
        conf = float(class_probabilities.get(raw_pred_label, 0.0))
        req_threshold = self.EVIDENTIARY_THRESHOLDS.get(raw_pred_label, 0.50)

        effective_label = raw_pred_label
        if conf < req_threshold and raw_pred_label != "Normal":
            # Demote sub-threshold abnormal predictions to Normal baseline or Inconclusive
            effective_label = "Normal" if class_probabilities.get("Normal", 0.0) >= 0.35 else "Inconclusive_Pattern"

        self.history.append({
            "label": effective_label,
            "conf": conf,
            "raw_label": raw_pred_label
        })

        recent_labels = [h["label"] for h in self.history]
        counts = {}
        for l in recent_labels:
            counts[l] = counts.get(l, 0) + 1

        top_pattern = max(counts.keys(), key=lambda k: counts[k])
        top_count = counts[top_pattern]

        # Step 2: Multi-Window Persistence Consensus
        if top_count >= self.consensus_threshold and top_pattern not in ("Normal", "Inconclusive_Pattern"):
            is_persistent = True
            screening_status = "PERSISTENT_NON_NORMAL"
            alert_msg = f"Persistent abnormal pulse pattern detected ({top_pattern}, {top_count}/{len(recent_labels)} windows). Obtain 12-lead ECG review."
        elif any(lbl not in ("Normal", "Inconclusive_Pattern") for lbl in recent_labels):
            is_persistent = False
            screening_status = "MONITORING_TRANSIENT"
            non_norm = next(lbl for lbl in reversed(recent_labels) if lbl not in ("Normal", "Inconclusive_Pattern"))
            non_norm_cnt = counts.get(non_norm, 1)
            alert_msg = f"Transient non-sustained pattern ({non_norm}, {non_norm_cnt}/{len(recent_labels)} windows). Awaiting multi-window persistence."
        else:
            is_persistent = False
            screening_status = "STABLE_NORMAL"
            alert_msg = "Stable physiological resting pattern verified."

        return {
            "screening_status": screening_status,
            "consensus_pattern": top_pattern,
            "consensus_count": top_count,
            "recent_history": recent_labels,
            "is_persistent": is_persistent,
            "current_window_label": effective_label,
            "current_window_conf": round(conf, 3),
            "alert_message": alert_msg
        }
