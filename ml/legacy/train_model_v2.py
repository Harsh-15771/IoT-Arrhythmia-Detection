# ============================================================
# [LEGACY v2 ARCHIVE - DEPRECATED]
# CardioTwin v2 - Preliminary 6-Class PhysioNet 2015 Model (354 records)
#
# NOTE: This script is preserved for historical baseline reproduction only.
# The authoritative production model is CardioTwin v3 (8 classes, 2,271 patients,
# 4,683 windows) produced by `ml/train_unified_models.py` using the unified
# multi-modal dataset (MIMIC-III + BUT PPG + CinC 2015 + BIDMC).
# ============================================================

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import wfdb

from scipy.signal import find_peaks, butter, filtfilt, resample, welch
from scipy.stats import skew, kurtosis

from sklearn.model_selection import StratifiedGroupKFold, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, ConfusionMatrixDisplay, roc_curve, auc,
    f1_score, precision_score, recall_score
)
from xgboost import XGBClassifier
import joblib

# -------------------------------------------------------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'ml' else BASE_DIR
DATASET_DIR  = os.path.join(ROOT_DIR, "data", "raw", "physionet_2015")
if not os.path.exists(DATASET_DIR):
    DATASET_DIR = os.path.join(ROOT_DIR, "physionet_2015")
MODEL_DIR    = os.path.join(ROOT_DIR, "model")
ORIGINAL_FS   = 250        # PhysioNet 2015 native sampling rate
TARGET_FS     = 100        # Standardized to 100 Hz (matches ESP32 MAX30102!)
WINDOW_SEC    = 10         # 10-second analysis window (1000 samples at 100Hz)
WINDOW_SAMPLES = TARGET_FS * WINDOW_SEC
OVERLAP_RATIO = 0.5        # 50% overlap for window augmentation

ALARM_MAP = {
    "Asystole"               : "Asystole",
    "Bradycardia"            : "Bradycardia",
    "Tachycardia"            : "Tachycardia",
    "Ventricular_Tachycardia": "V_Tachycardia",
    "Ventricular_Flutter_Fib": "V_Flutter_Fib",
    "Ventricular Tachycardia": "V_Tachycardia",
    "Ventricular Flutter/Fibrillation": "V_Flutter_Fib",
}

# -------------------------------------------------------
# STEP 1: PARSE HEA & ALARMS
# -------------------------------------------------------
def parse_alarm_file(dataset_dir):
    """Parse ground truth labels and true/false alarm flags."""
    alarm_info = {}
    alarms_path = os.path.join(dataset_dir, "ALARMS")
    if os.path.exists(alarms_path):
        with open(alarms_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) == 3:
                    rec_name, alarm_type, is_true = parts[0], parts[1], int(parts[2])
                    alarm_info[rec_name] = (alarm_type, is_true)
    return alarm_info

# -------------------------------------------------------
# STEP 2: SIGNAL PREPROCESSING
# -------------------------------------------------------
def bandpass_filter(signal, lowcut=0.5, highcut=8.0, fs=100, order=4):
    """4th order Butterworth bandpass filter to eliminate baseline wander and high-frequency noise."""
    nyq = 0.5 * fs
    low = max(0.001, lowcut / nyq)
    high = min(0.999, highcut / nyq)
    if low >= high:
        return signal
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)

def resample_signal(signal, orig_fs=250, target_fs=100):
    """Resample PPG signal from native rate to target 100 Hz."""
    if orig_fs == target_fs or len(signal) == 0:
        return signal
    num_samples = int(len(signal) * target_fs / orig_fs)
    return resample(signal, num_samples)

