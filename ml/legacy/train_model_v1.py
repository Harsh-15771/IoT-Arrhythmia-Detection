# ============================================================
# PPG Arrhythmia Detection - Model Training
# Dataset: PhysioNet/CinC Challenge 2015
# https://physionet.org/content/challenge-2015/1.0.0/
#
# INSTALL DEPENDENCIES:
#   pip install numpy pandas scipy scikit-learn joblib matplotlib wfdb
#
# RUN:
#   python train_model.py
# ============================================================

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import wfdb

from scipy.signal import find_peaks, butter, filtfilt
from scipy.stats import skew, kurtosis

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (classification_report, confusion_matrix,
                              accuracy_score, ConfusionMatrixDisplay)
import joblib

# -------------------------------------------------------
# CONFIG — update DATASET_DIR to match your folder path
# -------------------------------------------------------
DATASET_DIR   = "./physionet_2015"   # folder with .hea and .mat files
MODEL_DIR     = "./model"
SAMPLING_RATE = 250                  # PhysioNet 2015 is 250 Hz
# -------------------------------------------------------

ALARM_LABEL_MAP = {
    "Asystole"               : "Asystole",
    "Bradycardia"            : "Bradycardia",
    "Tachycardia"            : "Tachycardia",
    "Ventricular_Tachycardia": "V_Tachycardia",
    "Ventricular_Flutter_Fib": "V_Flutter_Fib",
    # handle spaces too
    "Ventricular Tachycardia": "V_Tachycardia",
    "Ventricular Flutter/Fibrillation": "V_Flutter_Fib",
}


# -------------------------------------------------------
# STEP 1: PARSE HEA FILE MANUALLY
# wfdb strips the '#' from comments — we read raw lines
# to reliably get the alarm type and true/false label
# -------------------------------------------------------

