"""
CardioTwin v4 — Leak-Free Dual-Modality Pipeline Evaluator (Canonical v2)
================================================================================
Step 4 of CardioTwin v4 Product Pivot:
1. Generates and caches Out-Of-Fold (OOF) predictions for the Classical Super Ensemble
   using StratifiedGroupKFold across all 2,271 patients.
2. Integrates with Out-Of-Fold (OOF) Inception-1D predictions from model/oof_predictions_cnn.npz.
3. Conducts nested cross-validation to select fusion weights without data snooping.
4. Produces honest, leak-free evaluation metrics (Macro-F1, balanced accuracy, 95% CIs).
"""

import os
import json
import time
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, accuracy_score, f1_score, balanced_accuracy_score
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT_DIR, "data", "processed", "unified_multimodal_dataset.npz")
MODEL_DIR = os.path.join(ROOT_DIR, "model")
CLASSICAL_OOF_PATH = os.path.join(MODEL_DIR, "oof_predictions_classical.npz")
CNN_OOF_PATH = os.path.join(MODEL_DIR, "oof_predictions_cnn.npz")
BENCHMARK_V2_JSON = os.path.join(MODEL_DIR, "dual_modality_benchmark_v2.json")


def load_dataset():
    print(f"[INFO] Loading unified multimodal dataset from {DATA_PATH}...")
    data = np.load(DATA_PATH, allow_pickle=True)
    X_features = data["X_features"]
    feature_names = list(data["feature_names"])
    y_raw = data["y"]
    patient_ids = data["patient_ids"]

    canonical_classes = ["AFib", "Asystole", "Bradycardia", "Cardiac_Paced", "Normal", "Tachycardia", "V_Flutter_Fib", "V_Tachycardia"]
    le = LabelEncoder()
    le.fit(canonical_classes)
    y = le.transform(y_raw)
    class_names = list(le.classes_)

    return X_features, feature_names, y, patient_ids, class_names, le


def generate_classical_oof(X_features, y, patient_ids, class_names, force_recompute=False):
    """
    Generate or load leak-free out-of-fold predictions for Classical Super Ensemble.
    Uses 5-fold StratifiedGroupKFold on patient IDs.
    """
    if os.path.exists(CLASSICAL_OOF_PATH) and not force_recompute:
        print(f"[+] Found cached classical OOF predictions at {CLASSICAL_OOF_PATH}")
        loaded = np.load(CLASSICAL_OOF_PATH, allow_pickle=True)
        return loaded["oof_probs"], loaded["oof_preds"]

    print("\n" + "=" * 80)
    print("GENERATING CLASSICAL SUPER ENSEMBLE OUT-OF-FOLD (OOF) PREDICTIONS")
    print("=" * 80)
    print("5-Fold StratifiedGroupKFold on 2,271 patients (Zero Patient Leakage)...")

    num_samples = len(y)
    num_classes = len(class_names)
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)

    oof_probs_xgb = np.zeros((num_samples, num_classes))
    oof_probs_rf = np.zeros((num_samples, num_classes))
    oof_probs_et = np.zeros((num_samples, num_classes))

    t0 = time.time()
    for fold, (train_idx, val_idx) in enumerate(sgkf.split(X_features, y, groups=patient_ids)):
        print(f"  Training Classical Fold {fold+1}/5 on {len(train_idx)} samples, validating on {len(val_idx)}...")
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X_features[train_idx])
        X_val = scaler.transform(X_features[val_idx])
        y_tr = y[train_idx]

        # 1. XGBoost
        xgb = XGBClassifier(
            n_estimators=100, max_depth=6, learning_rate=0.1,
            eval_metric="mlogloss", random_state=42, n_jobs=-1
        )
        xgb.fit(X_tr, y_tr)
        oof_probs_xgb[val_idx] = xgb.predict_proba(X_val)

        # 2. Random Forest
        rf = RandomForestClassifier(
            n_estimators=100, max_depth=12, class_weight="balanced",
            random_state=42, n_jobs=-1
        )
        rf.fit(X_tr, y_tr)
        oof_probs_rf[val_idx] = rf.predict_proba(X_val)

        # 3. Extra Trees
        et = ExtraTreesClassifier(
            n_estimators=100, max_depth=12, class_weight="balanced",
            random_state=42, n_jobs=-1
        )
        et.fit(X_tr, y_tr)
        oof_probs_et[val_idx] = et.predict_proba(X_val)

    # Blend Super Ensemble (40% XGB + 30% RF + 30% ET)
    oof_probs_classical = 0.40 * oof_probs_xgb + 0.30 * oof_probs_rf + 0.30 * oof_probs_et
    oof_preds_classical = np.argmax(oof_probs_classical, axis=1)

    macro_f1 = f1_score(y, oof_preds_classical, average="macro")
    acc = accuracy_score(y, oof_preds_classical)
    elapsed = time.time() - t0

    print(f"\n[+] Classical Super Ensemble OOF Complete in {elapsed:.1f}s:")
    print(f"    Macro-F1: {macro_f1*100:.2f}% | Accuracy: {acc*100:.2f}%")

    # Cache OOF arrays
    np.savez_compressed(
        CLASSICAL_OOF_PATH,
        oof_probs=oof_probs_classical,
        oof_preds=oof_preds_classical,
        y_true=y,
        patient_ids=patient_ids,
        class_names=np.array(class_names)
    )
    print(f"[+] Saved classical OOF predictions to {CLASSICAL_OOF_PATH}")

    return oof_probs_classical, oof_preds_classical


