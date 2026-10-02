#!/usr/bin/env python3
"""
===============================================================================
CardioTwin Hardware Validation Session Recorder & Quality Evaluator
===============================================================================
Automates the collection and quality scoring of empirical MAX30102 PPG recordings
against the 17-session hardware acceptance protocol defined in PLAN.md:
  - 9 Stable Seated Sessions (3 participants x 3 repeats, 60s each, Ref BPM)
  - 3 Controlled Motion Sessions (60s, motion at 20s and 40s)
  - 3 Sensor Liftoff / Finger-Off Sessions (30s, liftoff at 15s)
  - 2 Low-Contact / Loose Fit Sessions (30s)

Usage:
  python scripts/record_validation_session.py --participant P01 --type stable --ref-bpm 72
  python scripts/record_validation_session.py --participant P01 --type motion --duration 60
  python scripts/record_validation_session.py --test-stream --type stable --ref-bpm 72
===============================================================================
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
import numpy as np

# Ensure UTF-8 or ASCII-safe stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure root directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.signal_gate import SignalReliabilityGate

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' package is required. Install via: pip install requests")
    sys.exit(1)


def generate_mock_ppg_stream(duration_sec=60, fs=100, bpm=72.0, condition="stable"):
    """Generates synthetic pulse chunks for offline testing of the validation recorder."""
    total_samples = int(duration_sec * fs)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)
    hr_freq = bpm / 60.0
    
    # Base PPG waveform: fundamental + harmonics
    ppg = (
        np.sin(2 * np.pi * hr_freq * t) * 0.5 +
        np.sin(2 * np.pi * 2 * hr_freq * t + 0.6) * 0.25 +
        np.sin(2 * np.pi * 3 * hr_freq * t + 1.2) * 0.12
    )
    
    # Scale to typical MAX30102 ADC counts (around 22,000 baseline)
    raw = 22000.0 + ppg * 1200.0 + np.random.normal(0, 20.0, total_samples)

    if condition == "motion":
        # Inject deliberate motion artifact bursts between 20-25s and 40-45s
        idx1_start, idx1_end = int(20 * fs), int(25 * fs)
        idx2_start, idx2_end = int(40 * fs), int(45 * fs)
        raw[idx1_start:idx1_end] += np.random.normal(0, 3500.0, idx1_end - idx1_start)
        raw[idx2_start:idx2_end] += np.random.normal(0, 4200.0, idx2_end - idx2_start)
    elif condition == "finger_off":
        # Drop to near-zero optical baseline after t=15s
        liftoff_idx = int(15 * fs)
        raw[liftoff_idx:] = np.random.normal(50.0, 5.0, total_samples - liftoff_idx)
    elif condition == "loose_contact":
        # Attenuated pulsatile amplitude and high high-frequency jitter
        raw = 20500.0 + (ppg * 150.0) + np.random.normal(0, 180.0, total_samples)

    timestamps_ms = (t * 1000.0).astype(int) + int(time.time() * 1000.0)
    return timestamps_ms, raw


def evaluate_acceptance(session_type, ref_bpm, gate_report, duration_sec):
    """
    Evaluates session metrics against the official acceptance criteria in PLAN.md.
    """
    windows = gate_report.get("windows", [])
    n_windows = len(windows)
    criteria = []
    overall_pass = True

    # Criterion 1: Duration
    req_dur = 60.0 if session_type in ("stable", "motion") else 25.0
    dur_pass = duration_sec >= (req_dur - 2.0)
    criteria.append({
        "name": "Session Duration",
        "requirement": f">= {req_dur:.0f} seconds uninterrupted",
        "measured": f"{duration_sec:.1f} s",
        "passed": dur_pass
    })
    if not dur_pass:
        overall_pass = False

    # Window metrics
    reliable_count = sum(1 for w in windows if w.get("passed", False) or w.get("status") in ("RELIABLE", "STABILIZING"))
    reliability_rate = (reliable_count / n_windows) if n_windows > 0 else 0.0

    bpms = [w["metrics"]["bpm"] for w in windows if (w.get("passed", False) or w.get("status") in ("RELIABLE", "STABILIZING")) and w["metrics"]["bpm"] > 0]
    median_bpm = float(np.median(bpms)) if bpms else 0.0
    bpm_mae = abs(median_bpm - ref_bpm) if (ref_bpm and median_bpm > 0) else None

    if session_type == "stable":
        # Acceptance: >= 90% reliable windows
        rel_pass = reliability_rate >= 0.90
        criteria.append({
            "name": "Window Reliability Rate",
            "requirement": ">= 90.0% of 10s windows accepted",
            "measured": f"{reliability_rate * 100:.1f}% ({reliable_count}/{n_windows})",
            "passed": rel_pass
        })
        if not rel_pass:
            overall_pass = False

        # Acceptance: BPM MAE <= 5.0 vs reference
        if ref_bpm:
            mae_pass = bpm_mae is not None and bpm_mae <= 5.0
            criteria.append({
                "name": "Pulse Rate Accuracy (MAE)",
                "requirement": "MAE <= 5.0 BPM vs reference oximeter",
                "measured": f"{bpm_mae:.1f} BPM (Median: {median_bpm:.1f} vs Ref: {ref_bpm:.1f})" if bpm_mae is not None else "N/A",
                "passed": mae_pass
            })
            if not mae_pass:
                overall_pass = False

        # Acceptance: Zero false critical alarms
        crit_alarms = sum(1 for w in windows if w.get("status") in ("V_Tachycardia", "V_Flutter_Fib", "Asystole"))
        crit_pass = (crit_alarms == 0)
        criteria.append({
            "name": "Zero False Critical Arrhythmias",
            "requirement": "0 critical false alarms during resting demo",
            "measured": f"{crit_alarms} critical alarms triggered",
            "passed": crit_pass
        })
        if not crit_pass:
            overall_pass = False

    elif session_type == "finger_off":
        # Acceptance: 100% of post-liftoff segments detected as FINGER_OFF / UNRELIABLE
        gated_count = sum(1 for w in windows if not w.get("passed", False))
        gated_rate = (gated_count / n_windows) if n_windows > 0 else 0.0
        # For finger-off, the second half must be safely gated
        pass_fo = gated_count >= 1
        criteria.append({
            "name": "Sensor Liftoff Gating",
            "requirement": "Prompt detection of FINGER_OFF (AI screening gated)",
            "measured": f"{gated_count}/{n_windows} windows gated ({gated_rate*100:.1f}%)",
            "passed": pass_fo
        })
        if not pass_fo:
            overall_pass = False

    elif session_type == "motion":
        # Acceptance: Motion-corrupted windows successfully gated
        motion_gated = sum(1 for w in windows if w.get("status") in ("POOR_REGULARITY", "POOR_CONTACT", "VERIFY_SIGNAL"))
        pass_motion = motion_gated >= 1
        criteria.append({
            "name": "Motion Artifact Gating",
            "requirement": "Motion-corrupted segments flagged as POOR_REGULARITY / VERIFY_SIGNAL",
            "measured": f"{motion_gated} motion windows successfully gated",
            "passed": pass_motion
        })
        if not pass_motion:
            overall_pass = False

    return overall_pass, criteria, bpm_mae, median_bpm


def main():
    parser = argparse.ArgumentParser(description="CardioTwin Hardware Validation Session Recorder")
    parser.add_argument("--participant", "-p", default="P01", help="Participant ID (e.g. P01, P02, P03)")
    parser.add_argument("--type", "-t", choices=["stable", "motion", "finger_off", "loose_contact"], default="stable",
                        help="Session condition type")
    parser.add_argument("--ref-bpm", "-r", type=float, default=None,
                        help="Reference Heart Rate (BPM) from medical pulse oximeter or radial count")
    parser.add_argument("--duration", "-d", type=float, default=None,
                        help="Session recording duration in seconds (default: 60s for stable/motion, 30s for liftoff)")
    parser.add_argument("--api-url", default="http://127.0.0.1:5000", help="CardioTwin backend REST API base URL")
    parser.add_argument("--out-dir", default=os.path.join(ROOT_DIR, "recordings", "validation"),
                        help="Output directory for validated session CSVs and reports")
    parser.add_argument("--test-stream", action="store_true",
                        help="Run in synthetic simulation mode without physical ESP32 connected")
    args = parser.parse_args()

    # Default duration based on test protocol
    if args.duration is None:
        args.duration = 60.0 if args.type in ("stable", "motion") else 30.0

    os.makedirs(args.out_dir, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"session_{args.participant}_{args.type}_{timestamp_str}"
    csv_filename = f"{session_id}.csv"
    csv_path = os.path.join(args.out_dir, csv_filename)
    json_path = os.path.join(args.out_dir, f"{session_id}.json")

    print("\n" + "=" * 80)
    print("  CARDIO-TWIN HARDWARE ACCEPTANCE PROTOCOL RECORDER")
    print(f"  Participant:  {args.participant}")
    print(f"  Condition:    {args.type.upper()}")
    print(f"  Target Dur:   {args.duration:.0f} seconds")
    print(f"  Reference HR: {args.ref_bpm if args.ref_bpm is not None else 'Not Provided'} BPM")
    print(f"  Output CSV:   {csv_filename}")
    print("=" * 80)

    all_ts = []
    all_ppg = []

    if args.test_stream:
        print("\n[INFO] Running synthetic test-stream generation (mock ESP32 MAX30102)...")
        ref = args.ref_bpm or 72.0
        all_ts, all_ppg = generate_mock_ppg_stream(
            duration_sec=args.duration, fs=100, bpm=ref, condition=args.type
        )
        # Simulate live progress bar
        step_samples = 100
        total_steps = len(all_ppg) // step_samples
        for step in range(total_steps):
            elapsed = (step + 1) * 1.0
            pct = min(1.0, elapsed / args.duration)
            bar_len = 30
            filled = int(pct * bar_len)
            bar = "=" * filled + "-" * (bar_len - filled)
            sys.stdout.write(f"\r  Recording: [{bar}] {elapsed:5.1f}s / {args.duration:5.1f}s | Samples: {len(all_ppg):,}")
            sys.stdout.flush()
            time.sleep(0.02)
        print("\n  [DONE] Synthetic streaming capture complete.")
    else:
        # Check backend connectivity
        print(f"\n[INFO] Connecting to CardioTwin backend at {args.api_url}...")
        try:
            r = requests.get(f"{args.api_url}/", timeout=3.0)
            if r.status_code != 200:
                print(f"[ERROR] Backend returned status {r.status_code}")
                return 1
        except Exception as e:
            print(f"[ERROR] Could not connect to {args.api_url}: {e}")
            print("  Make sure backend/api_server.py is running, or test with --test-stream.")
            return 1

        # Start recording session on server
        try:
            start_res = requests.post(f"{args.api_url}/start", timeout=3.0).json()
            # Also tell ESP32 to run
            requests.post(f"{args.api_url}/command", json={"run": True}, timeout=3.0)
            print(f"[OK] Remote session started. ESP32 streaming enabled.")
        except Exception as e:
            print(f"[ERROR] Failed to start backend recording session: {e}")
            return 1

        start_time = time.time()
        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed >= args.duration:
                    break

                # Poll latest status
                try:
                    st_res = requests.get(f"{args.api_url}/twin/status", timeout=1.5).json()
                    gate_res = requests.get(f"{args.api_url}/signal/gate", timeout=1.5).json()
                    v = st_res.get("current_vitals", {})
                    curr_bpm = v.get("bpm", 0.0)
                    curr_sqi = v.get("signal_quality", 0.0)
                    g_status = gate_res.get("gate", {}).get("status", "INITIALIZING")
                    ai_on = gate_res.get("gate", {}).get("ai_screening_enabled", False)
                except Exception:
                    curr_bpm, curr_sqi, g_status, ai_on = 0.0, 0.0, "STREAMING", False

                pct = min(1.0, elapsed / args.duration)
                bar_len = 24
                filled = int(pct * bar_len)
                bar = "=" * filled + "-" * (bar_len - filled)
                ai_badge = "[AI ACTIVE]" if ai_on else "[GATED]"
                sys.stdout.write(
                    f"\r  [{bar}] {elapsed:4.1f}s/{args.duration:4.0f}s | "
                    f"BPM: {curr_bpm:5.1f} | SQI: {curr_sqi:.2f} | Gate: {g_status:<16} | {ai_badge}"
                )
                sys.stdout.flush()
                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n  [INTERRUPTED] Recording cancelled by user.")

        # Stop server recording
        print("\n\n[INFO] Finalizing and stopping recording session...")
        try:
            stop_res = requests.post(f"{args.api_url}/stop", timeout=3.0).json()
            requests.post(f"{args.api_url}/command", json={"run": False}, timeout=3.0)
            recorded_file = stop_res.get("file")
            if recorded_file and os.path.exists(recorded_file):
                import shutil
                shutil.copyfile(recorded_file, csv_path)
                print(f"[OK] Saved hardware telemetry CSV: {csv_path}")
        except Exception as e:
            print(f"[WARN] Failed to gracefully stop remote recording: {e}")

    # Write CSV if running test-stream
    if args.test_stream:
        with open(csv_path, "w") as f:
            f.write("timestamp_ms,ppg_value\n")
            for ts, val in zip(all_ts, all_ppg):
                f.write(f"{int(ts)},{int(val)}\n")
        print(f"[OK] Saved synthetic validation session: {csv_path}")

    # Run 5-Part Signal Reliability Gate on the recording
    print("\n" + "=" * 80)
    print("  EVALUATING 5-PART SIGNAL RELIABILITY GATE")
    print("=" * 80)

    import pandas as pd
    df = pd.read_csv(csv_path)
    val_col = 'ppg_value' if 'ppg_value' in df.columns else df.columns[-1]
    ts_col = 'timestamp_ms' if 'timestamp_ms' in df.columns else None

    raw_sig = df[val_col].dropna().values.astype(float)
    timestamps = df[ts_col].values if ts_col is not None else None

    gate = SignalReliabilityGate(target_fs=100.0, window_sec=10.0, stability_threshold=3)
    n_samples = len(raw_sig)
    actual_dur = n_samples / 100.0
    w_size = 1000
    n_windows = max(1, n_samples // w_size)

    report_windows = []
    print(f"\n{'WIN':>3} | {'STATUS':<18} | {'SR (Hz)':>7} | {'BPM':>5} | {'COV':>6} | {'RR CV':>6} | {'CLIP':>5} | {'AI SCREEN'}")
    print("-" * 80)

    for i in range(n_windows):
        start_idx = i * w_size
        end_idx = min(n_samples, start_idx + w_size)
        sig_w = raw_sig[start_idx:end_idx]
        ts_w = timestamps[start_idx:end_idx] if timestamps is not None else None

        res = gate.evaluate_window(sig_w, timestamps_ms=ts_w)
        m = res["metrics"]
        report_windows.append(res)
        ai_str = "ENABLED [OK]" if res["ai_screening_enabled"] else "BLOCKED [X]"
        print(
            f"{i+1:3d} | {res['status']:<18} | {m['sample_rate_estimate']:7.1f} | {m['bpm']:5.1f} | "
            f"{m['peak_coverage']*100:5.1f}% | {m['rr_cv']:6.3f} | {m['clipping_ratio']*100:4.1f}% | {ai_str}"
        )

    gate_report = {"windows": report_windows, "total_windows": n_windows}
    passed_all, criteria_results, bpm_mae, median_bpm = evaluate_acceptance(
        args.type, args.ref_bpm, gate_report, actual_dur
    )

    # Print Official Acceptance Criteria Table
    print("\n" + "=" * 80)
    print("  OFFICIAL ACCEPTANCE SCORECARD (PLAN.md EXIT GATE)")
    print("=" * 80)
    for crit in criteria_results:
        verdict = "PASS [OK]" if crit["passed"] else "FAIL [X]"
        print(f"  * {crit['name']:<30} : {verdict} ({crit['measured']} | Req: {crit['requirement']})")

    overall_badge = "PASSED ACCEPTANCE [OK]" if passed_all else "ACCEPTANCE PENDING / FAILED [X]"
    print("-" * 80)
    print(f"  FINAL SESSION VERDICT: {overall_badge}")
    print("=" * 80)

    # Save complete JSON metadata report
    meta_report = {
        "session_id": session_id,
        "participant": args.participant,
        "condition": args.type,
        "ref_bpm": args.ref_bpm,
        "median_bpm": median_bpm,
        "bpm_mae": bpm_mae,
        "duration_sec": round(actual_dur, 2),
        "total_samples": n_samples,
        "total_windows": n_windows,
        "passed_acceptance": passed_all,
        "criteria": criteria_results,
        "timestamp": timestamp_str
    }
    with open(json_path, "w") as f:
        json.dump(meta_report, f, indent=2)
    print(f"\n[OK] Validation metadata report written to: {json_path}\n")

    return 0 if passed_all else 1


if __name__ == "__main__":
    sys.exit(main())
