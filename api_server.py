# ============================================================
# PPG Heart Disease Detection - Flask API Server (v3)
# New flow:
#   START  → begin collecting, open a new CSV file
#   /data  → ESP32 streams PPG chunks, saved to CSV in real time
#   STOP   → close CSV, run ML on saved data, return prediction
#   /stream → mobile app polls for live graph + prediction
# ============================================================
# pip install flask flask-cors numpy scipy joblib
# python api_server.py
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import joblib
import os
import csv
import threading
import time
from collections import deque
from datetime import datetime
from scipy.signal import find_peaks, butter, filtfilt
from scipy.stats import skew, kurtosis

# ---- Config ----
MODEL_DIR    = "./model"
CSV_DIR      = "./recordings"   # folder where session CSVs are saved
PORT         = 5000
# ----------------

app = Flask(__name__)
CORS(app)

# ---- Load Model ----
print("[INFO] Loading model...")
model         = joblib.load(os.path.join(MODEL_DIR, "ppg_model.pkl"))
label_encoder = joblib.load(os.path.join(MODEL_DIR, "label_encoder.pkl"))
feature_names = joblib.load(os.path.join(MODEL_DIR, "feature_names.pkl"))
print("[INFO] Model loaded!")

os.makedirs(CSV_DIR, exist_ok=True)

# ---- Shared State ----
state = {
    "is_running"   : False,
    "display_buf"  : deque(maxlen=200),   # for live graph only
    "prediction"   : "---",
    "confidence"   : 0.0,
    "bpm"          : 0.0,
    "alert"        : False,
    "sample_count" : 0,
    "csv_path"     : None,
    "csv_writer"   : None,
    "csv_file"     : None,
    "status_msg"   : "Ready",
}
state_lock = threading.Lock()


# -------------------------------------------------------
# Signal Processing
# -------------------------------------------------------

