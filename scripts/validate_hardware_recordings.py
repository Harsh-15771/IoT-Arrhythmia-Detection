"""
CardioTwin - Hardware Recording & SQI Validation Suite
Evaluates raw live session recordings captured from the ESP32 MAX30102 sensor.
Tests:
  1. Duration and sampling rate consistency (target: 100 Hz).
  2. Signal Quality Index (SQI) and motion artifact rejection.
  3. Safe gating of unvalidated low-perfusion data.
"""

import os
import glob
import json
import joblib
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, butter, filtfilt
from scipy.stats import skew, kurtosis

import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
RECORDINGS_DIR = os.path.join(ROOT_DIR, "recordings")
MODEL_DIR = os.path.join(ROOT_DIR, "model")

def bandpass_filter(signal, lowcut=0.5, highcut=8.0, fs=100, order=4):
    nyq = 0.5 * fs
    low = max(0.001, lowcut / nyq)
    high = min(0.999, highcut / nyq)
    if low >= high: return signal
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)

from backend.signal_gate import SignalReliabilityGate

def evaluate_session_recording(filepath):
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        return {"file": os.path.basename(filepath), "status": f"Read error: {e}"}

    val_col = 'ppg_value' if 'ppg_value' in df.columns else df.columns[-1]
    ts_col = 'timestamp_ms' if 'timestamp_ms' in df.columns else None

    sig = df[val_col].dropna().values.astype(float)
    ts = df[ts_col].values if ts_col is not None else None
    n_samples = len(sig)

    if n_samples < 300:
        return {
            "file": os.path.basename(filepath),
            "samples": n_samples,
            "duration_sec": round(n_samples / 100.0, 1),
            "status": "Short recording (< 3 seconds)",
            "safe_gate_active": True
        }

    gate = SignalReliabilityGate(target_fs=100.0, window_sec=10.0, stability_threshold=3, min_bpm=40.0, max_bpm=180.0)
    res = gate.evaluate_window(sig[:1000], timestamps_ms=ts[:1000] if ts is not None else None)
    m = res["metrics"]

    gated = not res["ai_screening_enabled"]
    screening_status = f"{res['status']} ({'Screening Eligible' if not gated else 'Gated'})"

    return {
        "file": os.path.basename(filepath),
        "samples": n_samples,
        "duration_sec": round(n_samples / 100.0, 1),
        "estimated_bpm": round(m["bpm"], 1),
        "sqi": round(m["sqi"], 3),
        "sample_rate_estimate": m["sample_rate_estimate"],
        "peak_coverage": m["peak_coverage"],
        "rr_cv": m["rr_cv"],
        "clipping_ratio": m["clipping_ratio"],
        "screening_status": screening_status,
        "safe_gate_active": gated,
        "reason": res["reason"]
    }

def run_hardware_audit():
    print("=" * 65)
    print("  CardioTwin — Hardware Recording & SQI Audit Suite")
    print("=" * 65)

    csv_files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "*.csv")))
    print(f"Found {len(csv_files)} recorded sessions in '{RECORDINGS_DIR}'.\n")

    audit_records = []
    gated_count = 0
    clean_count = 0

    for fpath in csv_files:
        res = evaluate_session_recording(fpath)
        audit_records.append(res)
        if res.get("safe_gate_active"):
            gated_count += 1
        elif "Clean" in res.get("screening_status", ""):
            clean_count += 1

    # Print summary of sessions with >= 5 seconds
    long_sessions = [r for r in audit_records if r.get("samples", 0) >= 500]
    print(f"Sessions with >= 5 seconds of telemetry: {len(long_sessions)}")
    for s in long_sessions:
        print(f"  {s['file']:<28} | {s['duration_sec']:4.1f}s | SQI: {s.get('sqi', 0.0):.2f} | BPM: {s.get('estimated_bpm', 0.0):4.1f} | {s['screening_status']}")

    print("\n" + "=" * 65)
    print(f"  AUDIT SUMMARY:")
    print(f"  Total Session Files:        {len(csv_files)}")
    print(f"  Sufficient Duration (>=5s): {len(long_sessions)}")
    print(f"  SQI Safe-Gated (Artifact):  {gated_count}")
    print(f"  Safety Mechanism:           SQI < 0.40 rejects critical false alarms.")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    run_hardware_audit()
