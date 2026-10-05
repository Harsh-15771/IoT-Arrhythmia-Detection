# ============================================================
# CardioTwin - Real-Time Cardiovascular Digital Twin Backend
# Fuses:
#   Stream 1: Patient EHR (Demographics, Labs, Framingham Risk)
#   Stream 2: Live IoT Sensor Telemetry (ESP32 MAX30102 100Hz PPG)
#   ML Core: XGBoost Acute Arrhythmia Modulator + Bayesian Fusion
#   Interactive: What-If Treatment Outcome Simulator
# ============================================================

import os
import csv
import json
import time
import threading
from datetime import datetime
from collections import deque
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit

import numpy as np
import pandas as pd
import joblib
from scipy.signal import find_peaks, butter, filtfilt, welch
from scipy.stats import skew, kurtosis

try:
    from digital_twin_engine import CardioTwin
    from framingham_risk import calculate_framingham_cvd_risk
    from signal_gate import SignalReliabilityGate
    from dual_engine import DualModalityPredictor
    from pulse_rules import PhysiologicalPulseRules, MultiWindowPersistenceEngine
    from personal_baseline import PersonalBaselineManager
except ModuleNotFoundError:
    from backend.digital_twin_engine import CardioTwin
    from backend.framingham_risk import calculate_framingham_cvd_risk
    from backend.signal_gate import SignalReliabilityGate
    from backend.dual_engine import DualModalityPredictor
    from backend.pulse_rules import PhysiologicalPulseRules, MultiWindowPersistenceEngine
    from backend.personal_baseline import PersonalBaselineManager

# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------
PORT         = 5000
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'backend' else BASE_DIR
MODEL_DIR    = os.path.join(ROOT_DIR, "model")
CSV_DIR      = os.path.join(ROOT_DIR, "recordings", "new_session", "recordings")
PATIENTS_FILE = os.path.join(BASE_DIR, "synthetic_patients.json")
if not os.path.exists(PATIENTS_FILE):
    PATIENTS_FILE = os.path.join(ROOT_DIR, "synthetic_patients.json")
TARGET_FS    = 100
WINDOW_SEC   = 10
WINDOW_SAMPLES = TARGET_FS * WINDOW_SEC

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(CSV_DIR, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cardiotwin_secret_2026'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# -------------------------------------------------------
# LOAD ML MODEL ARTIFACTS
# -------------------------------------------------------
print("[INFO] Loading CardioTwin ML Model...")
model_loaded = False
try:
    xgb_model = joblib.load(os.path.join(MODEL_DIR, "xgboost_ppg_model.pkl"))
    scaler = joblib.load(os.path.join(MODEL_DIR, "scaler.pkl"))
    label_encoder = joblib.load(os.path.join(MODEL_DIR, "label_encoder.pkl"))
    feature_names = joblib.load(os.path.join(MODEL_DIR, "feature_names.pkl"))
    print(f"[INFO] XGBoost Model loaded! Classes: {list(label_encoder.classes_)}")
    model_loaded = True
except Exception as e:
    print(f"[WARN] Could not load XGBoost model: {e}. Running in heuristic fallback mode.")
    xgb_model, scaler, label_encoder, feature_names = None, None, None, []

# Initialize Phase 2 Dual-Modality Pipeline & Clinical Decision Engines
print("[INFO] Initializing Phase 2 Dual-Modality Predictor & Clinical Decision Layers...")
dual_predictor = DualModalityPredictor(MODEL_DIR)
live_pulse_rules = PhysiologicalPulseRules(sustained_window_count=3)
live_persistence_engine = MultiWindowPersistenceEngine(memory_windows=4, consensus_threshold=3)

# -------------------------------------------------------
# LOAD SYNTHETIC EHR PATIENTS COHORT
# -------------------------------------------------------
patients_db: Dict[str, Any] = {}
if os.path.exists(PATIENTS_FILE):
    with open(PATIENTS_FILE, "r") as f:
        p_list = json.load(f)
        for p in p_list:
            patients_db[p["id"]] = p
    print(f"[INFO] Loaded {len(patients_db)} synthetic Indian patient EHR records.")
else:
    print("[WARN] synthetic_patients.json not found! Generating fallback cohort...")
    from ehr_generator import generate_cohort
    p_list = generate_cohort(100, PATIENTS_FILE)
    for p in p_list:
        patients_db[p["id"]] = p

# Initialize Default Digital Twin (PAT001: High Risk Indian Male Post-PCI)
active_patient_id = "PAT001" if "PAT001" in patients_db else list(patients_db.keys())[0]
active_twin = CardioTwin(patients_db[active_patient_id])
live_baseline_manager = PersonalBaselineManager(active_patient_id)
twin_lock = threading.Lock()

# Initialize 5-Part Signal Reliability Gate (Phase 1 Clinical Safety Pipeline)
live_signal_gate = SignalReliabilityGate(
    target_fs=TARGET_FS,
    window_sec=WINDOW_SEC,
    stability_threshold=3,
    min_bpm=40.0,
    max_bpm=180.0,
    adc_min_limit=20000.0
)

# -------------------------------------------------------
# STREAMING & BUFFER STATE
# -------------------------------------------------------
state = {
    "is_recording": False,
    "active_patient_id": active_patient_id,
    "waveform_buffer": deque(maxlen=400), # 4 seconds live buffer for display
    "analysis_buffer": deque(maxlen=WINDOW_SAMPLES), # 10 seconds for feature extraction
    "timestamp_buffer": deque(maxlen=WINDOW_SAMPLES), # Timestamps for sample jitter check
    "sample_count": 0,
    "last_prediction_time": 0.0,
    "csv_file": None,
    "csv_writer": None,
    "csv_path": None,
    "status_msg": "System Ready - Digital Twin Active",
    "last_gate_result": None,
    "last_sequence": None,
    "sequence_gaps": 0,
    "last_device_id": None,
    "last_device_boot_id": None,
    "last_sample_interval_us": 10000,
    "dropped_buffers_total": 0,
    "measured_sample_rate": 100.0,
    "timing_jitter_ms": 0.0,
    "duplicate_chunks_rejected": 0
}
state_lock = threading.Lock()

# -------------------------------------------------------
# SIGNAL PROCESSING & FEATURE EXTRACTION (100 Hz)
# -------------------------------------------------------
def bandpass_filter(signal, lowcut=0.5, highcut=8.0, fs=100, order=4):
    nyq = 0.5 * fs
    low = max(0.001, lowcut / nyq)
    high = min(0.999, highcut / nyq)
    if low >= high: return signal
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)