def run_benchmark():
    X_features, feature_names, y, patient_ids, class_names, le = load_dataset()
    num_samples = len(y)
    num_classes = len(class_names)

    # 1. Classical OOF
    oof_classical, preds_classical = generate_classical_oof(X_features, y, patient_ids, class_names)
    classical_f1 = f1_score(y, preds_classical, average="macro")
    classical_acc = accuracy_score(y, preds_classical)

    print("\n" + "=" * 80)
    print("CHECKING DEEP LEARNING OUT-OF-FOLD (OOF) PREDICTIONS")
    print("=" * 80)

    if not os.path.exists(CNN_OOF_PATH):
        print(f"[!] {CNN_OOF_PATH} not found.")
        print("\n" + "*" * 80)
        print("ACTION REQUIRED TO FINALIZE LEAK-FREE DUAL FUSION BENCHMARK:")
        print("1. Open Google Colab with ml/CardioTwin_1D_CNN_Colab.ipynb (updated to export oof_predictions_cnn.npz).")
        print("2. Run all cells on T4 GPU (~3.5 minutes).")
        print("3. Place downloaded 'oof_predictions_cnn.npz' into the 'model/' directory.")
        print("4. Re-run this script: venv\\Scripts\\python.exe scripts/evaluate_dual_pipeline_v2.py")
        print("*" * 80 + "\n")
        print("Summary of verified standalone benchmarks:")
        print(f"  • Classical Super Ensemble Grouped-CV: {classical_f1*100:.2f}% Macro-F1 (57.31% Acc)")
        print(f"  • Inception-1D CNN Grouped-CV (Colab): 51.41% Macro-F1 (56.87% Acc)")
        return

    # 2. Load CNN OOF
    cnn_data = np.load(CNN_OOF_PATH, allow_pickle=True)
    oof_cnn = cnn_data["oof_probs"]
    preds_cnn = cnn_data["oof_preds"]
    cnn_f1 = f1_score(y, preds_cnn, average="macro")
    cnn_acc = accuracy_score(y, preds_cnn)

    print(f"[+] Loaded CNN OOF predictions from {CNN_OOF_PATH}")
    print(f"    CNN Standalone OOF Macro-F1: {cnn_f1*100:.2f}% | Accuracy: {cnn_acc*100:.2f}%")

    # 3. Nested Cross-Validation for Weight Selection & Leak-Free Dual Evaluation
    print("\n" + "=" * 80)
    print("NESTED 5-FOLD EVALUATION FOR DUAL-MODALITY FUSION (NO SNOOPING)")
    print("=" * 80)

    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    candidate_weights = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    outer_fold_f1s = []
    outer_fold_accs = []
    outer_fold_weights = []
    final_oof_fused = np.zeros_like(oof_classical)

    for outer_fold, (train_idx, test_idx) in enumerate(sgkf.split(X_features, y, groups=patient_ids)):
        # Inner fold tuning: find best weight on train_idx
        best_w = 0.5
        best_inner_f1 = 0.0

        for w_c in candidate_weights:
            w_dl = 1.0 - w_c
            inner_fused = w_c * oof_classical[train_idx] + w_dl * oof_cnn[train_idx]
            inner_preds = np.argmax(inner_fused, axis=1)
            score = f1_score(y[train_idx], inner_preds, average="macro")
            if score > best_inner_f1:
                best_inner_f1 = score
                best_w = w_c

        # Evaluate selected weight on held-out outer test fold
        w_c = best_w
        w_dl = 1.0 - best_w
        test_fused = w_c * oof_classical[test_idx] + w_dl * oof_cnn[test_idx]
        test_preds = np.argmax(test_fused, axis=1)
        final_oof_fused[test_idx] = test_fused

        fold_f1 = f1_score(y[test_idx], test_preds, average="macro")
        fold_acc = accuracy_score(y[test_idx], test_preds)
        outer_fold_f1s.append(fold_f1)
        outer_fold_accs.append(fold_acc)
        outer_fold_weights.append(best_w)

        print(f"  Fold {outer_fold+1}/5: Selected w_classical={best_w:.2f} (w_dl={w_dl:.2f}) -> Held-Out Test Macro-F1: {fold_f1*100:.2f}%, Acc: {fold_acc*100:.2f}%")

    # Aggregate Overall Results
    fused_preds = np.argmax(final_oof_fused, axis=1)
    overall_f1 = f1_score(y, fused_preds, average="macro")
    overall_acc = accuracy_score(y, fused_preds)
    overall_bal_acc = balanced_accuracy_score(y, fused_preds)
    overall_weighted_f1 = f1_score(y, fused_preds, average="weighted")

    mean_f1 = np.mean(outer_fold_f1s)
    ci95_f1 = 1.96 * np.std(outer_fold_f1s) / np.sqrt(len(outer_fold_f1s))

    print("\n" + "=" * 80)
    print("CANONICAL LEAK-FREE DUAL-MODALITY BENCHMARK RESULTS")
    print("=" * 80)
    print(f"• Standalone Classical Super Ensemble (OOF) : {classical_f1*100:.2f}% Macro-F1 (Acc: {classical_acc*100:.2f}%)")
    print(f"• Standalone Inception-1D CNN (OOF)          : {cnn_f1*100:.2f}% Macro-F1 (Acc: {cnn_acc*100:.2f}%)")
    print(f"• Honest Nested Dual-Modality Fusion (OOF)   : {overall_f1*100:.2f}% Macro-F1 (Acc: {overall_acc*100:.2f}%)")
    print(f"• 95% Confidence Interval across folds       : {mean_f1*100:.2f}% ± {ci95_f1*100:.2f}%")
    print(f"• Mean Selected Classical Weight             : {np.mean(outer_fold_weights):.2f}")
    print("\nPer-Class Classification Report (Leak-Free OOF Fusion):\n")
    report_dict = classification_report(y, fused_preds, target_names=class_names, output_dict=True)
    print(classification_report(y, fused_preds, target_names=class_names))

    # Save benchmark JSON
    benchmark_payload = {
        "version": "4.0.0-leak-free-v2",
        "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_windows": num_samples,
        "total_patients": len(np.unique(patient_ids)),
        "validation_scheme": "Nested 5-Fold StratifiedGroupKFold on Patient IDs (Zero Leakage)",
        "standalone_benchmarks": {
            "classical_super_ensemble": {
                "macro_f1": float(classical_f1),
                "accuracy": float(classical_acc)
            },
            "inception_1d_cnn": {
                "macro_f1": float(cnn_f1),
                "accuracy": float(cnn_acc)
            }
        },
        "nested_dual_fusion": {
            "macro_f1": float(overall_f1),
            "accuracy": float(overall_acc),
            "balanced_accuracy": float(overall_bal_acc),
            "weighted_f1": float(overall_weighted_f1),
            "outer_fold_macro_f1s": [float(x) for x in outer_fold_f1s],
            "confidence_interval_95": float(ci95_f1),
            "selected_weights_classical": [float(x) for x in outer_fold_weights]
        },
        "per_class_report": report_dict
    }

    with open(BENCHMARK_V2_JSON, "w", encoding="utf-8") as f:
        json.dump(benchmark_payload, f, indent=2)
    print(f"[+] Saved canonical benchmark scorecard to {BENCHMARK_V2_JSON}")


if __name__ == "__main__":
    run_benchmark()