def parse_hea(hea_path):
    """
    Read a .hea file and return:
      alarm_type  : str  e.g. "Tachycardia"
      is_true     : bool True = real alarm, False = false alarm
    """
    alarm_type  = None
    is_true     = None

    # Known alarm types in this dataset
    known_alarms = [
        "Asystole", "Bradycardia", "Tachycardia",
        "Ventricular_Tachycardia", "Ventricular_Flutter_Fib"
    ]

    try:
        with open(hea_path, 'r', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('#'):
                    continue
                content = line[1:].strip()  # remove '#'
                cl      = content.lower()

                # Format A: "#Asystole" — alarm type IS the content
                for alarm in known_alarms:
                    if content == alarm or content.replace(" ", "_") == alarm:
                        alarm_type = alarm
                        break

                # Format B: "#Alarm type: Tachycardia"
                if alarm_type is None and "alarm type" in cl:
                    parts = content.split(":", 1)
                    if len(parts) == 2:
                        alarm_type = parts[1].strip().replace(" ", "_")

                # True / False alarm
                if "true alarm" in cl:
                    is_true = True
                elif "false alarm" in cl:
                    is_true = False

    except Exception as e:
        pass

    return alarm_type, is_true


# -------------------------------------------------------
# STEP 2: LOAD DATASET
# -------------------------------------------------------

def load_dataset():
    if not os.path.exists(DATASET_DIR):
        print(f"[ERROR] Folder '{DATASET_DIR}' not found.")
        print("Rename your 'training' folder to 'physionet_2015' and try again.")
        sys.exit(1)

    hea_files = sorted([
        f[:-4] for f in os.listdir(DATASET_DIR) if f.endswith(".hea")
    ])

    if not hea_files:
        print(f"[ERROR] No .hea files found in '{DATASET_DIR}'")
        sys.exit(1)

    print(f"[INFO] Found {len(hea_files)} records")

    X_signals, y_labels = [], []
    skipped  = 0
    no_alarm = 0
    no_pleth = 0
    no_read  = 0

    for rec_name in hea_files:
        hea_path = os.path.join(DATASET_DIR, rec_name + ".hea")
        rec_path = os.path.join(DATASET_DIR, rec_name)

        # ── Parse alarm info from raw HEA file ──
        alarm_type, is_true = parse_hea(hea_path)

        if alarm_type is None:
            no_alarm += 1
            skipped  += 1
            continue

        # ── Read signal with wfdb ──
        try:
            record = wfdb.rdrecord(rec_path)
        except Exception as e:
            no_read += 1
            skipped += 1
            continue

        # ── Find PLETH (PPG) channel ──
        ppg_signal = None
        sig_names  = [s.upper() for s in record.sig_name]

        for keyword in ["PLETH", "PPG", "PULSE", "SPO2"]:
            for i, name in enumerate(sig_names):
                if keyword in name:
                    ppg_signal = record.p_signal[:, i]
                    break
            if ppg_signal is not None:
                break

        # Fallback: use last channel
        if ppg_signal is None:
            no_pleth += 1
            if record.p_signal.shape[1] > 0:
                ppg_signal = record.p_signal[:, -1]
            else:
                skipped += 1
                continue

        # Remove NaN/Inf
        ppg_signal = ppg_signal.astype(float)
        ppg_signal = ppg_signal[np.isfinite(ppg_signal)]

        if len(ppg_signal) < 500:
            skipped += 1
            continue

        # Map alarm type to clean label
        label = ALARM_LABEL_MAP.get(alarm_type, alarm_type)

        X_signals.append(ppg_signal)
        y_labels.append(label)

    print(f"[INFO] Loaded: {len(X_signals)} | Skipped: {skipped}")
    print(f"       (no alarm label: {no_alarm} | read error: {no_read} | no PLETH: {no_pleth})")

    if len(X_signals) == 0:
        print("\n[ERROR] No records loaded!")
        print("Checking first .hea file for debugging...")
        debug_hea(os.path.join(DATASET_DIR, hea_files[0] + ".hea"))
        sys.exit(1)

    # Print label distribution
    unique, counts = np.unique(y_labels, return_counts=True)
    print("[INFO] Label distribution:")
    for u, c in zip(unique, counts):
        print(f"  {u}: {c}")

    return X_signals, np.array(y_labels)


def debug_hea(hea_path):
    """Print raw contents of a HEA file for debugging."""
    print(f"\n[DEBUG] Contents of {hea_path}:")
    try:
        with open(hea_path, 'r', errors='ignore') as f:
            for i, line in enumerate(f):
                print(f"  Line {i}: {repr(line.rstrip())}")
    except Exception as e:
        print(f"  Could not read: {e}")


# -------------------------------------------------------
# STEP 3: SIGNAL PREPROCESSING
# -------------------------------------------------------

def bandpass_filter(signal, lowcut=0.5, highcut=8.0, fs=250, order=4):
    nyq  = 0.5 * fs
    low  = max(0.001, lowcut  / nyq)
    high = min(0.999, highcut / nyq)
    if low >= high:
        return signal
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)


# -------------------------------------------------------
# STEP 4: FEATURE EXTRACTION
# -------------------------------------------------------

def extract_features(signal, fs=250):
    # Use a 5-second window from the middle of the signal
    mid     = len(signal) // 2
    half    = fs * 5 // 2
    start   = max(0, mid - half)
    seg     = signal[start : start + fs * 5]

    if len(seg) < fs * 2:
        return None

    try:
        seg = bandpass_filter(seg, fs=fs)
    except Exception:
        pass

    peaks, _ = find_peaks(seg, distance=int(0.3 * fs), height=np.mean(seg))

    if len(peaks) < 2:
        return None

    rr = np.diff(peaks) / fs * 1000  # ms
    f  = {}

    f['bpm']              = 60000 / np.mean(rr) if np.mean(rr) > 0 else 0
    f['rr_mean']          = np.mean(rr)
    f['rr_std']           = np.std(rr)
    f['rmssd']            = np.sqrt(np.mean(np.diff(rr) ** 2)) if len(rr) > 1 else 0
    f['sdnn']             = np.std(rr)
    f['pnn50']            = np.sum(np.abs(np.diff(rr)) > 50) / max(len(rr), 1) * 100
    f['rr_min']           = np.min(rr)
    f['rr_max']           = np.max(rr)
    f['rr_range']         = f['rr_max'] - f['rr_min']
    f['rr_skew']          = float(skew(rr))
    f['rr_kurt']          = float(kurtosis(rr))
    f['sig_mean']         = np.mean(seg)
    f['sig_std']          = np.std(seg)
    f['sig_skew']         = float(skew(seg))
    f['sig_kurt']         = float(kurtosis(seg))
    f['sig_min']          = np.min(seg)
    f['sig_max']          = np.max(seg)
    f['sig_range']        = f['sig_max'] - f['sig_min']
    peak_amps             = seg[peaks]
    f['peak_amp_mean']    = np.mean(peak_amps)
    f['peak_amp_std']     = np.std(peak_amps)
    f['peak_amp_cv']      = f['peak_amp_std'] / (f['peak_amp_mean'] + 1e-6)
    pulse_widths          = np.diff(peaks)
    f['pulse_width_mean'] = np.mean(pulse_widths)
    f['pulse_width_std']  = np.std(pulse_widths)

    return f