def extract_live_features(signal, fs=100):
    if len(signal) < fs * 3:
        return None
    try:
        filtered = bandpass_filter(signal, fs=fs)
    except Exception:
        filtered = signal

    std_val = float(np.std(filtered))
    mean_val = float(np.mean(filtered))
    if std_val < 0.05:
        # Asystole / Flatline
        return {
            "bpm": 0.0, "rr_mean": 0.0, "rr_std": 0.0, "rmssd": 0.0, "sdnn": 0.0,
            "pnn50": 0.0, "pnn20": 0.0, "rr_min": 0.0, "rr_max": 0.0, "rr_range": 0.0,
            "rr_cv": 0.0, "rr_skew": 0.0, "rr_kurt": 0.0, "sig_mean": mean_val,
            "sig_std": std_val, "sig_skew": 0.0, "sig_kurt": 0.0, "sig_energy": float(np.mean(filtered**2)),
            "peak_amp_mean": 0.0, "peak_amp_std": 0.0, "peak_amp_cv": 0.0, "pulse_width_mean": 0.0,
            "pulse_width_std": 0.0, "lf_power": 0.0, "hf_power": 0.0, "lf_hf_ratio": 0.0, "sqi": 0.0
        }

    norm_sig = (filtered - mean_val) / std_val
    peaks, _ = find_peaks(norm_sig, distance=int(0.30 * fs), prominence=0.25)
    if len(peaks) < 2:
        return {
            "bpm": float(len(peaks) * 6), "rr_mean": 10000.0, "rr_std": 0.0, "rmssd": 0.0,
            "sdnn": 0.0, "pnn50": 0.0, "pnn20": 0.0, "rr_min": 10000.0, "rr_max": 10000.0,
            "rr_range": 0.0, "rr_cv": 0.0, "rr_skew": 0.0, "rr_kurt": 0.0, "sig_mean": float(np.mean(norm_sig)),
            "sig_std": float(np.std(norm_sig)), "sig_skew": float(skew(norm_sig)), "sig_kurt": float(kurtosis(norm_sig)),
            "sig_energy": float(np.mean(norm_sig**2)), "peak_amp_mean": float(np.mean(norm_sig[peaks])) if len(peaks) > 0 else 0.0,
            "peak_amp_std": 0.0, "peak_amp_cv": 0.0, "pulse_width_mean": 0.0, "pulse_width_std": 0.0,
            "lf_power": 0.0, "hf_power": 0.0, "lf_hf_ratio": 0.0, "sqi": 0.1
        }

    rr = np.diff(peaks) / fs * 1000.0
    diff_rr = np.diff(rr) if len(rr) > 1 else np.array([0.0])
    f = {}
    f['bpm']              = float(60000.0 / np.mean(rr)) if np.mean(rr) > 0 else 0.0
    f['rr_mean']          = float(np.mean(rr))
    f['rr_std']           = float(np.std(rr))
    f['rmssd']            = float(np.sqrt(np.mean(diff_rr ** 2))) if len(diff_rr) > 0 else 0.0
    f['sdnn']             = float(np.std(rr))
    f['pnn50']            = float(np.sum(np.abs(diff_rr) > 50) / max(len(diff_rr), 1) * 100.0)
    f['pnn20']            = float(np.sum(np.abs(diff_rr) > 20) / max(len(diff_rr), 1) * 100.0)
    f['rr_min']           = float(np.min(rr))
    f['rr_max']           = float(np.max(rr))
    f['rr_range']         = float(f['rr_max'] - f['rr_min'])
    f['rr_cv']            = float(f['rr_std'] / (f['rr_mean'] + 1e-6))
    f['rr_skew']          = float(skew(rr)) if len(rr) >= 3 else 0.0
    f['rr_kurt']          = float(kurtosis(rr)) if len(rr) >= 4 else 0.0
    f['sig_mean']         = float(np.mean(norm_sig))
    f['sig_std']          = float(np.std(norm_sig))
    f['sig_skew']         = float(skew(norm_sig))
    f['sig_kurt']         = float(kurtosis(norm_sig))
    f['sig_energy']       = float(np.mean(norm_sig ** 2))
    peak_amps             = norm_sig[peaks]
    f['peak_amp_mean']    = float(np.mean(peak_amps))
    f['peak_amp_std']     = float(np.std(peak_amps))
    f['peak_amp_cv']      = float(f['peak_amp_std'] / (abs(f['peak_amp_mean']) + 1e-6))
    pulse_widths          = np.diff(peaks) / fs * 1000.0
    f['pulse_width_mean'] = float(np.mean(pulse_widths))
    f['pulse_width_std']  = float(np.std(pulse_widths))
    try:
        freqs, psd = welch(norm_sig, fs=fs, nperseg=min(len(norm_sig), fs * 4))
        lf_band = (freqs >= 0.04) & (freqs < 0.15)
        hf_band = (freqs >= 0.15) & (freqs < 0.40)
        lf_power = float(np.trapz(psd[lf_band], freqs[lf_band])) if np.any(lf_band) else 0.0
        hf_power = float(np.trapz(psd[hf_band], freqs[hf_band])) if np.any(hf_band) else 0.0
        f['lf_power']     = lf_power
        f['hf_power']     = hf_power
        f['lf_hf_ratio']  = float(lf_power / (hf_power + 1e-6))
    except Exception:
        f['lf_power']     = 0.0
        f['hf_power']     = 0.0
        f['lf_hf_ratio']  = 1.0
    f['sqi'] = float(max(0.0, min(1.0, (abs(f['sig_kurt']) / 6.0) * (1.0 / (f['peak_amp_cv'] + 0.5)))))
    return f

