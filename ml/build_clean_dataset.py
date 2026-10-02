"""
CardioTwin - Unified Multi-Modal Dataset Pipeline
Integrates:
  1. BUT PPG v2.0 (3,888 expert-verified optical smartphone recordings)
  2. PhysioNet CinC 2015 True Alarms (Clinical ICU Arrhythmias: VT, VFib, Brady, Tachy, Asystole)
  3. BIDMC PPG (53 hospital ICU patients)
  4. MIMIC-III-Ext-PPG (Clinical ICU telemetry & 1,000+ patient cohort)

Standardizes all signals to 100 Hz (matching ESP32 MAX30102 hardware) and extracts
26 rich morphological, frequency-domain (Welch PSD), and time-domain biomarkers.
Evaluates using leak-free StratifiedGroupKFold on patient IDs.
"""

import os
import sys
import json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, butter, filtfilt, resample, welch
from scipy.stats import skew, kurtosis
try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kw: x
import wfdb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'ml' else BASE_DIR

RAW_DATA_DIR = os.path.join(ROOT_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(ROOT_DIR, "data", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

TARGET_FS = 100        # Standardized to 100 Hz (matches ESP32 MAX30102)
WINDOW_SEC = 10        # 10-second analysis window
WINDOW_SAMPLES = TARGET_FS * WINDOW_SEC # 1000 samples

ALARM_MAP = {
    "Asystole"               : "Asystole",
    "Bradycardia"            : "Bradycardia",
    "Tachycardia"            : "Tachycardia",
    "Ventricular_Tachycardia": "V_Tachycardia",
    "Ventricular_Flutter_Fib": "V_Flutter_Fib",
    "Ventricular Tachycardia": "V_Tachycardia",
    "Ventricular Flutter/Fibrillation": "V_Flutter_Fib",
}

# -------------------------------------------------------------
# SIGNAL FILTERING & RESAMPLING
# -------------------------------------------------------------
def bandpass_filter(signal, lowcut=0.5, highcut=8.0, fs=100, order=4):
    """4th-order Butterworth bandpass filter to eliminate baseline wander and high-frequency noise."""
    nyq = 0.5 * fs
    low = max(0.001, lowcut / nyq)
    high = min(0.999, highcut / nyq)
    if low >= high:
        return signal
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)

def resample_signal(signal, orig_fs, target_fs=100):
    """Resample any native PPG frequency to standardized 100 Hz."""
    if orig_fs == target_fs or len(signal) == 0:
        return signal
    num_samples = int(len(signal) * target_fs / orig_fs)
    return resample(signal, num_samples)

# -------------------------------------------------------------
# 26-BIOMARKER EXTRACTION
# -------------------------------------------------------------
def extract_features(window, fs=100):
    """Extract 26 time, frequency, and morphological biomarkers from a 10s 100Hz PPG window."""
    if len(window) < fs * 3:
        return None
    try:
        filtered = bandpass_filter(window, fs=fs)
    except Exception:
        filtered = window

    std_val = float(np.std(filtered))
    mean_val = float(np.mean(filtered))
    f = {}

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

    norm_sig = (filtered - mean_val) / std_val
    peaks, _ = find_peaks(norm_sig, distance=int(0.30 * fs), prominence=0.25)

    if len(peaks) < 2:
        f['bpm']              = float(len(peaks) * 6)
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

    rr = np.diff(peaks) / fs * 1000.0
    diff_rr = np.diff(rr) if len(rr) > 1 else np.array([0.0])

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

    peak_amps = norm_sig[peaks]
    f['peak_amp_mean']    = float(np.mean(peak_amps))
    f['peak_amp_std']     = float(np.std(peak_amps))
    f['peak_amp_cv']      = float(f['peak_amp_std'] / (abs(f['peak_amp_mean']) + 1e-6))

    pulse_widths = np.diff(peaks) / fs * 1000.0
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

# -------------------------------------------------------------
# 1. INGEST BUT PPG v2.0 (Wearable Robustness)
# -------------------------------------------------------------
def load_but_ppg():
    print("\n[INGEST 1/4] Loading BUT PPG v2.0 dataset (Wearable Baseline)...")
    but_base = os.path.join(RAW_DATA_DIR, "but_ppg", "brno-university-of-technology-smartphone-ppg-database-but-ppg-2.0.0")
    if not os.path.exists(but_base):
        print(f"[WARN] BUT PPG directory not found at: {but_base}")
        return [], [], [], []

    ann_csv = os.path.join(but_base, "quality-hr-ann.csv")
    quality_map = {}
    if os.path.exists(ann_csv):
        df_ann = pd.read_csv(ann_csv)
        for _, r in df_ann.iterrows():
            quality_map[str(r['ID'])] = int(r['Quality'])

    features, labels, patient_ids, waveforms = [], [], [], []
    folders = sorted([f for f in os.listdir(but_base) if os.path.isdir(os.path.join(but_base, f))])

    # Sample balanced set of clean normal recordings
    clean_count = 0
    for fld in tqdm(folders, desc="Ingesting BUT PPG"):
        q = quality_map.get(fld, 1)
        if q != 1:
            continue # Ingest expert-verified clean Normal baseline

        rec_path = os.path.join(but_base, fld, f"{fld}_PPG")
        if not os.path.exists(f"{rec_path}.hea"):
            continue

        try:
            rec = wfdb.rdrecord(rec_path, physical=True)
            sig_raw = rec.p_signal.flatten().astype(float)
            sig_raw = sig_raw[np.isfinite(sig_raw)]
            if len(sig_raw) < 150: # at 30 Hz = 5s
                continue

            sig_100 = resample_signal(sig_raw, orig_fs=rec.fs, target_fs=TARGET_FS)
            if len(sig_100) >= WINDOW_SAMPLES:
                win = sig_100[:WINDOW_SAMPLES]
                feats = extract_features(win, fs=TARGET_FS)
                if feats and feats['sqi'] >= 0.40:
                    features.append(feats)
                    labels.append("Normal")
                    patient_ids.append(f"BUT_{fld[:3]}") # Group by subject ID prefix

                    std_w = np.std(win)
                    norm_w = (win - np.mean(win)) / std_w if std_w > 1e-4 else np.zeros_like(win)
                    waveforms.append(norm_w)
                    clean_count += 1
                    if clean_count >= 1500: # Robust normal baseline
                        break
        except Exception:
            continue

    print(f"  -> Ingested {len(features)} clean Normal segments across {len(set(patient_ids))} subjects.")
    return features, labels, patient_ids, waveforms

# -------------------------------------------------------------
# 2. INGEST PHYSIONET CINC 2015 (Clinical ICU Alarms)
# -------------------------------------------------------------
def load_physionet_2015():
    print("\n[INGEST 2/4] Loading PhysioNet CinC 2015 dataset (Critical Arrhythmias)...")
    dataset_dir = os.path.join(RAW_DATA_DIR, "physionet_2015")
    if not os.path.exists(dataset_dir):
        print(f"[WARN] PhysioNet 2015 directory not found at: {dataset_dir}")
        return [], [], [], []

    alarm_file = os.path.join(dataset_dir, "ALARMS")
    alarm_info = {}
    if os.path.exists(alarm_file):
        with open(alarm_file, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 3:
                    alarm_info[parts[0]] = (parts[1], int(parts[2]))

    features, labels, patient_ids, waveforms = [], [], [], []
    hea_files = sorted([f[:-4] for f in os.listdir(dataset_dir) if f.endswith(".hea")])

    for rec_name in tqdm(hea_files, desc="Ingesting CinC 2015"):
        if rec_name not in alarm_info:
            continue
        mat_path = os.path.join(dataset_dir, f"{rec_name}.mat")
        if not os.path.exists(mat_path):
            continue

        alarm_type, is_true = alarm_info[rec_name]
        # Skip false alarms from arrhythmia training to avoid poisoning!
        if is_true == 0:
            continue
        label = ALARM_MAP.get(alarm_type, alarm_type)

        try:
            rec = wfdb.rdrecord(os.path.join(dataset_dir, rec_name))
            ppg = None
            for i, name in enumerate(rec.sig_name):
                if any(kw in name.upper() for kw in ["PLETH", "PPG", "PULSE", "SPO2"]):
                    ppg = rec.p_signal[:, i]
                    break
            if ppg is None: continue
            ppg = ppg.astype(float)
            ppg = ppg[np.isfinite(ppg)]
            if len(ppg) < rec.fs * 5: continue

            sig_100 = resample_signal(ppg, orig_fs=rec.fs, target_fs=TARGET_FS)
            step = int(WINDOW_SAMPLES * 0.5)
            max_w = 6 if label in ("Tachycardia", "Bradycardia") else 12

            w_count = 0
            for start in range(0, len(sig_100) - WINDOW_SAMPLES + 1, step):
                win = sig_100[start : start + WINDOW_SAMPLES]
                feats = extract_features(win, fs=TARGET_FS)
                if feats is not None:
                    features.append(feats)
                    labels.append(label)
                    patient_ids.append(f"CinC_{rec_name}")

                    std_w = np.std(win)
                    norm_w = (win - np.mean(win)) / std_w if std_w > 1e-4 else np.zeros_like(win)
                    waveforms.append(norm_w)
                    w_count += 1
                    if w_count >= max_w:
                        break
        except Exception:
            continue

    print(f"  -> Ingested {len(features)} verified true arrhythmia segments across {len(set(patient_ids))} ICU records.")
    return features, labels, patient_ids, waveforms

# -------------------------------------------------------------
# 3. INGEST BIDMC PPG (Hospital ICU Baseline)
# -------------------------------------------------------------
def load_bidmc():
    print("\n[INGEST 3/4] Loading BIDMC PPG dataset (Hospital ICU Baseline)...")
    bidmc_dir = os.path.join(RAW_DATA_DIR, "bidmc_ppg")
    if not os.path.exists(bidmc_dir):
        print(f"[WARN] BIDMC directory not found at: {bidmc_dir}")
        return [], [], [], []

    features, labels, patient_ids, waveforms = [], [], [], []
    hea_files = sorted([f[:-4] for f in os.listdir(bidmc_dir) if f.endswith(".hea")])

    for b_name in tqdm(hea_files, desc="Ingesting BIDMC"):
        dat_path = os.path.join(bidmc_dir, f"{b_name}.dat")
        if not os.path.exists(dat_path): continue

        try:
            rec = wfdb.rdrecord(os.path.join(bidmc_dir, b_name))
            ppg = None
            for i, s in enumerate(rec.sig_name):
                if "PLETH" in s.upper():
                    ppg = rec.p_signal[:, i]
                    break
            if ppg is None: continue
            ppg = ppg.astype(float)
            ppg = ppg[np.isfinite(ppg)]

            sig_100 = resample_signal(ppg, orig_fs=rec.fs, target_fs=TARGET_FS)
            mid = len(sig_100) // 3
            for w_i in range(5):
                start = mid + (w_i * WINDOW_SAMPLES)
                if start + WINDOW_SAMPLES <= len(sig_100):
                    win = sig_100[start : start + WINDOW_SAMPLES]
                    feats = extract_features(win, fs=TARGET_FS)
                    if feats and feats['sqi'] >= 0.50:
                        features.append(feats)
                        labels.append("Normal")
                        patient_ids.append(f"BIDMC_{b_name}")

                        std_w = np.std(win)
                        norm_w = (win - np.mean(win)) / std_w if std_w > 1e-4 else np.zeros_like(win)
                        waveforms.append(norm_w)
        except Exception:
            continue

    print(f"  -> Ingested {len(features)} clean hospital segments across {len(set(patient_ids))} patients.")
    return features, labels, patient_ids, waveforms

# -------------------------------------------------------------
# 4. INGEST MIMIC-III-Ext-PPG (Primary Clinical Waveforms)
# -------------------------------------------------------------
MIMIC_RHYTHM_MAP = {
    'AF': 'AFib',
    'SBRAD': 'Bradycardia',
    'STACH': 'Tachycardia',
    'SVTACH': 'Tachycardia',
    'SR': 'Normal',
    '1AVB': 'Cardiac_Paced',
    'VPACE': 'Cardiac_Paced',
    'AVPACE': 'Cardiac_Paced',
    'APACE': 'Cardiac_Paced',
    'AFLT': 'Cardiac_Paced',
}

def load_mimic():
    print("\n[INGEST 4/4] Loading MIMIC-III-Ext-PPG dataset...")
    mimic_dir = os.path.join(RAW_DATA_DIR, "mimic_ppg")
    features, labels, patient_ids, waveforms = [], [], [], []

    # Priority 1: Check for the verified 2,000-patient balanced cohort!
    balanced_csv = os.path.join(mimic_dir, "mimic_2000_balanced_cohort.csv")
    wf_dir = os.path.join(mimic_dir, "mimic_waveforms")

    if os.path.exists(balanced_csv) and os.path.exists(wf_dir):
        print(f"  -> [+] Found Verified 2,000-Patient Balanced Cohort at {balanced_csv}!")
        df_cohort = pd.read_csv(balanced_csv)
        print(f"  -> Scanning {len(df_cohort):,} waveform records in {wf_dir}...")

        success_count = 0
        for _, row in tqdm(df_cohort.iterrows(), total=len(df_cohort), desc="Ingesting 2,000 MIMIC Patients"):
            sig_name = str(row['signal_file_name'])
            rhythm = str(row['event_rhythm'])
            pid = str(row['patient'])
            label = MIMIC_RHYTHM_MAP.get(rhythm, 'Normal')

            rec_path = os.path.join(wf_dir, sig_name)
            if not os.path.exists(f"{rec_path}.hea") or not os.path.exists(f"{rec_path}.dat"):
                continue

            try:
                rec = wfdb.rdrecord(rec_path)
                ppg = None
                for i, s in enumerate(rec.sig_name):
                    if any(k in s.upper() for k in ["PLETH", "PPG", "PULSE", "SPO2"]):
                        ppg = rec.p_signal[:, i]
                        break
                if ppg is None:
                    continue
                ppg = ppg.astype(float)
                ppg = ppg[np.isfinite(ppg)]
                if len(ppg) < rec.fs * 5:
                    continue

                sig_100 = resample_signal(ppg, orig_fs=rec.fs, target_fs=TARGET_FS)
                # Take central 10-second window
                start = max(0, (len(sig_100) - WINDOW_SAMPLES) // 2)
                win = sig_100[start : start + WINDOW_SAMPLES]
                if len(win) == WINDOW_SAMPLES:
                    feats = extract_features(win, fs=TARGET_FS)
                    if feats:
                        features.append(feats)
                        labels.append(label)
                        patient_ids.append(f"MIMIC_{pid}")

                        std_w = np.std(win)
                        norm_w = (win - np.mean(win)) / std_w if std_w > 1e-4 else np.zeros_like(win)
                        waveforms.append(norm_w)
                        success_count += 1
            except Exception:
                continue

        print(f"  -> Successfully ingested {success_count:,} real clinical MIMIC patients across {len(set(patient_ids))} unique IDs.")
        return features, labels, patient_ids, waveforms

    # Check if user has generated the Colab 1,000+ patient export package!
    colab_csv = os.path.join(mimic_dir, "mimic_1000_features.csv")
    colab_npz = os.path.join(mimic_dir, "mimic_1000_waveforms.npz")

    if os.path.exists(colab_csv):
        print(f"  -> [+] Found Colab 1,000+ Patient Export at {colab_csv}!")
        df_colab = pd.read_csv(colab_csv)
        for _, row in df_colab.iterrows():
            f_dict = row.to_dict()
            lbl = str(f_dict.get('label', 'Normal'))
            pid = str(f_dict.get('patient_id', 'MIMIC_P'))
            features.append(f_dict)
            labels.append(lbl)
            patient_ids.append(f"MIMIC_{pid}")

        if os.path.exists(colab_npz):
            npz_data = np.load(colab_npz)
            waveforms.extend(list(npz_data['X']))
        print(f"  -> Successfully loaded {len(features)} MIMIC clinical windows from Colab export.")
        return features, labels, patient_ids, waveforms

    # Fallback to loading local WFDB files in mimic_dir
    hea_files = sorted([f[:-4] for f in os.listdir(mimic_dir) if f.endswith(".hea")])
    if len(hea_files) == 0:
        print("  -> No local MIMIC files yet (run Colab notebook ml/MIMIC_1000_Cohort_Extractor.ipynb to download).")
        return [], [], [], []

    for seg_name in tqdm(hea_files, desc="Ingesting local MIMIC"):
        dat_path = os.path.join(mimic_dir, f"{seg_name}.dat")
        if not os.path.exists(dat_path): continue

        try:
            rec = wfdb.rdrecord(os.path.join(mimic_dir, seg_name))
            ppg = None
            for i, s in enumerate(rec.sig_name):
                if "PLETH" in s.upper() or "PPG" in s.upper():
                    ppg = rec.p_signal[:, i]
                    break
            if ppg is None: continue
            ppg = ppg.astype(float)
            ppg = ppg[np.isfinite(ppg)]

            sig_100 = resample_signal(ppg, orig_fs=rec.fs, target_fs=TARGET_FS)
            for start in range(0, len(sig_100) - WINDOW_SAMPLES + 1, WINDOW_SAMPLES):
                win = sig_100[start : start + WINDOW_SAMPLES]
                feats = extract_features(win, fs=TARGET_FS)
                if feats:
                    features.append(feats)
                    labels.append("Normal")
                    patient_ids.append(f"MIMIC_{seg_name.split('_')[0]}")

                    std_w = np.std(win)
                    norm_w = (win - np.mean(win)) / std_w if std_w > 1e-4 else np.zeros_like(win)
                    waveforms.append(norm_w)
        except Exception:
            continue

    print(f"  -> Ingested {len(features)} local MIMIC segments.")
    return features, labels, patient_ids, waveforms

# -------------------------------------------------------------
# MAIN COMPILATION
# -------------------------------------------------------------
def build_dataset():
    print("=" * 60)
    print("CARDIOTWIN - UNIFIED DATASET BUILDER")
    print("=" * 60)

    f_but, l_but, p_but, w_but = load_but_ppg()
    f_cinc, l_cinc, p_cinc, w_cinc = load_physionet_2015()
    f_bidmc, l_bidmc, p_bidmc, w_bidmc = load_bidmc()
    f_mimic, l_mimic, p_mimic, w_mimic = load_mimic()

    all_features = f_but + f_cinc + f_bidmc + f_mimic
    all_labels = l_but + l_cinc + l_bidmc + l_mimic
    all_patients = p_but + p_cinc + p_bidmc + p_mimic
    all_waveforms = w_but + w_cinc + w_bidmc + w_mimic

    print("\n" + "=" * 60)
    print("DATASET AGGREGATION SUMMARY")
    print("=" * 60)
    print(f"Total 10s Windows: {len(all_labels):,}")
    print(f"Unique Patient IDs: {len(set(all_patients)):,}")

    df_feats = pd.DataFrame(all_features).fillna(0)
    # Remove metadata columns if present in dict
    clean_cols = [c for c in df_feats.columns if c not in ['record_id', 'patient_id', 'label']]
    df_clean_feats = df_feats[clean_cols]

    labels_arr = np.array(all_labels)
    patients_arr = np.array(all_patients)
    waveforms_arr = np.array(all_waveforms, dtype=np.float32).reshape(-1, WINDOW_SAMPLES, 1)

    unique, counts = np.unique(labels_arr, return_counts=True)
    print("\nClass Distribution:")
    for u, c in zip(unique, counts):
        pct = (c / len(labels_arr)) * 100.0
        print(f"  {u:25s}: {c:5d} ({pct:5.1f}%)")

    # Save compiled dataset
    out_npz = os.path.join(PROCESSED_DIR, "unified_multimodal_dataset.npz")
    np.savez_compressed(
        out_npz,
        X_features=df_clean_feats.values,
        feature_names=clean_cols,
        X_waveforms=waveforms_arr,
        y=labels_arr,
        patient_ids=patients_arr
    )
    print(f"\n[SUCCESS] Saved unified dataset to: {out_npz} ({os.path.getsize(out_npz)/(1024*1024):.1f} MB)")

if __name__ == "__main__":
    build_dataset()
