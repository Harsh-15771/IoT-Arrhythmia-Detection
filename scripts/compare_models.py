import json

with open("model/model_metadata.json") as f:
    xgb = json.load(f)

with open("model/cnn_metadata.json") as f:
    cnn = json.load(f)

print("=" * 75)
print("  CARDIOTWIN DUAL-MODEL REPRESENTATION BENCHMARK (2,271 PATIENTS)")
print("=" * 75)
print(f"Dataset:              2,271 Patients | 4,683 Windows (10s @ 100 Hz)")
print(f"Validation Protocol:  5-Fold StratifiedGroupKFold on Patient IDs (Zero Leakage)")
print("-" * 75)
print(f"{'Metric':<25} | {'Model A (XGBoost v3)':<22} | {'Model B (PyTorch 1D-CNN)':<22}")
print("-" * 75)
print(f"{'Overall Accuracy':<25} | {xgb['metrics']['overall_accuracy']*100:6.2f}%                 | {cnn['metrics']['overall_accuracy']*100:6.2f}%")
print(f"{'Macro-F1 Score':<25} | {xgb['metrics']['macro_f1']*100:6.2f}%                 | {cnn['metrics']['macro_f1']*100:6.2f}%")
print(f"{'Weighted-F1 Score':<25} | {xgb['metrics']['weighted_f1']*100:6.2f}%                 | {cnn['metrics']['weighted_f1']*100:6.2f}%")
print("-" * 75)
print("\n" + "=" * 75)
print("  PER-CLASS F1-SCORE & SENSITIVITY (RECALL) COMPARISON")
print("=" * 75)
print(f"{'Class':<15} | {'XGBoost F1':<12} | {'1D-CNN F1':<12} | {'F1 Delta':<10} | {'1D-CNN Recall':<14}")
print("-" * 75)

xgb_f1 = {
    "Normal": 0.7802,
    "Bradycardia": 0.6542,
    "Tachycardia": 0.6292,
    "AFib": 0.5614,
    "V_Tachycardia": 0.3315,
    "Cardiac_Paced": 0.3075,
    "Asystole": 0.2507,
    "V_Flutter_Fib": 0.2222
}

cnn_metrics = cnn["per_class_metrics"]
for cls in xgb["classes"]:
    c_f1 = cnn_metrics[cls]["f1-score"]
    c_rec = cnn_metrics[cls]["recall"]
    x_f1 = xgb_f1.get(cls, 0.0)
    delta = c_f1 - x_f1
    delta_str = f"+{delta*100:5.2f}%" if delta >= 0 else f"{delta*100:5.2f}%"
    print(f"{cls:<15} | {x_f1:10.4f}   | {c_f1:10.4f}   | {delta_str:<10} | {c_rec*100:6.2f}%")
print("-" * 75)