# -------------------------------------------------------
# REST API ENDPOINTS
# -------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "system": "CardioTwin Cardiovascular Digital Twin Engine",
        "version": "3.0.0",
        "model_version": "v3-8class-2271patients",
        "status": "Investigational Screening Prototype (Non-Diagnostic)",
        "active_patient": active_twin.name,
        "endpoints": [
            "GET  /patients",
            "GET  /patient/<id>",
            "POST /patient/select",
            "GET  /twin/status",
            "POST /twin/simulate",
            "POST /twin/scenario",
            "POST /data",
            "POST /ingest_telemetry",
            "GET  /command",
            "POST /command",
            "GET  /stream",
            "POST /start",
            "POST /stop"
        ]
    })

# 1. Device Command Endpoint (ESP32 Polling & Remote Control)
@app.route("/command", methods=["GET", "POST"])
def device_command():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if "run" in data:
            with state_lock:
                state["is_recording"] = bool(data["run"])
        return jsonify({
            "status": "ok",
            "run": state["is_recording"],
            "message": "Recording state updated"
        })
    return jsonify({
        "run": state["is_recording"],
        "status": "ok",
        "active_patient": active_twin.name,
        "sample_rate": TARGET_FS
    })

# 2. Patient Directory & EHR Profiles
@app.route("/patients", methods=["GET"])
def get_patients():
    summary_list = []
    for pid, p in patients_db.items():
        summary_list.append({
            "id": pid,
            "name": p["name"],
            "age": p["age"],
            "gender": p["gender"],
            "city": p["city"],
            "state": p["state"],
            "risk_category": p.get("cardiovascular_risk", {}).get("risk_category", "Unknown"),
            "base_risk_pct": p.get("cardiovascular_risk", {}).get("recalibrated_risk_pct", 15.0),
            "primary_condition": p.get("clinical_history", {}).get("conditions", ["None"])[0]
        })
    return jsonify({"patients": summary_list, "total": len(summary_list), "active_patient_id": active_twin.patient_id})

@app.route("/patient/<pid>", methods=["GET"])
def get_patient_detail(pid):
    patient = patients_db.get(pid)
    if not patient:
        return jsonify({"error": f"Patient {pid} not found"}), 404
    return jsonify(patient)

@app.route("/patient/select", methods=["POST"])
def select_patient():
    global active_twin, state, live_baseline_manager
    data = request.get_json() or {}
    pid = data.get("patient_id")
    if pid not in patients_db:
        return jsonify({"error": f"Patient ID '{pid}' does not exist"}), 400
    
    with twin_lock:
        active_twin = CardioTwin(patients_db[pid])
        live_baseline_manager = PersonalBaselineManager(pid)
        state["active_patient_id"] = pid
        state["status_msg"] = f"Active Digital Twin switched to {active_twin.name}"
    
    # Broadcast patient switch to connected dashboards via WebSocket
    socketio.emit("patient_switched", active_twin.get_status())
    return jsonify({
        "success": True,
        "message": f"Active Digital Twin set to {active_twin.name}",
        "status": active_twin.get_status()
    })

# 3. Digital Twin Status & Live Telemetry
@app.route("/twin/status", methods=["GET"])
def get_twin_status():
    with twin_lock:
        status = active_twin.get_status()
    with state_lock:
        status["has_calibrated_baseline"] = live_baseline_manager.baseline is not None
        status["personal_baseline"] = live_baseline_manager.baseline
        status["is_calibrating"] = live_baseline_manager.is_calibrating
        if live_baseline_manager.is_calibrating:
            elapsed = time.time() - live_baseline_manager.calibration_start_time
            status["calibration_status"] = {
                "is_calibrating": True,
                "elapsed_sec": round(elapsed, 1),
                "target_duration_sec": live_baseline_manager.target_calibration_duration_sec,
                "stabilization_duration_sec": live_baseline_manager.stabilization_duration_sec,
                "windows_collected": len(live_baseline_manager.calibration_windows),
                "windows_required": 6
            }
        status["hardware_telemetry"] = {
            "device_id": state.get("last_device_id"),
            "device_boot_id": state.get("last_device_boot_id"),
            "measured_sample_rate": state.get("measured_sample_rate", 100.0),
            "timing_jitter_ms": state.get("timing_jitter_ms", 0.0),
            "sequence_gaps": state.get("sequence_gaps", 0),
            "dropped_buffers": state.get("dropped_buffers_total", 0),
            "duplicate_chunks_rejected": state.get("duplicate_chunks_rejected", 0),
            "last_sequence": state.get("last_sequence")
        }
    return jsonify(status)

# 4. Interactive "What-If" Treatment Simulator
@app.route("/twin/simulate", methods=["POST"])
def simulate_treatment():
    data = request.get_json() or {}
    with twin_lock:
        result = active_twin.simulate_treatment(data)
    return jsonify({"success": True, "simulation": result})

