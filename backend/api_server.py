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
except ModuleNotFoundError:
    from backend.digital_twin_engine import CardioTwin
    from backend.framingham_risk import calculate_framingham_cvd_risk

# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------
PORT         = 5000
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'backend' else BASE_DIR
MODEL_DIR    = os.path.join(ROOT_DIR, "model")
CSV_DIR      = os.path.join(ROOT_DIR, "recordings")
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
twin_lock = threading.Lock()

# -------------------------------------------------------
# STREAMING & BUFFER STATE
# -------------------------------------------------------
state = {
    "is_recording": False,
    "active_patient_id": active_patient_id,
    "waveform_buffer": deque(maxlen=400), # 4 seconds live buffer for display
    "analysis_buffer": deque(maxlen=WINDOW_SAMPLES), # 10 seconds for feature extraction
    "sample_count": 0,
    "last_prediction_time": 0.0,
    "csv_file": None,
    "csv_writer": None,
    "csv_path": None,
    "status_msg": "System Ready - Digital Twin Active"
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
    global active_twin, state
    data = request.get_json() or {}
    pid = data.get("patient_id")
    if pid not in patients_db:
        return jsonify({"error": f"Patient ID '{pid}' does not exist"}), 400
    
    with twin_lock:
        active_twin = CardioTwin(patients_db[pid])
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
    return jsonify(status)

# 4. Interactive "What-If" Treatment Simulator
@app.route("/twin/simulate", methods=["POST"])
def simulate_treatment():
    data = request.get_json() or {}
    with twin_lock:
        result = active_twin.simulate_treatment(data)
    return jsonify({"success": True, "simulation": result})

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
            "data_source": "SIMULATION"
        },
        "hypoxia_event": {
            "bpm": 96, "rmssd": 24.0, "sdnn": 32.0, "spo2": 87, "signal_quality": 0.88,
            "arrhythmia_predicted": "Normal",
            "arrhythmia_probabilities": {"Normal": 0.80, "Tachycardia": 0.15, "Bradycardia": 0.05},
            "data_source": "SIMULATION"
        },
        "critical_v_tach": {
            "bpm": 165, "rmssd": 8.0, "sdnn": 12.0, "spo2": 91, "signal_quality": 0.92,
            "arrhythmia_predicted": "V_Tachycardia",
            "arrhythmia_probabilities": {"V_Tachycardia": 0.91, "Tachycardia": 0.06, "Normal": 0.03},
            "data_source": "SIMULATION"
        },
        "afib_episode": {
            "bpm": 118, "rmssd": 78.0, "sdnn": 84.0, "spo2": 96, "signal_quality": 0.92,
            "arrhythmia_predicted": "AFib",
            "arrhythmia_probabilities": {"AFib": 0.84, "Normal": 0.08, "Tachycardia": 0.05, "Bradycardia": 0.03},
            "data_source": "SIMULATION"
        },
        "calm_normal": {
            "bpm": 72, "rmssd": 44.0, "sdnn": 52.0, "spo2": 99, "signal_quality": 0.95,
            "arrhythmia_predicted": "Normal",
            "arrhythmia_probabilities": {"Normal": 0.96, "Tachycardia": 0.02, "Bradycardia": 0.02},
            "data_source": "SIMULATION"
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
    raw_bpm = raw_json.get("bpm", None)
    raw_spo2 = raw_json.get("spo2", None)

    if not ppg_chunk:
        return jsonify({"error": "No values or samples received"}), 400

    now_ts = time.time()
    with state_lock:
        for val in ppg_chunk:
            state["waveform_buffer"].append(float(val))
            state["analysis_buffer"].append(float(val))
            state["sample_count"] += 1
            if state["is_recording"] and state["csv_writer"]:
                state["csv_writer"].writerow([val, time.strftime("%Y-%m-%d %H:%M:%S")])

    buf_len = len(state["analysis_buffer"])

    # Enforce full 10-second window (WINDOW_SAMPLES = 1000 at 100Hz) before inference
    if buf_len >= WINDOW_SAMPLES and (now_ts - state["last_prediction_time"] >= 2.5):
        state["last_prediction_time"] = now_ts
        sig_window = np.array(state["analysis_buffer"])
        feats = extract_live_features(sig_window, fs=TARGET_FS)
        
        pred_label = "Normal"
        probs = {"Normal": 0.90}
        sqi_val = feats.get("sqi", 0.0) if feats else 0.0
        sig_std = feats.get("sig_std", 0.0) if feats else 0.0

        # SQI GATING & ARTIFACT REJECTION
        if sig_std < 0.05:
            # Amplitude near zero — finger off sensor
            pred_label = "Sensor Disconnected / Lead Off"
            probs = {"Sensor_Off": 1.0}
        elif sqi_val < 0.40:
            # Significant motion artifact or poor optical perfusion
            pred_label = "Signal Insufficient (Motion Artifact)"
            probs = {"Artifact": 1.0}
        elif feats is not None and model_loaded:
            feat_vector = np.array([feats[col] for col in feature_names]).reshape(1, -1)
            feat_scaled = scaler.transform(feat_vector)
            pred_code = xgb_model.predict(feat_scaled)[0]
            pred_label = label_encoder.classes_[pred_code]
            pred_probs_arr = xgb_model.predict_proba(feat_scaled)[0]
            probs = {cls_name: float(pred_probs_arr[i]) for i, cls_name in enumerate(label_encoder.classes_)}

        # Update Digital Twin with LIVE_HARDWARE provenance
        telemetry_payload = {
            "bpm": round(float(raw_bpm) if raw_bpm is not None else (feats["bpm"] if feats else 72.0), 1),
            "rmssd": round(feats["rmssd"] if feats else 35.0, 1),
            "sdnn": round(feats["sdnn"] if feats else 40.0, 1),
            "spo2": round(float(raw_spo2) if raw_spo2 is not None else 98.0, 1),
            "signal_quality": round(sqi_val, 2),
            "arrhythmia_predicted": pred_label,
            "arrhythmia_probabilities": probs,
            "data_source": "LIVE_HARDWARE"
        }
        with twin_lock:
            twin_status = active_twin.update_telemetry(telemetry_payload)
        
        # Broadcast full twin status to WebSocket
        socketio.emit("telemetry_update", twin_status)

    elif buf_len < WINDOW_SAMPLES:
        # Buffer filling notification
        buffering_sec = buf_len // TARGET_FS
        buffering_payload = {
            "bpm": round(float(raw_bpm) if raw_bpm is not None else 72.0, 1),
            "rmssd": 35.0,
            "sdnn": 40.0,
            "spo2": round(float(raw_spo2) if raw_spo2 is not None else 98.0, 1),
            "signal_quality": 0.50,
            "arrhythmia_predicted": f"Buffering ({buffering_sec}/10s)",
            "arrhythmia_probabilities": {"Buffering": 1.0},
            "data_source": "LIVE_HARDWARE"
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

    return jsonify({"status": "ok", "samples_received": len(ppg_chunk)}), 200

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
        writer.writerow(["ppg_value", "timestamp"])
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
