"""
CardioTwin - Session Signal Reliability Report & Quality Audit
==============================================================
Ingests PPG session recordings (CSV files) and runs the authoritative
5-part Signal Reliability Gate per 10-second window.

Outputs the 5 core validation numbers:
  1. sample_rate_estimate (Hz)
  2. bpm (BPM)
  3. peak_coverage (0.00 - 1.00)
  4. rr_cv (Coefficient of variation of pulse intervals)
  5. clipping_ratio (Fraction of ADC-clipped/saturated samples)
"""

import os
import sys
import glob
import argparse
import numpy as np
import pandas as pd

# Add root to sys.path to import backend modules
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.signal_gate import SignalReliabilityGate


def analyze_session_csv(csv_path: str, verbose: bool = True) -> dict:
    gate = SignalReliabilityGate(
        target_fs=100.0,
        window_sec=10.0,
        stability_threshold=3,
        min_bpm=40.0,
        max_bpm=180.0
    )

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return {"file": os.path.basename(csv_path), "error": str(e)}

    val_col = 'ppg_value' if 'ppg_value' in df.columns else df.columns[-1]
    ts_col = 'timestamp_ms' if 'timestamp_ms' in df.columns else None

    raw_signal = df[val_col].dropna().values.astype(float)
    timestamps = df[ts_col].values if ts_col is not None else None

    n_samples = len(raw_signal)
    duration_sec = n_samples / 100.0

    if verbose:
        print("\n" + "=" * 80)
        print(f"  CARDIO-TWIN SIGNAL RELIABILITY AUDIT: {os.path.basename(csv_path)}")
        print(f"  Total Samples: {n_samples:,} | Duration: {duration_sec:.1f}s | Target Rate: 100 Hz")
        print("=" * 80)

    if n_samples < 300:
        if verbose:
            print(f"  [SKIPPED] Insufficient session length ({n_samples} samples < 3.0s)")
        return {
            "file": os.path.basename(csv_path),
            "samples": n_samples,
            "duration_sec": round(duration_sec, 1),
            "status": "INSUFFICIENT_DURATION",
            "windows": []
        }

    # Slice into 10-second windows (1,000 samples each)
    window_samples = 1000
    n_windows = max(1, n_samples // window_samples)
    window_results = []

    if verbose:
        print(f"  {'WIN':<4} | {'FS (Hz)':<7} | {'BPM':<6} | {'COVERAGE':<8} | {'RR CV':<7} | {'CLIP %':<6} | {'STATUS':<15} | {'AI SCREEN'}")
        print("  " + "-" * 76)

    for w_idx in range(n_windows):
        start_idx = w_idx * window_samples
        end_idx = min(start_idx + window_samples, n_samples)
        
        # If last window is shorter than 6 seconds, break
        if (end_idx - start_idx) < 600:
            break

        w_samples = raw_signal[start_idx:end_idx]
        w_ts = timestamps[start_idx:end_idx] if timestamps is not None else None

        res = gate.evaluate_window(w_samples, timestamps_ms=w_ts)
        m = res["metrics"]
        window_results.append({
            "window_index": w_idx + 1,
            "sample_rate_estimate": m["sample_rate_estimate"],
            "bpm": m["bpm"],
            "peak_coverage": m["peak_coverage"],
            "rr_cv": m["rr_cv"],
            "clipping_ratio": m["clipping_ratio"],
            "sqi": m["sqi"],
            "status": res["status"],
            "ai_screening_enabled": res["ai_screening_enabled"],
            "reason": res["reason"]
        })

        if verbose:
            ai_flag = "ENABLED" if res["ai_screening_enabled"] else "GATED"
            print(
                f"  #{w_idx+1:<3} | "
                f"{m['sample_rate_estimate']:>7.1f} | "
                f"{m['bpm']:>6.1f} | "
                f"{m['peak_coverage']*100:>7.1f}% | "
                f"{m['rr_cv']:>7.3f} | "
                f"{m['clipping_ratio']*100:>5.1f}% | "
                f"{res['status']:<15} | "
                f"{ai_flag}"
            )

    # Session Summary
    reliable_windows = sum(1 for w in window_results if w["status"] == "RELIABLE")
    total_evaluated = len(window_results)

    session_summary = {
        "file": os.path.basename(csv_path),
        "samples": n_samples,
        "duration_sec": round(duration_sec, 1),
        "total_windows": total_evaluated,
        "reliable_windows": reliable_windows,
        "reliability_ratio": round(reliable_windows / max(1, total_evaluated), 2),
        "overall_status": "RELIABLE" if reliable_windows >= 1 else (window_results[-1]["status"] if window_results else "EMPTY"),
        "windows": window_results
    }

    if verbose:
        print("  " + "-" * 76)
        print(f"  SESSION VERDICT: {session_summary['overall_status']} ({reliable_windows}/{total_evaluated} windows passed 5-part gate)")
        if session_summary['overall_status'] != 'RELIABLE' and window_results:
            print(f"  Latest Flag Reason: {window_results[-1]['reason']}")
        print("=" * 80 + "\n")

    return session_summary


def main():
    parser = argparse.ArgumentParser(description="CardioTwin 5-Part Signal Reliability Gate Audit")
    parser.add_argument("--file", type=str, default=None, help="Path to single recording CSV file")
    parser.add_argument("--dir", type=str, default="recordings", help="Directory of recording CSV files")
    args = parser.parse_args()

    if args.file and os.path.exists(args.file):
        analyze_session_csv(args.file, verbose=True)
    else:
        rec_dir = os.path.join(ROOT_DIR, args.dir)
        csv_files = sorted(glob.glob(os.path.join(rec_dir, "**", "*.csv"), recursive=True))
        print(f"\n[INFO] Found {len(csv_files)} recording files in '{rec_dir}'. Running quality audit on sessions with >= 500 samples...")
        
        passed_sessions = 0
        audited_sessions = 0

        for f in csv_files:
            summary = analyze_session_csv(f, verbose=True)
            if summary.get("total_windows", 0) > 0:
                audited_sessions += 1
                if summary["overall_status"] == "RELIABLE":
                    passed_sessions += 1

        print("\n" + "=" * 80)
        print("  HARDWARE RECORDING AUDIT SUMMARY")
        print("=" * 80)
        print(f"  Total Session Files:        {len(csv_files)}")
        print(f"  Sessions Audited (>= 6s):   {audited_sessions}")
        print(f"  Reliable Multi-Window:      {passed_sessions}")
        print(f"  Gated (Artifact/Liftoff):   {audited_sessions - passed_sessions}")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