# -------------------------------------------------------
# STEP 3: FEATURE EXTRACTION (26 RICH BIOMARKERS)
# -------------------------------------------------------
def extract_features(window, fs=100):
    """
    Extract 26 time-domain, frequency-domain, and morphological features
    from a 10-second standardized 100 Hz PPG window.
    Handles flatlines/asystole gracefully.
    """
    if len(window) < fs * 3:
        return None
    
    # Clean filter
    try:
        filtered = bandpass_filter(window, fs=fs)
    except Exception:
        filtered = window

    # Signal amplitude stats
    std_val = float(np.std(filtered))
    mean_val = float(np.mean(filtered))
    f = {}

    # Check for Asystole / Flatline (extremely low amplitude variance)
    if std_val < 0.05:
        f['bpm']              = 0.0
        f['rr_mean']          = 0.0
        f['rr_std']           = 0.0
        f['rmssd']            = 0.0
        f['sdnn']             = 0.0
        f['pnn50']            = 0.0
        f['pnn20']            = 0.0
        f['rr_min']           = 0.0
        f['rr_max']           = 0.0
        f['rr_range']         = 0.0
        f['rr_cv']            = 0.0
        f['rr_skew']          = 0.0
        f['rr_kurt']          = 0.0
        f['sig_mean']         = mean_val
        f['sig_std']          = std_val
        f['sig_skew']         = 0.0
        f['sig_kurt']         = 0.0
        f['sig_energy']       = float(np.mean(filtered ** 2))
        f['peak_amp_mean']    = 0.0
        f['peak_amp_std']     = 0.0
        f['peak_amp_cv']      = 0.0
        f['pulse_width_mean'] = 0.0
        f['pulse_width_std']  = 0.0
        f['lf_power']         = 0.0
        f['hf_power']         = 0.0
        f['lf_hf_ratio']      = 0.0
        f['sqi']              = 0.0
        return f

    # Normalize amplitude
    norm_sig = (filtered - mean_val) / std_val

    # Detect systolic peaks
    peaks, _ = find_peaks(norm_sig, distance=int(0.30 * fs), prominence=0.25)
    
    # If fewer than 2 peaks detected, treat as severe bradycardia/asystole
    if len(peaks) < 2:
        f['bpm']              = float(len(peaks) * 6) # e.g. 1 peak in 10s = 6 bpm
        f['rr_mean']          = 10000.0
        f['rr_std']           = 0.0
        f['rmssd']            = 0.0
        f['sdnn']             = 0.0
        f['pnn50']            = 0.0
        f['pnn20']            = 0.0
        f['rr_min']           = 10000.0
        f['rr_max']           = 10000.0
        f['rr_range']         = 0.0
        f['rr_cv']            = 0.0
        f['rr_skew']          = 0.0
        f['rr_kurt']          = 0.0
        f['sig_mean']         = float(np.mean(norm_sig))
        f['sig_std']          = float(np.std(norm_sig))
        f['sig_skew']         = float(skew(norm_sig))
        f['sig_kurt']         = float(kurtosis(norm_sig))
        f['sig_energy']       = float(np.mean(norm_sig ** 2))
        f['peak_amp_mean']    = float(np.mean(norm_sig[peaks])) if len(peaks) > 0 else 0.0
        f['peak_amp_std']     = 0.0
        f['peak_amp_cv']      = 0.0
        f['pulse_width_mean'] = 0.0
        f['pulse_width_std']  = 0.0
        f['lf_power']         = 0.0
        f['hf_power']         = 0.0
        f['lf_hf_ratio']      = 0.0
        f['sqi']              = 0.1
        return f

    # Calculate RR intervals in milliseconds
    rr = np.diff(peaks) / fs * 1000.0  # ms
    diff_rr = np.diff(rr) if len(rr) > 1 else np.array([0.0])

    # 1. Time-Domain HRV Metrics
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

    # 2. Waveform Morphology & Statistical Metrics
    f['sig_mean']         = float(np.mean(norm_sig))
    f['sig_std']          = float(np.std(norm_sig))
    f['sig_skew']         = float(skew(norm_sig))
    f['sig_kurt']         = float(kurtosis(norm_sig))
    f['sig_energy']       = float(np.mean(norm_sig ** 2))
    
    peak_amps = norm_sig[peaks]
    f['peak_amp_mean']    = float(np.mean(peak_amps))
    f['peak_amp_std']     = float(np.std(peak_amps))
    f['peak_amp_cv']      = float(f['peak_amp_std'] / (abs(f['peak_amp_mean']) + 1e-6))
    
    pulse_widths = np.diff(peaks) / fs * 1000.0
    f['pulse_width_mean'] = float(np.mean(pulse_widths))
    f['pulse_width_std']  = float(np.std(pulse_widths))

    # 3. Frequency-Domain HRV (Welch Power Spectral Density)
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

    # 4. Signal Quality Index (SQI)
    f['sqi'] = float(max(0.0, min(1.0, (abs(f['sig_kurt']) / 6.0) * (1.0 / (f['peak_amp_cv'] + 0.5)))))
    return f

