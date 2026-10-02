"""
CardioTwin - 1D-CNN Google Colab Exporter
Prepares:
  1. A standalone Google Colab Notebook (CardioTwin_1D_CNN_Colab.ipynb)
     for training deep learning models on GPU (T4 on free tier).
  2. A data export script that packages 100Hz PPG segments into an .npz file
     ready for drag-and-drop into Google Drive / Colab.
"""

import os
import json

def create_colab_notebook(output_path="CardioTwin_1D_CNN_Colab.ipynb"):
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# 🫀 CardioTwin — 1D-CNN Arrhythmia Classification on Raw PPG\n",
                    "### Digital Twin Challenge 2026 (Happiest Health)\n",
                    "\n",
                    "This notebook trains a **1-Dimensional Convolutional Neural Network (1D-CNN)** directly on **raw 100 Hz PPG waveform segments** (1000 samples per window, normalized).\n",
                    "\n",
                    "**Hardware Acceleration:** Make sure to select **Runtime → Change runtime type → T4 GPU** in Google Colab.\n",
                    "\n",
                    "**Safety Net Note:** Our XGBoost model is already trained and shipping. This deep learning model is an upgrade candidate targeting **85-92% accuracy**."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# 1. Environment & Dependencies\n",
                    "!pip install -q wfdb scikit-learn matplotlib seaborn\n",
                    "import numpy as np\n",
                    "import matplotlib.pyplot as plt\n",
                    "import tensorflow as tf\n",
                    "from tensorflow.keras import layers, models, callbacks\n",
                    "from sklearn.model_selection import train_test_split\n",
                    "from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay\n",
                    "\n",
                    "print('TensorFlow Version:', tf.__version__)\n",
                    "print('GPU Available:', tf.config.list_physical_devices('GPU'))"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 2. Load or Download Preprocessed 100 Hz PPG Segments\n",
                    "You can upload `ppg_100hz_dataset.npz` directly to the Colab files panel on the left, or download from your repository."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Load preprocessed segments\n",
                    "try:\n",
                    "    data = np.load('ppg_100hz_dataset.npz')\n",
                    "    X = data['X'] # Shape: (N, 1000, 1)\n",
                    "    y = data['y'] # Integer labels (0 to num_classes-1)\n",
                    "    classes = data['classes']\n",
                    "    print(f'Loaded dataset: {X.shape[0]} windows, {X.shape[1]} samples each.')\n",
                    "    print('Classes:', classes)\n",
                    "except Exception as e:\n",
                    "    print('Please upload ppg_100hz_dataset.npz to the Colab files tab on the left.')\n",
                    "    print('Error:', e)"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 3. 1D-CNN Deep Learning Architecture\n",
                    "Designed specifically for photoplethysmography (PPG):\n",
                    "- Wide initial receptive field (kernel 15) to capture morphological dicrotic notch and systolic peak.\n",
                    "- Batch normalization after each conv block for fast gradient flow.\n",
                    "- Global Average Pooling to prevent spatial overfitting and maintain rotational invariance."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "def build_1d_cnn(input_shape=(1000, 1), num_classes=6):\n",
                    "    inputs = layers.Input(shape=input_shape)\n",
                    "    \n",
                    "    # Block 1\n",
                    "    x = layers.Conv1D(32, kernel_size=15, padding='same', activation='relu')(inputs)\n",
                    "    x = layers.BatchNormalization()(x)\n",
                    "    x = layers.MaxPooling1D(pool_size=2)(x)\n",
                    "    x = layers.Dropout(0.2)(x)\n",
                    "    \n",
                    "    # Block 2\n",
                    "    x = layers.Conv1D(64, kernel_size=11, padding='same', activation='relu')(x)\n",
                    "    x = layers.BatchNormalization()(x)\n",
                    "    x = layers.MaxPooling1D(pool_size=2)(x)\n",
                    "    x = layers.Dropout(0.2)(x)\n",
                    "    \n",
                    "    # Block 3\n",
                    "    x = layers.Conv1D(128, kernel_size=7, padding='same', activation='relu')(x)\n",
                    "    x = layers.BatchNormalization()(x)\n",
                    "    x = layers.MaxPooling1D(pool_size=2)(x)\n",
                    "    x = layers.Dropout(0.3)(x)\n",
                    "    \n",
                    "    # Global Average Pooling\n",
                    "    x = layers.GlobalAveragePooling1D()(x)\n",
                    "    x = layers.Dense(64, activation='relu')(x)\n",
                    "    x = layers.Dropout(0.3)(x)\n",
                    "    outputs = layers.Dense(num_classes, activation='softmax')(x)\n",
                    "    \n",
                    "    model = models.Model(inputs=inputs, outputs=outputs, name='CardioTwin_1DCNN')\n",
                    "    model.compile(\n",
                    "        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),\n",
                    "        loss='sparse_categorical_crossentropy',\n",
                    "        metrics=['accuracy']\n",
                    "    )\n",
                    "    return model\n",
                    "\n",
                    "model = build_1d_cnn(input_shape=(1000, 1), num_classes=len(classes))\n",
                    "model.summary()"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 4. Train with Early Stopping & Learning Rate Reduction"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# Train / Test split\n",
                    "X_train, X_test, y_train, y_test = train_test_split(\n",
                    "    X, y, test_size=0.20, random_state=42, stratify=y\n",
                    ")\n",
                    "\n",
                    "cb_list = [\n",
                    "    callbacks.EarlyStopping(monitor='val_loss', patience=8, restore_best_weights=True),\n",
                    "    callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, min_lr=1e-6)\n",
                    "]\n",
                    "\n",
                    "history = model.fit(\n",
                    "    X_train, y_train,\n",
                    "    validation_data=(X_test, y_test),\n",
                    "    epochs=35,\n",
                    "    batch_size=32,\n",
                    "    callbacks=cb_list\n",
                    ")"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 5. Model Evaluation & Confusion Matrix"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "y_pred_probs = model.predict(X_test)\n",
                    "y_pred = np.argmax(y_pred_probs, axis=1)\n",
                    "\n",
                    "print('=== CLASSIFICATION REPORT ===')\n",
                    "print(classification_report(y_test, y_pred, target_names=classes))\n",
                    "\n",
                    "cm = confusion_matrix(y_test, y_pred)\n",
                    "fig, ax = plt.subplots(figsize=(8, 6))\n",
                    "disp = ConfusionMatrixDisplay(cm, display_labels=classes)\n",
                    "disp.plot(ax=ax, cmap='Blues', colorbar=False)\n",
                    "plt.title('CardioTwin 1D-CNN Confusion Matrix')\n",
                    "plt.tight_layout()\n",
                    "plt.savefig('confusion_matrix_1dcnn.png', dpi=200)\n",
                    "plt.show()"
                ]
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## 6. Export Trained Model for CardioTwin Backend Integration"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "model.save('cardiotwin_1dcnn.keras')\n",
                    "print('Saved trained 1D-CNN to cardiotwin_1dcnn.keras!')\n",
                    "# Download to your local machine\n",
                    "from google.colab import files\n",
                    "files.download('cardiotwin_1dcnn.keras')"
                ]
            }
        ],
        "metadata": {
            "accelerator": "GPU",
            "colab": {
                "gpuType": "T4",
                "provenance": []
            },
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }
    
    with open(output_path, "w") as f:
        json.dump(notebook, f, indent=2)
    print(f"Generated Google Colab Notebook at '{output_path}'.")

