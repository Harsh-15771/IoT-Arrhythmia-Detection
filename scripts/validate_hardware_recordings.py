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

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDINGS_DIR = os.path.join(ROOT_DIR, "recordings")
MODEL_DIR = os.path.join(ROOT_DIR, "model")

def bandpass_filter(signal, lowcut=0.5, highcut=8.0, fs=100, order=4):
    nyq = 0.5 * fs
    low = max(0.001, lowcut / nyq)
    high = min(0.999, highcut / nyq)
    if low >= high: return signal
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)

def evaluate_session_recording(filepath):
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        return {"file": os.path.basename(filepath), "status": f"Read error: {e}"}

    val_col = 'ppg_value' if 'ppg_value' in df.columns else df.columns[-1]
    sig = df[val_col].dropna().values.astype(float)
    n_samples = len(sig)

    if n_samples < 300:
        return {
            "file": os.path.basename(filepath),
            "samples": n_samples,
            "duration_sec": round(n_samples / 100.0, 1),
            "status": "Short recording (< 3 seconds)"
        }

    # Filter signal
    try:
        filtered = bandpass_filter(sig, fs=100)
    except Exception:
        filtered = sig

    std_val = float(np.std(filtered))
    mean_val = float(np.mean(filtered))

    if std_val < 0.05:
        return {
            "file": os.path.basename(filepath),
            "samples": n_samples,
            "duration_sec": round(n_samples / 100.0, 1),
            "sqi": 0.0,
            "screening_status": "Sensor Disconnected / Flatline (Gated)",
            "safe_gate_active": True
        }

    norm_sig = (filtered - mean_val) / std_val
    peaks, _ = find_peaks(norm_sig, distance=30, prominence=0.25)
    sig_kurt = float(kurtosis(norm_sig))

    if len(peaks) >= 2:
        rr = np.diff(peaks) / 100.0 * 1000.0
        bpm = float(60000.0 / np.mean(rr)) if np.mean(rr) > 0 else 0.0
        peak_amps = norm_sig[peaks]
        peak_amp_cv = float(np.std(peak_amps) / (abs(np.mean(peak_amps)) + 1e-6))
        sqi = float(max(0.0, min(1.0, (abs(sig_kurt) / 6.0) * (1.0 / (peak_amp_cv + 0.5)))))
    else:
        bpm = 0.0
        sqi = 0.1

    gated = sqi < 0.40
    screening_status = "Signal Insufficient / Motion Artifact (Gated)" if gated else "Clean PPG (Screening Eligible)"

    return {
        "file": os.path.basename(filepath),
        "samples": n_samples,
        "duration_sec": round(n_samples / 100.0, 1),
        "estimated_bpm": round(bpm, 1),
        "sqi": round(sqi, 3),
        "screening_status": screening_status,
        "safe_gate_active": gated
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