# -------------------------------------------------------
# STEP 4: LOAD & WINDOW DATASETS (PhysioNet + BIDMC)
# -------------------------------------------------------
def load_and_process_dataset():
    print(f"[INFO] Scanning PhysioNet 2015 from '{DATASET_DIR}'...")
    alarm_info = parse_alarm_file(DATASET_DIR)
    hea_files = sorted([f[:-4] for f in os.listdir(DATASET_DIR) if f.endswith(".hea")])
    
    all_features   = []
    all_labels     = []
    all_record_ids = []
    manifest       = []
    rec_count      = 0
    skipped        = 0

    for rec_name in hea_files:
        if rec_name not in alarm_info:
            continue
        
        # Check if .mat file is downloaded
        mat_path = os.path.join(DATASET_DIR, rec_name + ".mat")
        if not os.path.exists(mat_path):
            skipped += 1
            continue

        alarm_type, is_true = alarm_info[rec_name]
        label = "Normal" if is_true == 0 else ALARM_MAP.get(alarm_type, alarm_type)

        rec_path = os.path.join(DATASET_DIR, rec_name)
        try:
            record = wfdb.rdrecord(rec_path)
        except Exception:
            skipped += 1
            continue

        # Locate PLETH / PPG channel
        ppg_signal = None
        sig_names  = [s.upper() for s in record.sig_name]
        for kw in ["PLETH", "PPG", "PULSE", "SPO2"]:
            for i, name in enumerate(sig_names):
                if kw in name:
                    ppg_signal = record.p_signal[:, i]
                    break
            if ppg_signal is not None:
                break
        
        if ppg_signal is None:
            skipped += 1
            continue

        ppg_signal = ppg_signal.astype(float)
        ppg_signal = ppg_signal[np.isfinite(ppg_signal)]
        if len(ppg_signal) < ORIGINAL_FS * 5:
            skipped += 1
            continue

        # Standardize to 100 Hz
        sig_100hz = resample_signal(ppg_signal, orig_fs=ORIGINAL_FS, target_fs=TARGET_FS)
        
        # Dynamic per-class window sampling for balanced representation
        if label == "Normal":
            step = int(WINDOW_SAMPLES * 0.7)
            max_windows = 5
        elif label == "Tachycardia":
            step = int(WINDOW_SAMPLES * 0.7)
            max_windows = 5
        elif label == "V_Tachycardia":
            step = int(WINDOW_SAMPLES * 0.5)
            max_windows = 8
        elif label == "Bradycardia":
            step = int(WINDOW_SAMPLES * 0.4)
            max_windows = 10
        elif label == "Asystole":
            step = int(WINDOW_SAMPLES * 0.3)
            max_windows = 15
        elif label == "V_Flutter_Fib":
            step = int(WINDOW_SAMPLES * 0.2)
            max_windows = 25
        else:
            step = int(WINDOW_SAMPLES * 0.5)
            max_windows = 6
        
        extracted_for_rec = 0
        for start_idx in range(0, len(sig_100hz) - WINDOW_SAMPLES + 1, step):
            window = sig_100hz[start_idx : start_idx + WINDOW_SAMPLES]
            feats = extract_features(window, fs=TARGET_FS)
            if feats is not None:
                all_features.append(feats)
                all_labels.append(label)
                all_record_ids.append(rec_name)
                extracted_for_rec += 1
                if extracted_for_rec >= max_windows:
                    break
        
        if extracted_for_rec > 0:
            manifest.append({
                "record_id": rec_name,
                "source": "PhysioNet / CinC Challenge 2015",
                "ground_truth_label": label,
                "alarm_type": alarm_type,
                "is_true_alarm": is_true,
                "native_fs": ORIGINAL_FS,
                "target_fs": TARGET_FS,
                "windows_extracted": extracted_for_rec,
                "license": "PhysioNet Open Research / Contributor License"
            })
            rec_count += 1

    print(f"[INFO] Processed {rec_count} PhysioNet records.")

    # Ingest BIDMC PPG Dataset as additional clean Normal baseline
    bidmc_dir = "bidmc_ppg"
    if not os.path.exists(bidmc_dir):
        bidmc_dir = os.path.join(ROOT_DIR, "bidmc_ppg")
    
    bidmc_recs_processed = 0
    if os.path.exists(bidmc_dir):
        bidmc_heas = sorted([f[:-4] for f in os.listdir(bidmc_dir) if f.endswith(".hea")])
        for b_name in bidmc_heas:
            b_dat = os.path.join(bidmc_dir, f"{b_name}.dat")
            if not os.path.exists(b_dat):
                continue
            try:
                b_rec = wfdb.rdrecord(os.path.join(bidmc_dir, b_name))
                b_pleth = None
                for i, s_name in enumerate(b_rec.sig_name):
                    if "PLETH" in s_name.upper():
                        b_pleth = b_rec.p_signal[:, i]
                        break
                if b_pleth is not None:
                    b_pleth = b_pleth.astype(float)
                    b_pleth = b_pleth[np.isfinite(b_pleth)]
                    b_100hz = resample_signal(b_pleth, orig_fs=b_rec.fs, target_fs=TARGET_FS)
                    mid = len(b_100hz) // 3
                    b_extracted = 0
                    for w_i in range(6):
                        s_idx = mid + (w_i * WINDOW_SAMPLES)
                        if s_idx + WINDOW_SAMPLES <= len(b_100hz):
                            b_win = b_100hz[s_idx : s_idx + WINDOW_SAMPLES]
                            b_feats = extract_features(b_win, fs=TARGET_FS)
                            if b_feats is not None:
                                all_features.append(b_feats)
                                all_labels.append("Normal")
                                all_record_ids.append(b_name)
                                b_extracted += 1
                    if b_extracted > 0:
                        manifest.append({
                            "record_id": b_name,
                            "source": "BIDMC PPG and Respiration Dataset",
                            "ground_truth_label": "Normal",
                            "alarm_type": "None",
                            "is_true_alarm": 0,
                            "native_fs": b_rec.fs,
                            "target_fs": TARGET_FS,
                            "windows_extracted": b_extracted,
                            "license": "ODC Public Domain Dedication and License"
                        })
                        bidmc_recs_processed += 1
            except Exception:
                continue

    if bidmc_recs_processed > 0:
        print(f"[INFO] Ingested {bidmc_recs_processed} clean BIDMC baseline recordings.")

    df_features = pd.DataFrame(all_features).fillna(0)
    labels = np.array(all_labels)
    record_ids = np.array(all_record_ids)

    unique, counts = np.unique(labels, return_counts=True)
    print("\n[INFO] Class Distribution in Windowed Dataset:")
    for u, c in zip(unique, counts):
        pct = (c / len(labels)) * 100.0
        print(f"  {u:25s}: {c:5d} ({pct:5.1f}%)")

    # Save dataset manifest
    manifest_path = os.path.join(ROOT_DIR, "data", "dataset_manifest.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump({
            "total_records": len(manifest),
            "total_windows": len(labels),
            "classes": sorted(list(unique)),
            "records": manifest
        }, f, indent=2)
    print(f"[INFO] Saved dataset manifest to '{manifest_path}'. Total records: {len(manifest)}, total windows: {len(labels)}")

    return df_features, labels, record_ids, manifest

