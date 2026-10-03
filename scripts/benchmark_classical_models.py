"""
CardioTwin - Classical ML Algorithm Tournament (Phase 2)
Systematically evaluates multiple algorithms on the exact same 2,271 patients (4,683 windows)
using 5-Fold StratifiedGroupKFold on Patient IDs (Zero Data Leakage).

Algorithms Benchmarked:
  1. XGBoost (Current Baseline)
  2. Random Forest (Balanced Bagging Ensemble)
  3. Extra Trees (Extremely Randomized Trees)
  4. Histogram Gradient Boosting (Fast Binned GBDT)
  5. Multi-Layer Perceptron (MLP Neural Net on Features)
  6. Soft-Voting Super Ensemble (XGBoost + Random Forest + Extra Trees)
"""

import os
import sys
import json
import time
import argparse
import numpy as np

from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight

from sklearn.ensemble import (
    RandomForestClassifier,
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    VotingClassifier
)
from sklearn.neural_network import MLPClassifier
from xgboost import XGBClassifier

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT_DIR, "data", "processed", "unified_multimodal_dataset.npz")
MODEL_DIR = os.path.join(ROOT_DIR, "model")


def load_dataset():
    data = np.load(DATA_PATH, allow_pickle=True)
    X = np.nan_to_num(data['X_features'], nan=0.0, posinf=1e4, neginf=-1e4)
    y_raw = data['y']
    patient_ids = data['patient_ids']

    # Use canonical class ordering
    le = LabelEncoder()
    canonical_classes = ['AFib', 'Asystole', 'Bradycardia', 'Cardiac_Paced', 'Normal', 'Tachycardia', 'V_Flutter_Fib', 'V_Tachycardia']
    le.fit(canonical_classes)
    y = le.transform(y_raw)
    class_names = list(le.classes_)

    return X, y, patient_ids, class_names


def get_candidate_models(class_names):
    num_classes = len(class_names)
    return {
        "XGBoost": lambda fold: XGBClassifier(
            n_estimators=250, max_depth=6, learning_rate=0.08,
            subsample=0.85, colsample_bytree=0.85, objective='multi:softprob',
            num_class=num_classes, random_state=42 + fold, n_jobs=-1, eval_metric='mlogloss'
        ),
        "Random_Forest": lambda fold: RandomForestClassifier(
            n_estimators=250, max_depth=16, min_samples_split=4,
            class_weight='balanced', random_state=42 + fold, n_jobs=-1
        ),
        "Extra_Trees": lambda fold: ExtraTreesClassifier(
            n_estimators=250, max_depth=16, min_samples_split=4,
            class_weight='balanced', random_state=42 + fold, n_jobs=-1
        ),
        "Hist_Gradient_Boosting": lambda fold: HistGradientBoostingClassifier(
            max_iter=180, max_depth=8, learning_rate=0.08,
            class_weight='balanced', random_state=42 + fold
        ),
        "MLP_Neural_Net": lambda fold: MLPClassifier(
            hidden_layer_sizes=(128, 64), activation='relu',
            learning_rate_init=0.002, max_iter=150, early_stopping=True,
            random_state=42 + fold
        )
    }


def evaluate_single_model(name, model_fn, X, y, patient_ids, class_names, cv_folds=5):
    print(f"\n[+] Evaluating: {name} ({cv_folds}-Fold Patient-Isolated CV)...")
    sgkf = StratifiedGroupKFold(n_splits=cv_folds, shuffle=True, random_state=42)

    oof_preds = np.zeros(len(y), dtype=int)
    oof_probs = np.zeros((len(y), len(class_names)), dtype=float)
    fold_f1s = []
    t0 = time.time()

    for fold, (train_idx, val_idx) in enumerate(sgkf.split(X, y, groups=patient_ids)):
        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)

        clf = model_fn(fold)

        # Apply sample weights if supported
        if name in ("XGBoost", "Hist_Gradient_Boosting"):
            sw = compute_sample_weight('balanced', y_train)
            clf.fit(X_train_scaled, y_train, sample_weight=sw)
        else:
            clf.fit(X_train_scaled, y_train)

        val_probs = clf.predict_proba(X_val_scaled)
        val_preds = np.argmax(val_probs, axis=1)

        oof_preds[val_idx] = val_preds
        oof_probs[val_idx] = val_probs

        f_macro = f1_score(y_val, val_preds, average='macro', zero_division=0)
        fold_f1s.append(f_macro)

    elapsed = time.time() - t0
    acc = accuracy_score(y, oof_preds)
    macro_f1 = f1_score(y, oof_preds, average='macro', zero_division=0)
    weighted_f1 = f1_score(y, oof_preds, average='weighted', zero_division=0)

    print(f"    Finished in {elapsed:5.1f}s | Acc: {acc*100:5.2f}% | Macro-F1: {macro_f1*100:5.2f}% | Weighted-F1: {weighted_f1*100:5.2f}%")

    return {
        "name": name,
        "accuracy": acc,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "fold_f1s": fold_f1s,
        "elapsed_sec": elapsed,
        "oof_preds": oof_preds,
        "oof_probs": oof_probs
    }