def extract_all_features(X_signals, fs=250):
    print("[INFO] Extracting features...")
    records, valid_idx = [], []
    for i, sig in enumerate(X_signals):
        if i % 100 == 0:
            print(f"  {i}/{len(X_signals)}...")
        feats = extract_features(sig.astype(float), fs=fs)
        if feats is not None:
            records.append(feats)
            valid_idx.append(i)
    df = pd.DataFrame(records).fillna(0)
    print(f"[INFO] Valid: {len(df)}/{len(X_signals)}")
    return df, valid_idx


# -------------------------------------------------------
# STEP 5: TRAIN MODEL
# -------------------------------------------------------

def train_model(X_features, y_encoded, label_encoder):
    X_train, X_test, y_train, y_test = train_test_split(
        X_features, y_encoded,
        test_size=0.2, random_state=42, stratify=y_encoded
    )
    print(f"[INFO] Train: {len(X_train)} | Test: {len(X_test)}")
    print("[INFO] Training Random Forest...")

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_split=3,
        random_state=42,
        n_jobs=-1,
        class_weight='balanced'
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc    = accuracy_score(y_test, y_pred)
    print(f"\n✅ Test Accuracy: {acc * 100:.2f}%\n")
    print(classification_report(y_test, y_pred, target_names=label_encoder.classes_))

    os.makedirs(MODEL_DIR, exist_ok=True)

    cm   = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(cm, display_labels=label_encoder.classes_)
    fig, ax = plt.subplots(figsize=(8, 6))
    disp.plot(ax=ax, cmap='Blues', colorbar=False)
    plt.title(f"Confusion Matrix  |  Accuracy: {acc*100:.1f}%")
    plt.tight_layout()
    plt.savefig(os.path.join(MODEL_DIR, "confusion_matrix.png"), dpi=150)
    print("[INFO] Saved confusion_matrix.png")

    feat_imp = pd.Series(model.feature_importances_, index=X_features.columns)
    feat_imp.nlargest(12).sort_values().plot(kind='barh', figsize=(7, 5), color='steelblue')
    plt.title("Top 12 Most Important Features")
    plt.xlabel("Importance")
    plt.tight_layout()
    plt.savefig(os.path.join(MODEL_DIR, "feature_importance.png"), dpi=150)
    print("[INFO] Saved feature_importance.png")

    return model


# -------------------------------------------------------
# STEP 6: SAVE MODEL
# -------------------------------------------------------

def save_model(model, label_encoder, feature_names):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model,         os.path.join(MODEL_DIR, "ppg_model.pkl"))
    joblib.dump(label_encoder, os.path.join(MODEL_DIR, "label_encoder.pkl"))
    joblib.dump(feature_names, os.path.join(MODEL_DIR, "feature_names.pkl"))
    print(f"\n💾 Model saved to '{MODEL_DIR}/'")


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

if __name__ == "__main__":
    print("=" * 55)
    print("  PPG Arrhythmia Detection — PhysioNet 2015")
    print("=" * 55)

    X_signals, y_raw      = load_dataset()
    X_features, valid_idx = extract_all_features(X_signals, fs=SAMPLING_RATE)
    y_valid               = y_raw[valid_idx]

    le    = LabelEncoder()
    y_enc = le.fit_transform(y_valid)
    print(f"[INFO] Final classes: {le.classes_}")
    dist  = {c: int((y_enc == i).sum()) for i, c in enumerate(le.classes_)}
    print(f"[INFO] Distribution: {dist}")

    model = train_model(X_features, y_enc, le)
    save_model(model, le, list(X_features.columns))

    print("\n✅ Training complete! Now run api_server.py.")