# -------------------------------------------------------
# STEP 5: LEAK-FREE RECORD-LEVEL GROUPED EVALUATION & TRAINING
# -------------------------------------------------------
def train_and_evaluate(df_features, labels, record_ids, manifest):
    le = LabelEncoder()
    y_encoded = le.fit_transform(labels)
    feature_names = list(df_features.columns)
    X_raw = df_features.values

    print("\n" + "=" * 65)
    print("  RIGOROUS RECORD-LEVEL GROUPED CROSS-VALIDATION (5 FOLDS)")
    print("  Ensures ZERO patient/record data leakage between train & test")
    print("=" * 65)

    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    
    cv_accuracies = []
    cv_macro_f1s = []
    cv_weighted_f1s = []

    primary_artifacts = {}

    for fold_idx, (train_idx, test_idx) in enumerate(sgkf.split(X_raw, y_encoded, groups=record_ids)):
        train_records = set(record_ids[train_idx])
        test_records = set(record_ids[test_idx])
        overlap = train_records.intersection(test_records)
        assert len(overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping records: {overlap}"

        # Train-only scaler fitting (leak-free!)
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_raw[train_idx])
        X_test = scaler.transform(X_raw[test_idx])
        y_train = y_encoded[train_idx]
        y_test = y_encoded[test_idx]

        sample_weights = compute_sample_weight('balanced', y_train)

        xgb = XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            eval_metric='mlogloss',
            n_jobs=-1
        )
        xgb.fit(X_train, y_train, sample_weight=sample_weights)

        y_pred = xgb.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        macro_f1 = f1_score(y_test, y_pred, average='macro', zero_division=0)
        weighted_f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

        cv_accuracies.append(acc)
        cv_macro_f1s.append(macro_f1)
        cv_weighted_f1s.append(weighted_f1)

        print(f"  Fold {fold_idx + 1}/5: Records Train={len(train_records)}, Test={len(test_records)} | "
              f"Windows Train={len(train_idx)}, Test={len(test_idx)} | "
              f"Acc={acc*100:.2f}%, Macro-F1={macro_f1:.4f}, Weighted-F1={weighted_f1:.4f}")

        # Track fold 0 as canonical held-out reference for reproducible evaluation artifacts
        if fold_idx == 0:
            primary_artifacts = {
                "xgb_model": xgb,
                "scaler": scaler,
                "X_test": X_test,
                "y_test": y_test,
                "y_pred": y_pred,
                "acc": acc,
                "macro_f1": macro_f1,
                "weighted_f1": weighted_f1,
                "train_records": list(train_records),
                "test_records": list(test_records)
            }

    mean_acc = float(np.mean(cv_accuracies))
    std_acc = float(np.std(cv_accuracies))
    mean_macro_f1 = float(np.mean(cv_macro_f1s))
    std_macro_f1 = float(np.std(cv_macro_f1s))
    mean_weighted_f1 = float(np.mean(cv_weighted_f1s))
    std_weighted_f1 = float(np.std(cv_weighted_f1s))
    ci_95_f1 = [round(mean_macro_f1 - 1.96 * (std_macro_f1 / np.sqrt(5)), 4),
                round(mean_macro_f1 + 1.96 * (std_macro_f1 / np.sqrt(5)), 4)]

    print("\n" + "=" * 65)
    print(f"  5-FOLD RECORD-LEVEL GROUPED EVALUATION SUMMARY:")
    print(f"  Mean Accuracy:       {mean_acc*100:.2f}% ± {std_acc*100:.2f}%")
    print(f"  Mean Macro-F1:       {mean_macro_f1:.4f} ± {std_macro_f1:.4f}")
    print(f"  Mean Weighted-F1:    {mean_weighted_f1:.4f} ± {std_weighted_f1:.4f}")
    print(f"  95% CI (Macro-F1):   [{ci_95_f1[0]}, {ci_95_f1[1]}]")
    print("=" * 65 + "\n")

    # Primary Held-out test evaluation report
    y_test_primary = primary_artifacts["y_test"]
    y_pred_primary = primary_artifacts["y_pred"]
    primary_acc = primary_artifacts["acc"]
    primary_macro_f1 = primary_artifacts["macro_f1"]
    
    print(f"--- Held-out Test Set Classification Report (Fold 1) ---")
    rep = classification_report(y_test_primary, y_pred_primary, target_names=le.classes_, output_dict=True)
    print(classification_report(y_test_primary, y_pred_primary, target_names=le.classes_))

    # Save artifacts
    LEGACY_DIR = os.path.join(MODEL_DIR, "legacy_v2")
    os.makedirs(LEGACY_DIR, exist_ok=True)

    # 1. Confusion Matrix
    cm = confusion_matrix(y_test_primary, y_pred_primary)
    fig, ax = plt.subplots(figsize=(9, 7))
    disp = ConfusionMatrixDisplay(cm, display_labels=le.classes_)
    disp.plot(ax=ax, cmap='Blues', colorbar=False, values_format='d')
    plt.title(f"CardioTwin [LEGACY v2] Record-Grouped Confusion Matrix\nHeld-Out Test Accuracy: {primary_acc*100:.1f}% | Macro-F1: {primary_macro_f1:.3f}", fontsize=11, fontweight='bold')
    plt.xticks(rotation=25, ha='right')
    plt.tight_layout()
    cm_path = os.path.join(LEGACY_DIR, "confusion_matrix_v2.png")
    plt.savefig(cm_path, dpi=200)
    plt.close()
    print(f"[INFO] Saved legacy confusion matrix to '{cm_path}'")

    # 2. Top Feature Importances

    feat_imp = pd.Series(primary_artifacts["xgb_model"].feature_importances_, index=feature_names)
    fig, ax = plt.subplots(figsize=(9, 6))
    feat_imp.nlargest(15).sort_values().plot(kind='barh', ax=ax, color='#1E88E5')
    plt.title("CardioTwin [LEGACY v2] - Top 15 Biomarkers (354 records)", fontsize=12, fontweight='bold')
    plt.xlabel("Relative Importance Score", fontsize=10)
    plt.tight_layout()
    feat_path = os.path.join(LEGACY_DIR, "feature_importance_v2.png")
    plt.savefig(feat_path, dpi=200)
    plt.close()
    print(f"[INFO] Saved legacy feature importances to '{feat_path}'")

    # 3. Save Model Files into legacy_v2/ directory
    joblib.dump(primary_artifacts["xgb_model"], os.path.join(LEGACY_DIR, "xgboost_ppg_model_v2.pkl"))
    joblib.dump(primary_artifacts["scaler"], os.path.join(LEGACY_DIR, "scaler_v2.pkl"))
    joblib.dump(le, os.path.join(LEGACY_DIR, "label_encoder_v2.pkl"))
    joblib.dump(feature_names, os.path.join(LEGACY_DIR, "feature_names_v2.pkl"))

    # 4. Model Metadata JSON with Legacy Archival Tag
    metadata = {
        "model_name": "CardioTwin_MultiClass_XGBoost_v2_Legacy",
        "version": "2.0.0-legacy-archive",
        "status": "Legacy Research Benchmark (Superseded by v3 8-class 2,271 patients)",
        "model_type": "XGBoost",
        "evaluation_protocol": "Record-Level Grouped 5-Fold Stratified Cross-Validation (Disjoint Patients, Leak-Free)",
        "leak_free_verification": "Zero overlap between patient record IDs in train and test sets. Preprocessing StandardScaler fitted strictly on training partition.",
        "target_fs": TARGET_FS,
        "window_sec": WINDOW_SEC,
        "total_records": len(set(record_ids)),
        "total_windows": len(labels),
        "held_out_test_accuracy": float(primary_acc),
        "held_out_test_macro_f1": float(primary_macro_f1),
        "held_out_test_weighted_f1": float(primary_artifacts["weighted_f1"]),
        "cv_5fold_accuracy_mean": mean_acc,
        "cv_5fold_accuracy_std": std_acc,
        "cv_5fold_macro_f1_mean": mean_macro_f1,
        "cv_5fold_macro_f1_std": std_macro_f1,
        "cv_5fold_weighted_f1_mean": mean_weighted_f1,
        "cv_5fold_weighted_f1_std": std_weighted_f1,
        "ci_95_macro_f1": ci_95_f1,
        "classes": list(le.classes_),
        "num_features": len(feature_names),
        "features": feature_names,
        "class_counts": {c: int(np.sum(labels == c)) for c in le.classes_},
        "per_class_metrics": {c: rep[c] for c in le.classes_ if c in rep},
        "intended_use": "Historical baseline reproduction only. Superseded by v3 (8 classes, 2,271 patients).",
        "limitations": "Model trained on PhysioNet CinC 2015 and BIDMC clinical ICU PPG; exhibits domain shift on raw MAX30102 consumer optical sensors without signal-quality gating (SQI >= 0.40)."
    }
    with open(os.path.join(LEGACY_DIR, "model_metadata_v2.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[INFO] All legacy v2 artifacts safely saved to '{LEGACY_DIR}/'. (v3 artifacts untouched)")
    return primary_artifacts["xgb_model"], primary_acc

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
if __name__ == "__main__":
    print("=" * 65)
    print("  [LEGACY ARCHIVE] CardioTwin v2 ML Pipeline (354 records)")
    print("  NOTE: Authoritative model is v3 (2,271 patients, 8 classes).")
    print("  See `ml/train_unified_models.py` or `scripts/run_v3_pipeline.py`.")
    print("=" * 65)
    df_features, labels, record_ids, manifest = load_and_process_dataset()
    train_and_evaluate(df_features, labels, record_ids, manifest)