def run_tournament(cv_folds=5):
    print("=" * 80)
    print("  CARDIOTWIN MULTI-ALGORITHM TOURNAMENT (2,271 PATIENTS)")
    print("=" * 80)

    X, y, patient_ids, class_names = load_dataset()
    print(f"[+] Loaded {len(y):,} windows across {len(np.unique(patient_ids)):,} unique patients.")
    print(f"[+] 27 Features Evaluated | 8 Rhythm Classes")

    models_dict = get_candidate_models(class_names)
    results = {}

    for name, model_fn in models_dict.items():
        res = evaluate_single_model(name, model_fn, X, y, patient_ids, class_names, cv_folds=cv_folds)
        results[name] = res

    # Evaluate Soft-Voting Ensemble (XGBoost + Random Forest + Extra Trees)
    print("\n[+] Evaluating Soft-Voting Super Ensemble (XGBoost + Random Forest + Extra Trees)...")
    ensemble_probs = (
        0.40 * results["XGBoost"]["oof_probs"] +
        0.30 * results["Random_Forest"]["oof_probs"] +
        0.30 * results["Extra_Trees"]["oof_probs"]
    )
    ensemble_preds = np.argmax(ensemble_probs, axis=1)

    ens_acc = accuracy_score(y, ensemble_preds)
    ens_macro_f1 = f1_score(y, ensemble_preds, average='macro', zero_division=0)
    ens_weighted_f1 = f1_score(y, ensemble_preds, average='weighted', zero_division=0)

    results["Soft_Voting_Ensemble"] = {
        "name": "Soft_Voting_Ensemble",
        "accuracy": ens_acc,
        "macro_f1": ens_macro_f1,
        "weighted_f1": ens_weighted_f1,
        "elapsed_sec": sum(results[k]["elapsed_sec"] for k in ("XGBoost", "Random_Forest", "Extra_Trees")),
        "oof_preds": ensemble_preds,
        "oof_probs": ensemble_probs
    }

    # Print Final Leaderboard Table
    print("\n" + "=" * 80)
    print("  FINAL ALGORITHM LEADERBOARD (SORTED BY MACRO-F1)")
    print("=" * 80)
    print(f"{'Rank':<5} | {'Algorithm':<26} | {'Accuracy':<10} | {'Macro-F1':<10} | {'Weighted-F1':<12} | {'Time':<6}")
    print("-" * 80)

    sorted_results = sorted(results.values(), key=lambda r: r["macro_f1"], reverse=True)
    for rank, r in enumerate(sorted_results, 1):
        is_champion = " [CHAMPION]" if rank == 1 else ""
        print(f"#{rank:<4} | {r['name']:<26} | {r['accuracy']*100:6.2f}%    | {r['macro_f1']*100:6.2f}%    | {r['weighted_f1']*100:6.2f}%       | {r['elapsed_sec']:4.1f}s{is_champion}")
    print("=" * 80)

    # Save Tournament Summary JSON
    summary_path = os.path.join(MODEL_DIR, "algorithm_tournament_results.json")
    export_dict = {
        "dataset": "2,271 Patients | 4,683 Windows (10s @ 100 Hz)",
        "protocol": f"{cv_folds}-Fold StratifiedGroupKFold on Patient IDs (Zero Patient-Leakage)",
        "leaderboard": [
            {
                "rank": rank,
                "model": r["name"],
                "accuracy": round(float(r["accuracy"]), 4),
                "macro_f1": round(float(r["macro_f1"]), 4),
                "weighted_f1": round(float(r["weighted_f1"]), 4),
                "training_time_sec": round(float(r["elapsed_sec"]), 1)
            }
            for rank, r in enumerate(sorted_results, 1)
        ]
    }
    with open(summary_path, "w") as f:
        json.dump(export_dict, f, indent=2)
    print(f"\n[+] Saved Tournament Results to: {summary_path}")

    return export_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Multi-Algorithm Tournament")
    parser.add_argument("--cv", type=int, default=5, help="Number of CV folds")
    args = parser.parse_args()

    run_tournament(cv_folds=args.cv)