def bandpass_filter(signal, lowcut=0.5, highcut=5.0, fs=100, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return filtfilt(b, a, signal.astype(float))


def extract_features(signal, fs=100):
    peaks, _ = find_peaks(signal, distance=int(0.4 * fs), height=np.mean(signal))
    if len(peaks) < 2:
        return None
    rr = np.diff(peaks) / fs * 1000
    f = {}
    f['bpm']              = 60000 / np.mean(rr) if np.mean(rr) > 0 else 0
    f['rr_mean']          = np.mean(rr)
    f['rr_std']           = np.std(rr)
    f['rmssd']            = np.sqrt(np.mean(np.diff(rr) ** 2))
    f['sdnn']             = np.std(rr)
    f['pnn50']            = np.sum(np.abs(np.diff(rr)) > 50) / max(len(rr), 1) * 100
    f['rr_min']           = np.min(rr)
    f['rr_max']           = np.max(rr)
    f['rr_range']         = f['rr_max'] - f['rr_min']
    f['rr_skew']          = float(skew(rr))
    f['rr_kurt']          = float(kurtosis(rr))
    f['sig_mean']         = np.mean(signal)
    f['sig_std']          = np.std(signal)
    f['sig_skew']         = float(skew(signal))
    f['sig_kurt']         = float(kurtosis(signal))
    f['sig_min']          = np.min(signal)
    f['sig_max']          = np.max(signal)
    f['sig_range']        = f['sig_max'] - f['sig_min']
    peak_amps             = signal[peaks]
    f['peak_amp_mean']    = np.mean(peak_amps)
    f['peak_amp_std']     = np.std(peak_amps)
    f['peak_amp_cv']      = f['peak_amp_std'] / (f['peak_amp_mean'] + 1e-6)
    pulse_widths          = np.diff(peaks)
    f['pulse_width_mean'] = np.mean(pulse_widths)
    f['pulse_width_std']  = np.std(pulse_widths)
    for name in feature_names:
        if name not in f:
            f[name] = 0
    return f


def run_prediction_from_csv(csv_path):
    """
    Read saved CSV, run ML model on full signal, update state.
    Called after STOP is pressed.
    """
    try:
        with state_lock:
            state["status_msg"] = "Analysing..."

        print(f"[INFO] Running ML on {csv_path}...")

        # Read all PPG samples from CSV
        samples = []
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                samples.append(float(row["ppg_value"]))

        if len(samples) < 100:
            with state_lock:
                state["prediction"]  = "Too short"
                state["status_msg"]  = "Recording too short — try again"
            return

        signal   = np.array(samples)
        filtered = bandpass_filter(signal)
        feats    = extract_features(filtered)

        if feats is None:
            with state_lock:
                state["prediction"]  = "No peaks"
                state["status_msg"]  = "Could not detect peaks — try again"
            return

        vec        = np.array([[feats[n] for n in feature_names]])
        idx        = model.predict(vec)[0]
        label      = label_encoder.inverse_transform([idx])[0]
        probs      = model.predict_proba(vec)[0]
        confidence = float(np.max(probs))
        bpm        = round(feats.get('bpm', 0), 1)
        alert      = label != "Normal"

        with state_lock:
            state["prediction"]  = label
            state["confidence"]  = round(confidence, 4)
            state["bpm"]         = bpm
            state["alert"]       = alert
            state["status_msg"]  = f"Done — {len(samples)} samples analysed"

        print(f"[RESULT] {label} | conf: {confidence:.2f} | BPM: {bpm} | samples: {len(samples)}")

    except Exception as e:
        print(f"[ERROR] Prediction failed: {e}")
        with state_lock:
            state["status_msg"] = f"Error: {str(e)}"


# -------------------------------------------------------
# ROUTES
# -------------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "PPG Server v3 running"})


@app.route("/status", methods=["GET"])
def status():
    with state_lock:
        return jsonify({
            "is_running"   : state["is_running"],
            "prediction"   : state["prediction"],
            "confidence"   : state["confidence"],
            "bpm"          : state["bpm"],
            "alert"        : state["alert"],
            "sample_count" : state["sample_count"],
            "status_msg"   : state["status_msg"],
            "csv_path"     : state["csv_path"],
        })


@app.route("/start", methods=["POST"])
def start():
    """
    Mobile app taps START.
    Creates a new timestamped CSV file for this session.
    """
    with state_lock:
        if state["is_running"]:
            return jsonify({"error": "Already running"}), 400

        # Create new CSV file for this session
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path  = os.path.join(CSV_DIR, f"ppg_{timestamp}.csv")
        csv_file  = open(csv_path, "w", newline="")
        writer    = csv.DictWriter(csv_file, fieldnames=["timestamp_ms", "ppg_value"])
        writer.writeheader()

        state["is_running"]   = True
        state["csv_path"]     = csv_path
        state["csv_file"]     = csv_file
        state["csv_writer"]   = writer
        state["sample_count"] = 0
        state["prediction"]   = "---"
        state["confidence"]   = 0.0
        state["bpm"]          = 0.0
        state["alert"]        = False
        state["status_msg"]   = "Recording..."
        state["display_buf"].clear()

    print(f"[INFO] ▶ Started — saving to {csv_path}")
    return jsonify({"status": "started", "csv": csv_path})


@app.route("/stop", methods=["POST"])
def stop():
    """
    Mobile app taps STOP.
    Closes the CSV, then runs ML prediction on the saved file.
    """
    with state_lock:
        if not state["is_running"]:
            return jsonify({"error": "Not running"}), 400

        state["is_running"] = False
        csv_path = state["csv_path"]

        # Close CSV file
        if state["csv_file"]:
            state["csv_file"].close()
            state["csv_file"]   = None
            state["csv_writer"] = None

        state["status_msg"] = "Analysing..."

    print(f"[INFO] ■ Stopped — {state['sample_count']} samples saved to {csv_path}")

    # Run ML in background so response returns immediately
    threading.Thread(
        target=run_prediction_from_csv,
        args=(csv_path,),
        daemon=True
    ).start()

    return jsonify({
        "status"      : "stopped",
        "csv"         : csv_path,
        "sample_count": state["sample_count"],
    })


@app.route("/command", methods=["GET"])
def command():
    """ESP32 polls this every second to know whether to collect."""
    with state_lock:
        return jsonify({"run": state["is_running"]})


@app.route("/data", methods=["POST"])
def receive_data():
    """
    ESP32 sends PPG chunks here while running.
    Each sample is saved to CSV immediately.
    Body: { "samples": [val1, val2, ...] }
    """
    try:
        data    = request.get_json()
        samples = data.get("samples", [])
        if not samples:
            return jsonify({"error": "No samples"}), 400

        with state_lock:
            if not state["is_running"]:
                return jsonify({"status": "stopped"})

            t_ms = int(time.time() * 1000)
            for i, s in enumerate(samples):
                # Save to CSV
                if state["csv_writer"]:
                    state["csv_writer"].writerow({
                        "timestamp_ms": t_ms + i * 10,  # 10ms apart at 100Hz
                        "ppg_value"   : s,
                    })
                # Add to display buffer for live graph
                state["display_buf"].append(s)
                state["sample_count"] += 1

            # Flush CSV periodically so data isn't lost on crash
            if state["sample_count"] % 100 == 0 and state["csv_file"]:
                state["csv_file"].flush()

            count = state["sample_count"]

        return jsonify({"status": "ok", "total_samples": count})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/stream", methods=["GET"])
def stream():
    """Mobile app polls this for live PPG graph + prediction + status."""
    with state_lock:
        return jsonify({
            "ppg"          : list(state["display_buf"]),
            "prediction"   : state["prediction"],
            "confidence"   : state["confidence"],
            "bpm"          : state["bpm"],
            "alert"        : state["alert"],
            "is_running"   : state["is_running"],
            "sample_count" : state["sample_count"],
            "status_msg"   : state["status_msg"],
        })


@app.route("/recordings", methods=["GET"])
def list_recordings():
    """List all saved CSV recordings."""
    files = sorted(os.listdir(CSV_DIR), reverse=True)
    csvs  = [f for f in files if f.endswith(".csv")]
    return jsonify({"recordings": csvs, "count": len(csvs)})


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

if __name__ == "__main__":
    print(f"\n🚀 PPG Server v3 on port {PORT}")
    print(f"   Recordings saved to: {os.path.abspath(CSV_DIR)}")
    print(f"   Find your IP: run 'ipconfig' → IPv4 Address\n")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