# 4b. 5-Part Signal Reliability Gate Status & Metrics
@app.route("/signal/gate", methods=["GET"])
def get_signal_gate():
    gate_data = state.get("last_gate_result")
    if gate_data is None:
        return jsonify({
            "status": "IDLE",
            "reason": "Awaiting live sensor stream (10s window needed)",
            "ai_screening_enabled": False,
            "consecutive_good_windows": live_signal_gate.consecutive_good_windows,
            "stability_threshold": live_signal_gate.stability_threshold,
            "metrics": {
                "sample_rate_estimate": float(TARGET_FS),
                "bpm": 0.0,
                "peak_coverage": 0.0,
                "rr_cv": 1.0,
                "clipping_ratio": 0.0,
                "sqi": 0.0
            }
        })
    return jsonify(gate_data)

# 4c. Personal Baseline Calibration & Retrieval Endpoints
@app.route("/baseline/calibrate", methods=["POST"])
def start_baseline_calibration():
    res = live_baseline_manager.start_calibration()
    return jsonify({"success": True, "calibration": res})

@app.route("/baseline/cancel", methods=["POST"])
def cancel_baseline_calibration():
    live_baseline_manager.cancel_calibration()
    return jsonify({"success": True, "status": "CALIBRATION_CANCELLED"})

@app.route("/baseline/<pid>", methods=["GET"])
def get_personal_baseline(pid):
    mgr = PersonalBaselineManager(pid)
    return jsonify({
        "patient_id": pid,
        "has_calibrated_baseline": mgr.baseline is not None,
        "baseline": mgr.baseline
    })

@app.route("/signal/gate/reset", methods=["POST"])
def reset_signal_gate():
    live_signal_gate.reset()
    with state_lock:
        state["analysis_buffer"].clear()
        state["timestamp_buffer"].clear()
        state["last_gate_result"] = None
    return jsonify({"success": True, "message": "Signal Reliability Gate reset to baseline."})

# 4d. Hardware Telemetry & FreeRTOS Timing Integrity Endpoint
@app.route("/telemetry/integrity", methods=["GET"])
def get_telemetry_integrity():
    with state_lock:
        return jsonify({
            "device_id": state.get("last_device_id"),
            "device_boot_id": state.get("last_device_boot_id"),
            "measured_sample_rate": state.get("measured_sample_rate", 100.0),
            "timing_jitter_ms": state.get("timing_jitter_ms", 0.0),
            "sequence_gaps": state.get("sequence_gaps", 0),
            "dropped_buffers": state.get("dropped_buffers_total", 0),
            "duplicate_chunks_rejected": state.get("duplicate_chunks_rejected", 0),
            "last_sequence": state.get("last_sequence")
        })

# 4e. Explainability & Research Transparency Endpoints (Phase 1)
@app.route("/transparency/evidence_ledger", methods=["GET"])
def get_evidence_ledger():
    return jsonify({
        "status": "VALIDATED",
        "system": "CardioTwin Sentinel Cardiovascular Digital Twin",
        "evidence_ledger": {
            "sensor_type": "Reflective Photoplethysmography (MAX30102 Infrared 880nm @ 100 Hz)",
            "spo2_available": False,
            "spo2_reason": "Single-channel infrared optical sensor; clinical SpO2 requires red + IR ratiometric measurement and calibrated lookup table",
            "ecg_equivalence": "NOT EQUIVALENT (Optical volume pulse wave cannot assess QRS complexes, ST segment depression, or axis deviation)",
            "personal_baseline_calibration": "2-minute empirical calibration required; population default baselines strictly forbidden",
            "training_cohort": "PhysioNet CinC 2015 & MIMIC-III ICU monitoring cohorts (2,271 unique patients, 4,683 windows)",
            "source_bias_alert": "100% of Ventricular Tachycardia, Asystole, and Ventricular Flutter/Fib in training data originate from CinC 2015",
            "regulatory_status": "Investigational research decision-support prototype — not cleared by US FDA or India CDSCO for primary clinical diagnosis"
        }
    })