def package_npz_dataset(output_npz="ppg_100hz_dataset.npz"):
    import numpy as np
    import wfdb
    from scipy.signal import resample
    from train_model_v2 import parse_alarm_file, resample_signal, DATASET_DIR, ORIGINAL_FS, TARGET_FS, WINDOW_SAMPLES, ALARM_MAP

    print(f"[INFO] Packaging raw 100Hz PPG segments into '{output_npz}' for Google Colab...")
    alarm_info = parse_alarm_file(DATASET_DIR)
    hea_files = sorted([f[:-4] for f in os.listdir(DATASET_DIR) if f.endswith(".hea")])

    windows_list = []
    labels_list = []

    for rec_name in hea_files:
        if rec_name not in alarm_info:
            continue
        mat_path = os.path.join(DATASET_DIR, rec_name + ".mat")
        if not os.path.exists(mat_path):
            continue

        alarm_type, is_true = alarm_info[rec_name]
        label = "Normal" if is_true == 0 else ALARM_MAP.get(alarm_type, alarm_type)

        try:
            record = wfdb.rdrecord(os.path.join(DATASET_DIR, rec_name))
            ppg = None
            for i, name in enumerate(record.sig_name):
                if any(kw in name.upper() for kw in ["PLETH", "PPG", "PULSE", "SPO2"]):
                    ppg = record.p_signal[:, i]
                    break
            if ppg is None:
                continue

            ppg = ppg.astype(float)
            ppg = ppg[np.isfinite(ppg)]
            if len(ppg) < ORIGINAL_FS * 5:
                continue

            # Standardize to 100 Hz
            sig_100 = resample_signal(ppg, orig_fs=ORIGINAL_FS, target_fs=TARGET_FS)
            
            # Step and count per class
            step = int(WINDOW_SAMPLES * 0.5)
            max_w = 6 if label in ("Normal", "Tachycardia") else 12

            w_count = 0
            for s_idx in range(0, len(sig_100) - WINDOW_SAMPLES + 1, step):
                win = sig_100[s_idx : s_idx + WINDOW_SAMPLES]
                # Z-score normalize window
                std_w = np.std(win)
                if std_w > 1e-4:
                    norm_win = (win - np.mean(win)) / std_w
                else:
                    norm_win = np.zeros_like(win)

                windows_list.append(norm_win)
                labels_list.append(label)
                w_count += 1
                if w_count >= max_w:
                    break
        except Exception:
            continue

    # Also ingest BIDMC
    bidmc_dir = "bidmc_ppg"
    if os.path.exists(bidmc_dir):
        for b_name in sorted([f[:-4] for f in os.listdir(bidmc_dir) if f.endswith(".hea")]):
            b_dat = os.path.join(bidmc_dir, f"{b_name}.dat")
            if not os.path.exists(b_dat): continue
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
                    b_100 = resample_signal(b_pleth, orig_fs=b_rec.fs, target_fs=TARGET_FS)
                    mid = len(b_100) // 3
                    for w_i in range(5):
                        s_idx = mid + (w_i * WINDOW_SAMPLES)
                        if s_idx + WINDOW_SAMPLES <= len(b_100):
                            w = b_100[s_idx : s_idx + WINDOW_SAMPLES]
                            std_w = np.std(w)
                            norm_w = (w - np.mean(w)) / std_w if std_w > 1e-4 else np.zeros_like(w)
                            windows_list.append(norm_w)
                            labels_list.append("Normal")
            except Exception:
                continue

    classes = sorted(list(set(labels_list)))
    class_to_idx = {c: i for i, c in enumerate(classes)}
    y_idx = np.array([class_to_idx[l] for l in labels_list], dtype=np.int32)
    X_arr = np.array(windows_list, dtype=np.float32).reshape(-1, WINDOW_SAMPLES, 1)

    np.savez_compressed(output_npz, X=X_arr, y=y_idx, classes=classes)
    print(f"[SUCCESS] Saved {X_arr.shape[0]} windows to '{output_npz}' (Size: {os.path.getsize(output_npz) / (1024*1024):.2f} MB).")
    print(f"Classes: {classes}")

if __name__ == "__main__":
    create_colab_notebook()
    package_npz_dataset()