@app.route("/transparency/source_confounding", methods=["GET"])
def get_source_confounding_matrix():
    conf_path = os.path.join(ROOT_DIR, "docs", "source_confounding_audit.json")
    if os.path.exists(conf_path):
        with open(conf_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({"error": "Source confounding audit not yet generated"}), 404

@app.route("/explainability/shap", methods=["GET"])
def get_shap_explainability():
    shap_path = os.path.join(ROOT_DIR, "docs", "shap_feature_importance.json")
    if os.path.exists(shap_path):
        with open(shap_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({"error": "SHAP feature importance report not yet generated"}), 404

# 5. Scenario Injector for Demonstrations (Explicitly Provenanced as Simulation)
@app.route("/twin/scenario", methods=["POST"])
def trigger_scenario():
    data = request.get_json() or {}
    scenario = data.get("scenario", "stress_tachycardia")
    
    scenarios = {
        "stress_tachycardia": {
            "bpm": 138, "rmssd": 12.0, "sdnn": 18.0, "spo2": 95, "signal_quality": 0.90,
            "arrhythmia_predicted": "Tachycardia",
            "arrhythmia_probabilities": {"Tachycardia": 0.88, "Normal": 0.08, "Bradycardia": 0.02, "V_Tachycardia": 0.02},
            "data_source": "SIMULATION",
            "signal_gate": {
                "status": "RELIABLE",
                "reason": "Simulated telemetry passed 5-part clinical gate",
                "ai_screening_enabled": True,
                "consecutive_good_windows": 3,
                "stability_threshold": 3,
                "sample_rate_estimate": 100.0,
                "bpm": 138.0,
                "peak_coverage": 0.95,
                "rr_cv": 0.08,
                "clipping_ratio": 0.0,
                "checks": {"contact_amplitude": True, "sample_timing": True, "peak_regularity": True, "physiological_plausibility": True, "window_stability": True}
            }
        },
        "afib_episode": {
            "bpm": 118, "rmssd": 78.0, "sdnn": 84.0, "spo2": 96, "signal_quality": 0.92,
            "arrhythmia_predicted": "AFib",
            "arrhythmia_probabilities": {"AFib": 0.84, "Normal": 0.08, "Tachycardia": 0.05, "Bradycardia": 0.03},
            "data_source": "SIMULATION",
            "signal_gate": {
                "status": "RELIABLE",
                "reason": "Simulated optical pulse passed 5-part clinical gate",
                "ai_screening_enabled": True,
                "consecutive_good_windows": 3,
                "stability_threshold": 3,
                "sample_rate_estimate": 100.0,
                "bpm": 118.0,
                "peak_coverage": 0.92,
                "rr_cv": 0.22,
                "clipping_ratio": 0.0,
                "checks": {"contact_amplitude": True, "sample_timing": True, "peak_regularity": True, "physiological_plausibility": True, "window_stability": True}
            }
        },
        "hypoxia_event": {
            "bpm": 96, "rmssd": 24.0, "sdnn": 32.0, "spo2": 87, "signal_quality": 0.88,
            "arrhythmia_predicted": "Normal",
            "arrhythmia_probabilities": {"Normal": 0.80, "Tachycardia": 0.15, "Bradycardia": 0.05},
            "data_source": "SIMULATION",
            "signal_gate": {
                "status": "RELIABLE",
                "reason": "Simulated telemetry passed 5-part clinical gate",
                "ai_screening_enabled": True,
                "consecutive_good_windows": 3,
                "stability_threshold": 3,
                "sample_rate_estimate": 100.0,
                "bpm": 96.0,
                "peak_coverage": 0.94,
                "rr_cv": 0.09,
                "clipping_ratio": 0.0,
                "checks": {"contact_amplitude": True, "sample_timing": True, "peak_regularity": True, "physiological_plausibility": True, "window_stability": True}
            }
        },
        "calm_normal": {
            "bpm": 72, "rmssd": 44.0, "sdnn": 52.0, "spo2": 99, "signal_quality": 0.95,
            "arrhythmia_predicted": "Normal",
            "arrhythmia_probabilities": {"Normal": 0.96, "Tachycardia": 0.02, "Bradycardia": 0.02},
            "data_source": "SIMULATION",
            "signal_gate": {
                "status": "RELIABLE",
                "reason": "Simulated clean baseline passed 5-part clinical gate",
                "ai_screening_enabled": True,
                "consecutive_good_windows": 3,
                "stability_threshold": 3,
                "sample_rate_estimate": 100.0,
                "bpm": 72.0,
                "peak_coverage": 0.98,
                "rr_cv": 0.05,
                "clipping_ratio": 0.0,
                "checks": {"contact_amplitude": True, "sample_timing": True, "peak_regularity": True, "physiological_plausibility": True, "window_stability": True}
            }
        },
        "motion_artifact": {
            "bpm": None, "rmssd": None, "sdnn": None, "spo2": 93, "signal_quality": 0.28,
            "arrhythmia_predicted": "Verification: OPTICAL_MOTION_ARTIFACT",
            "arrhythmia_probabilities": {"OPTICAL_MOTION_ARTIFACT": 1.0},
            "data_source": "SIMULATION",
            "signal_gate": {
                "status": "OPTICAL_MOTION_ARTIFACT",
                "reason": "Optical motion artifact detected: baseline wandering and peak clipping exceed tolerances",
                "ai_screening_enabled": False,
                "consecutive_good_windows": 0,
                "stability_threshold": 3,
                "sample_rate_estimate": 100.0,
                "bpm": None,
                "peak_coverage": 0.45,
                "rr_cv": 0.40,
                "clipping_ratio": 0.08,
                "checks": {"contact_amplitude": True, "sample_timing": True, "peak_morphology": False, "optical_stability": False, "window_stability": False}
            }
        },
        "sensor_liftoff": {
            "bpm": 0, "rmssd": 0.0, "sdnn": 0.0, "spo2": 0, "signal_quality": 0.0,
            "arrhythmia_predicted": "Verification: FINGER_OFF",
            "arrhythmia_probabilities": {"FINGER_OFF": 1.0},
            "data_source": "SIMULATION",
            "signal_gate": {
                "status": "FINGER_OFF",
                "reason": "Sensor liftoff or flatline detected (amplitude below optical threshold)",
                "ai_screening_enabled": False,
                "consecutive_good_windows": 0,
                "stability_threshold": 3,
                "sample_rate_estimate": 100.0,
                "bpm": 0.0,
                "peak_coverage": 0.0,
                "rr_cv": 1.0,
                "clipping_ratio": 0.0,
                "checks": {"contact_amplitude": False, "sample_timing": True, "peak_regularity": False, "physiological_plausibility": False, "window_stability": False}
            }
        }
    }

    if scenario not in scenarios:
        return jsonify({"error": f"Unknown scenario '{scenario}'. Available: {list(scenarios.keys())}"}), 400

    sim_vitals = scenarios[scenario]
    with twin_lock:
        updated_status = active_twin.update_telemetry(sim_vitals)

    # Broadcast update
    socketio.emit("telemetry_update", updated_status)
    return jsonify({
        "success": True,
        "scenario_applied": scenario,
        "updated_status": updated_status
    })

# 6. Live Sensor Stream (ESP32 MAX30102 Chunks — accepts 'values' or 'samples')
@app.route("/data", methods=["POST"])
@app.route("/ingest_telemetry", methods=["POST"])
def receive_sensor_data():
    raw_json = request.get_json(silent=True) or {}
    ppg_chunk = raw_json.get("values") or raw_json.get("samples") or []
    # Accept device_bpm if provided, otherwise raw bpm (never fabricate)
    raw_bpm = raw_json.get("device_bpm") if "device_bpm" in raw_json else raw_json.get("bpm", None)
    raw_spo2 = raw_json.get("spo2", None)
    seq = raw_json.get("sequence", None)
    device_id = raw_json.get("device_id", None)
    boot_id = raw_json.get("device_boot_id", None)
    dropped_buffers = raw_json.get("dropped_buffers", 0)
    timing_deltas_us = raw_json.get("timing_deltas_us", [])
    first_sample_ms = raw_json.get("first_sample_ms", None)
    sample_interval_us = raw_json.get("sample_interval_us", None)

    if not ppg_chunk:
        return jsonify({"error": "No values or samples received"}), 400

    now_ts = time.time()
    now_ms = now_ts * 1000.0

    # Step 1.2: Reconstruct timestamps from device timing if available
    dt_ms = (sample_interval_us / 1000.0) if sample_interval_us else (1000.0 / TARGET_FS)

    with state_lock:
        # 1. Device reboot detection
        if boot_id is not None:
            if state["last_device_boot_id"] is not None and boot_id != state["last_device_boot_id"]:
                print(f"[WARN] Hardware reboot detected! Previous: {state['last_device_boot_id']} -> Current: {boot_id}")
                state["last_sequence"] = None
                state["status_msg"] = f"Device restarted ({boot_id})"
            state["last_device_boot_id"] = boot_id

        # 2. Duplicate / out-of-order sequence rejection
        if seq is not None and state["last_sequence"] is not None:
            if seq <= state["last_sequence"]:
                state["duplicate_chunks_rejected"] += 1
                return jsonify({
                    "status": "REJECTED_DUPLICATE_OR_OUT_OF_ORDER",
                    "sequence": seq,
                    "last_accepted_sequence": state["last_sequence"]
                }), 200

            if seq > (state["last_sequence"] + 1):
                gap = seq - (state["last_sequence"] + 1)
                state["sequence_gaps"] += gap

        if seq is not None:
            state["last_sequence"] = seq

        if device_id:
            state["last_device_id"] = device_id
        if dropped_buffers:
            state["dropped_buffers_total"] = dropped_buffers

        # 3. Calculate measured sample rate and jitter from microsecond deltas
        if timing_deltas_us and len(timing_deltas_us) >= 5:
            deltas_arr = np.array(timing_deltas_us, dtype=float)
            mean_delta_us = float(np.mean(deltas_arr))
            std_delta_us = float(np.std(deltas_arr))
            state["measured_sample_rate"] = round(1e6 / max(100.0, mean_delta_us), 1)
            state["timing_jitter_ms"] = round(std_delta_us / 1000.0, 2)

        for i, val in enumerate(ppg_chunk):
            if first_sample_ms is not None:
                sample_time_ms = first_sample_ms + i * dt_ms
            else:
                sample_time_ms = now_ms - (len(ppg_chunk) - 1 - i) * dt_ms
            state["waveform_buffer"].append(float(val))
            state["analysis_buffer"].append(float(val))
            state["timestamp_buffer"].append(sample_time_ms)
            state["sample_count"] += 1
            if state["is_recording"] and state["csv_writer"]:
                state["csv_writer"].writerow([int(sample_time_ms), int(val)])

    buf_len = len(state["analysis_buffer"])

    # Enforce full 10-second window (WINDOW_SAMPLES = 1000 at 100Hz) before inference
    if buf_len >= WINDOW_SAMPLES and (now_ts - state["last_prediction_time"] >= 2.5):
        state["last_prediction_time"] = now_ts
        sig_window = np.array(state["analysis_buffer"])
        ts_window = np.array(state["timestamp_buffer"]) if len(state["timestamp_buffer"]) == buf_len else None

        # Execute 5-Part Signal Reliability Gate
        gate_res = live_signal_gate.evaluate_window(sig_window, timestamps_ms=ts_window)
        state["last_gate_result"] = gate_res
        m = gate_res["metrics"]

        feats = extract_live_features(sig_window, fs=TARGET_FS)
        pred_label = "Normal"
        probs = {"Normal": 0.90}

        # 5-Part Gate Decision Logic:
        # If gate is NOT passed (FINGER_OFF, SENSOR_SATURATED, POOR_TIMING, POOR_CONTACT, VERIFY_SIGNAL, or STABILIZING)
        # -> Strictly block AI screening to prevent spurious critical alerts!
        if not gate_res["ai_screening_enabled"]:
            pred_label = f"Verification: {gate_res['status']}"
            probs = {gate_res["status"]: 1.0}
            dual_meta = {"pipeline_mode": f"GATED_{gate_res['status']}"}
            live_persistence_engine.reset()
            pulse_eval = live_pulse_rules.evaluate(0.0, None, signal_reliable=False)
            consensus_eval = {
                "screening_status": "GATED",
                "alert_state": "CLEAR",
                "alert_message": f"Screening Paused ({gate_res['status']})",
                "consensus_class": pred_label,
                "is_persistent": False,
                "history_summary": ["Verification"]
            }
        else:
            # Clean window -> Execute Dual-Modality Prediction (38% Classical + 62% Inception-1D)
            dual_res = dual_predictor.predict_window(sig_window, feats=feats, w_classical=0.38, w_dl=0.62)
            raw_pred_label = dual_res["predicted_label"]
            probs = dual_res["probabilities"]
            dual_meta = {
                "pipeline_mode": dual_res["pipeline_mode"],
                "confidence": dual_res["confidence"],
                "fusion_weights": dual_res["fusion_weights"]
            }

            # Layer 1: Deterministic Physiological Pulse Rules
            # Compute real pulse rate from gate or features (never fabricate)
            computed_bpm = m["bpm"] if (m and m.get("bpm", 0) > 0) else (feats["bpm"] if (feats and feats.get("bpm", 0) > 0) else 0.0)
            cal_bpm = float(raw_bpm) if (raw_bpm is not None and float(raw_bpm) > 0) else computed_bpm
            # Hardware telemetry transmits single-channel IR; do NOT fabricate SpO2
            cal_spo2 = float(raw_spo2) if (raw_spo2 is not None and float(raw_spo2) > 0) else None
            pulse_eval = live_pulse_rules.evaluate(cal_bpm, cal_spo2, signal_reliable=True)

            # Layer 2: Multi-Window Persistence Consensus Engine
            consensus_eval = live_persistence_engine.process_window(
                predicted_class=raw_pred_label,
                class_probabilities=probs,
                signal_reliable=True
            )
            # Use persistence-filtered consensus class
            pred_label = consensus_eval["consensus_class"]

        # Determine verified BPM: only real measurement or None
        computed_bpm = m["bpm"] if (m and m.get("bpm", 0) > 0) else (feats["bpm"] if (feats and feats.get("bpm", 0) > 0) else 0.0)
        live_bpm = None
        if raw_bpm is not None and float(raw_bpm) > 0:
            live_bpm = round(float(raw_bpm), 1)
        elif computed_bpm > 0:
            live_bpm = round(computed_bpm, 1)

        live_spo2 = round(float(raw_spo2), 1) if (raw_spo2 is not None and float(raw_spo2) > 0) else None
        spo2_status = "VALIDATED" if live_spo2 is not None else "UNAVAILABLE_NO_RED_CHANNEL"

        # Step 3: Compute Personalized Cardiovascular Instability (Relative to personal baseline)
        if live_baseline_manager.is_calibrating:
            calib_status = live_baseline_manager.process_calibration_window(
                bpm=live_bpm,
                rmssd=feats.get("rmssd") if feats else 35.0,
                rr_cv=m.get("rr_cv", 0.10),
                sqi=m.get("sqi", 0.85),
                is_quality_ok=gate_res["signal_quality"]["screening_allowed"]
            )
        else:
            calib_status = None

        instability_eval = live_baseline_manager.compute_instability(
            current_bpm=live_bpm,
            current_rmssd=feats.get("rmssd") if feats else None,
            current_rr_cv=m.get("rr_cv") if m else None,
            is_quality_reliable=gate_res["signal_quality"]["screening_allowed"]
        )

        # Update Digital Twin with LIVE_HARDWARE provenance, Personal Instability & Research Reframing
        telemetry_payload = {
            "bpm": live_bpm,
            "rmssd": round(feats["rmssd"], 1) if feats else None,
            "sdnn": round(feats["sdnn"], 1) if feats else None,
            "spo2": live_spo2,
            "spo2_status": spo2_status,
            "signal_quality": round(m["sqi"], 2),
            "personal_instability": instability_eval,
            "calibration_status": calib_status,
            "arrhythmia_predicted": pred_label,
            "research_waveform_pattern": pred_label,
            "research_disclaimer": "Investigational screening prototype. Optical patterns cannot substitute for 12-lead diagnostic ECG.",
            "arrhythmia_probabilities": probs,
            "data_source": "LIVE_HARDWARE",
            "device_id": state["last_device_id"],
            "sequence": state["last_sequence"],
            "sequence_gaps": state["sequence_gaps"],
            "dual_modality": dual_meta,
            "layer1_pulse_rules": pulse_eval,
            "layer2_persistence": consensus_eval,
            "physiological_observation": gate_res.get("physiological_observation"),
            "signal_gate": {
                "status": gate_res["status"],
                "reason": gate_res["reason"],
                "ai_screening_enabled": gate_res["ai_screening_enabled"],
                "screening_allowed": gate_res.get("screening_allowed", gate_res["ai_screening_enabled"]),
                "consecutive_good_windows": gate_res["consecutive_good_windows"],
                "stability_threshold": gate_res["stability_threshold"],
                "signal_quality": gate_res.get("signal_quality"),
                "physiological_observation": gate_res.get("physiological_observation"),
                "sample_rate_estimate": m["sample_rate_estimate"],
                "bpm": live_bpm,
                "peak_coverage": m["peak_coverage"],
                "rr_cv": m["rr_cv"],
                "clipping_ratio": m["clipping_ratio"],
                "checks": gate_res["checks"]
            }
        }
        with twin_lock:
            twin_status = active_twin.update_telemetry(telemetry_payload)
            if instability_eval.get("instability_score") is not None:
                active_twin.physiological_instability_score = instability_eval["instability_score"]
                active_twin.current_dynamic_risk = instability_eval["instability_score"]
                twin_status["current_dynamic_risk"] = instability_eval["instability_score"]
                twin_status["physiological_instability_score"] = instability_eval["instability_score"]
            twin_status["has_calibrated_baseline"] = live_baseline_manager.baseline is not None
            twin_status["personal_baseline"] = live_baseline_manager.baseline
            twin_status["is_calibrating"] = live_baseline_manager.is_calibrating
        
        # Broadcast full twin status to WebSocket
        socketio.emit("telemetry_update", twin_status)

    elif buf_len < WINDOW_SAMPLES:
        # Buffer filling notification
        buffering_sec = buf_len // TARGET_FS
        buffering_payload = {
            "bpm": round(float(raw_bpm), 1) if (raw_bpm is not None and float(raw_bpm) > 0) else None,
            "rmssd": None,
            "sdnn": None,
            "spo2": round(float(raw_spo2), 1) if (raw_spo2 is not None and float(raw_spo2) > 0) else None,
            "spo2_status": "UNAVAILABLE_NO_RED_CHANNEL" if raw_spo2 is None else "VALIDATED",
            "signal_quality": 0.50,
            "personal_instability": {
                "instability_score": None,
                "status_label": f"Buffering Baseline ({buffering_sec}/10s)",
                "review_recommended": False,
                "departure_flags": ["BUFFERING"]
            },
            "arrhythmia_predicted": f"Buffering ({buffering_sec}/10s)",
            "research_waveform_pattern": f"Buffering ({buffering_sec}/10s)",
            "research_disclaimer": "Investigational screening prototype. Optical patterns cannot substitute for 12-lead diagnostic ECG.",
            "arrhythmia_probabilities": {"Buffering": 1.0},
            "data_source": "LIVE_HARDWARE",
            "device_id": state["last_device_id"],
            "sequence": state["last_sequence"],
            "sequence_gaps": state["sequence_gaps"],
            "signal_gate": {
                "status": "BUFFERING",
                "reason": f"Accumulating 10-second baseline ({buffering_sec}/10s)",
                "ai_screening_enabled": False,
                "consecutive_good_windows": 0,
                "stability_threshold": 3,
                "sample_rate_estimate": 100.0,
                "bpm": 0.0,
                "peak_coverage": 0.0,
                "rr_cv": 0.0,
                "clipping_ratio": 0.0,
                "checks": {
                    "contact_amplitude": True,
                    "sample_timing": True,
                    "peak_regularity": False,
                    "physiological_plausibility": False,
                    "window_stability": False
                }
            }
        }
        with twin_lock:
            twin_status = active_twin.update_telemetry(buffering_payload)
        socketio.emit("telemetry_update", twin_status)

    # Lightweight broadcast of live waveform chunk to keep graph fluid
    socketio.emit("live_waveform", {
        "chunk": ppg_chunk[-25:],
        "bpm": raw_bpm,
        "spo2": raw_spo2,
        "data_source": "LIVE_HARDWARE"
    })

    return jsonify({
        "status": "ok",
        "last_accepted_seq": state["last_sequence"],
        "samples_received": len(ppg_chunk),
        "run": state["is_recording"]
    }), 200

# 6. Legacy/Mobile App Polling Support
@app.route("/stream", methods=["GET"])
def stream_poll():
    with state_lock:
        wave_pts = list(state["waveform_buffer"])
    with twin_lock:
        twin_st = active_twin.get_status()
    
    return jsonify({
        "waveform": wave_pts,
        "bpm": twin_st["current_vitals"]["bpm"],
        "spo2": twin_st["current_vitals"]["spo2"],
        "rmssd": twin_st["current_vitals"]["rmssd"],
        "dynamic_risk": twin_st["current_dynamic_risk"],
        "base_risk": twin_st["base_clinical_risk"],
        "prediction": twin_st["current_vitals"]["arrhythmia_predicted"],
        "status_label": twin_st["status_label"],
        "patient_name": twin_st["patient_name"],
        "recent_alerts": twin_st["recent_alerts"]
    })

@app.route("/start", methods=["POST"])
def start_session():
    with state_lock:
        if state["is_recording"]:
            return jsonify({"status": "already_running"}), 200
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ppg_session_{state['active_patient_id']}_{timestamp}.csv"
        filepath = os.path.join(CSV_DIR, filename)
        f = open(filepath, "w", newline="")
        writer = csv.writer(f)
        writer.writerow(["timestamp_ms", "ppg_value"])
        state["csv_file"] = f
        state["csv_writer"] = writer
        state["csv_path"] = filepath
        state["is_recording"] = True
        state["sample_count"] = 0
        state["status_msg"] = f"Recording started for {active_twin.name}"
    return jsonify({"status": "started", "file": filename})

@app.route("/stop", methods=["POST"])
def stop_session():
    with state_lock:
        if not state["is_recording"]:
            return jsonify({"status": "not_running"}), 200
        state["is_recording"] = False
        if state["csv_file"]:
            state["csv_file"].close()
            state["csv_file"] = None
            state["csv_writer"] = None
        state["status_msg"] = "Session stopped"
        rec_path = state["csv_path"]
    
    with twin_lock:
        final_status = active_twin.get_status()

    return jsonify({
        "status": "stopped",
        "saved_to": rec_path,
        "file": os.path.basename(rec_path) if rec_path else None,
        "final_twin_status": final_status
    })

# -------------------------------------------------------
# WEBSOCKET EVENT HANDLERS
# -------------------------------------------------------
@socketio.on("connect")
def on_connect():
    print(f"[WebSocket] Client connected: {request.sid}")
    with twin_lock:
        emit("initial_state", active_twin.get_status())

@socketio.on("disconnect")
def on_disconnect():
    print(f"[WebSocket] Client disconnected: {request.sid}")

# -------------------------------------------------------
# MAIN RUNNER
# -------------------------------------------------------
if __name__ == "__main__":
    print(f"\n=======================================================")
    print(f"  CardioTwin Backend Server running on port {PORT}")
    print(f"  Active Patient: {active_twin.name} ({active_twin.patient_id})")
    print(f"  Base CVD Risk: {active_twin.base_risk_score}% (Framingham South Asian)")
    print(f"  WebSocket Enabled: ws://localhost:{PORT}")
    print(f"=======================================================\n")
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False, allow_unsafe_werkzeug=True)
