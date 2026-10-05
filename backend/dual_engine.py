"""
CardioTwin - Dual-Modality Inference Engine (Phase 2)
Integrates:
  1. Modality A: Classical Super Ensemble (XGBoost + Random Forest + Extra Trees on 27 Biomarkers - 47.39% Grouped-CV Macro-F1)
  2. Modality B: Deep Learning Inception-1D (Multi-Scale Convolutions on 100 Hz Raw Waveforms - 51.41% Grouped-CV Macro-F1)
  3. Weighted Fusion: Investigational screening fusion architecture (pending re-evaluation with strict CNN OOF predictions)
"""

import os
import joblib
import torch
import numpy as np
import torch.nn as nn
from typing import Dict, Any, Tuple, Optional


class InceptionBlock1D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        branch_ch = out_channels // 4
        self.branch1 = nn.Sequential(
            nn.Conv1d(in_channels, branch_ch, kernel_size=3, padding=1),
            nn.BatchNorm1d(branch_ch),
            nn.ReLU()
        )
        self.branch2 = nn.Sequential(
            nn.Conv1d(in_channels, branch_ch, kernel_size=7, padding=3),
            nn.BatchNorm1d(branch_ch),
            nn.ReLU()
        )
        self.branch3 = nn.Sequential(
            nn.Conv1d(in_channels, branch_ch, kernel_size=15, padding=7),
            nn.BatchNorm1d(branch_ch),
            nn.ReLU()
        )
        self.branch4 = nn.Sequential(
            nn.Conv1d(in_channels, branch_ch, kernel_size=31, padding=15),
            nn.BatchNorm1d(branch_ch),
            nn.ReLU()
        )
        self.shortcut = nn.Conv1d(in_channels, out_channels, kernel_size=1) if in_channels != out_channels else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = torch.cat([self.branch1(x), self.branch2(x), self.branch3(x), self.branch4(x)], dim=1)
        return out + self.shortcut(x)


class Inception1DCNN(nn.Module):
    def __init__(self, num_classes: int = 8):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv1d(1, 32, kernel_size=7, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )
        self.inc1 = InceptionBlock1D(32, 64)
        self.pool1 = nn.Sequential(nn.MaxPool1d(2), nn.Dropout(0.2))
        self.inc2 = InceptionBlock1D(64, 128)
        self.pool2 = nn.Sequential(nn.MaxPool1d(2), nn.Dropout(0.3))
        self.inc3 = InceptionBlock1D(128, 128)
        self.gap = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.pool1(self.inc1(x))
        x = self.pool2(self.inc2(x))
        x = self.gap(self.inc3(x))
        return self.classifier(x)


class DualModalityPredictor:
    """
    Unified Dual-Modality Arrhythmia Predictor
    Fuses classical statistical biomarkers with deep morphological waveform features.
    """
    CANONICAL_CLASSES = [
        'AFib', 'Asystole', 'Bradycardia', 'Cardiac_Paced',
        'Normal', 'Tachycardia', 'V_Flutter_Fib', 'V_Tachycardia'
    ]

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self.classes = list(self.CANONICAL_CLASSES)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # 1. Load Classical Models
        self.classical_loaded = False
        self.super_ensemble = None
        self.scaler = None
        self.xgb_fallback = None
        self.feature_names = []

        try:
            ens_path = os.path.join(model_dir, "super_ensemble.pkl")
            if os.path.exists(ens_path):
                bundle = joblib.load(ens_path)
                self.super_ensemble = bundle
                self.scaler = bundle["scaler"]
                self.classes = bundle.get("class_names", self.CANONICAL_CLASSES)
                self.classical_loaded = True
                print("[INFO] DualEngine: Loaded Classical Super Ensemble (XGB+RF+ET)")
            else:
                # Fallback to standalone XGBoost
                xgb_path = os.path.join(model_dir, "xgboost_ppg_model.pkl")
                scaler_path = os.path.join(model_dir, "scaler.pkl")
                if os.path.exists(xgb_path) and os.path.exists(scaler_path):
                    self.xgb_fallback = joblib.load(xgb_path)
                    self.scaler = joblib.load(scaler_path)
                    self.classical_loaded = True
                    print("[INFO] DualEngine: Loaded standalone XGBoost fallback")
        except Exception as e:
            print(f"[WARN] DualEngine: Could not load classical model: {e}")

        # Feature names
        try:
            fn_path = os.path.join(model_dir, "feature_names.pkl")
            if os.path.exists(fn_path):
                self.feature_names = list(joblib.load(fn_path))
        except Exception:
            self.feature_names = []

        # 2. Load Deep Learning Inception-1D Model
        self.dl_loaded = False
        self.dl_model = None
        try:
            cnn_path = os.path.join(model_dir, "ppg_1d_cnn.pt")
            if os.path.exists(cnn_path):
                self.dl_model = Inception1DCNN(num_classes=len(self.classes))
                state = torch.load(cnn_path, map_location=self.device)
                self.dl_model.load_state_dict(state)
                self.dl_model.to(self.device)
                self.dl_model.eval()
                self.dl_loaded = True
                print(f"[INFO] DualEngine: Loaded Inception-1D Deep Learning Champion on {self.device}")
        except Exception as e:
            print(f"[WARN] DualEngine: Could not load Inception-1D model: {e}")

        # 3. Load SHAP Feature Attribution Knowledge
        self.shap_metadata = None
        try:
            shap_path = os.path.join(model_dir, "shap_feature_importance.json")
            if not os.path.exists(shap_path):
                shap_path = os.path.join(os.path.dirname(model_dir), "docs", "shap_feature_importance.json")
            if os.path.exists(shap_path):
                import json
                with open(shap_path, "r", encoding="utf-8") as f:
                    self.shap_metadata = json.load(f)
                print("[INFO] DualEngine: Loaded SHAP explainability knowledge base")
        except Exception as e:
            print(f"[WARN] DualEngine: Could not load SHAP metadata: {e}")

    def predict_window(
        self,
        sig_window: np.ndarray,
        feats: Optional[Dict[str, Any]] = None,
        w_classical: float = 0.30,
        w_dl: float = 0.70
    ) -> Dict[str, Any]:
        """
        Run Dual-Modality Inference on a single 10-second PPG window.
        Returns combined probabilities, individual modality predictions, and confidence.
        """
        probs_c = None
        probs_dl = None

        # 1. Classical Modality Inference
        if self.classical_loaded and feats is not None and self.scaler is not None and len(self.feature_names) > 0:
            try:
                feat_vec = np.array([feats.get(c, 0.0) for c in self.feature_names]).reshape(1, -1)
                feat_vec = np.nan_to_num(feat_vec, nan=0.0, posinf=1e4, neginf=-1e4)
                feat_sc = self.scaler.transform(feat_vec)

                if self.super_ensemble is not None:
                    p_xgb = self.super_ensemble["xgb"].predict_proba(feat_sc)[0]
                    p_rf = self.super_ensemble["rf"].predict_proba(feat_sc)[0]
                    p_et = self.super_ensemble["et"].predict_proba(feat_sc)[0]
                    w = self.super_ensemble["weights"]
                    probs_c = w[0] * p_xgb + w[1] * p_rf + w[2] * p_et
                elif self.xgb_fallback is not None:
                    probs_c = self.xgb_fallback.predict_proba(feat_sc)[0]
            except Exception as e:
                probs_c = None

        # 2. Deep Learning Waveform Inference
        if self.dl_loaded and self.dl_model is not None and len(sig_window) >= 1000:
            try:
                # Normalize waveform (zero mean, unit variance)
                wf = sig_window[:1000].astype(np.float32)
                std_val = float(np.std(wf))
                if std_val > 1e-4:
                    wf = (wf - float(np.mean(wf))) / std_val
                else:
                    wf = wf - float(np.mean(wf))

                # Shape: (1, 1, 1000)
                tensor_in = torch.tensor(wf, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    logits = self.dl_model(tensor_in)
                    probs_dl = torch.softmax(logits, dim=1).cpu().numpy()[0]
            except Exception as e:
                probs_dl = None

        # 3. Decision Fusion
        mode = "HEURISTIC_FALLBACK"
        if probs_c is not None and probs_dl is not None:
            fused = w_classical * probs_c + w_dl * probs_dl
            fused = fused / np.sum(fused)
            mode = "DUAL_MODALITY_FUSION"
        elif probs_dl is not None:
            fused = probs_dl
            mode = "INCEPTION_1D_ONLY"
        elif probs_c is not None:
            fused = probs_c
            mode = "CLASSICAL_ENSEMBLE_ONLY"
        else:
            # Fallback
            fused = np.zeros(len(self.classes), dtype=float)
            normal_idx = self.classes.index("Normal") if "Normal" in self.classes else 0
            fused[normal_idx] = 0.90
            rem = 0.10 / max(1, len(self.classes) - 1)
            for i in range(len(self.classes)):
                if i != normal_idx:
                    fused[i] = rem

        pred_idx = int(np.argmax(fused))
        pred_label = self.classes[pred_idx]
        confidence = float(fused[pred_idx])

        # Feature Attribution & Explainability (Phase 1.1)
        explainability = {
            "method": "SHAP (TreeExplainer on Classical XGBoost Component)",
            "top_drivers": [],
            "summary": f"Optical pattern '{pred_label}' identified with {confidence*100:.1f}% confidence."
        }
        if self.shap_metadata and "per_class_importance" in self.shap_metadata:
            class_ranking = self.shap_metadata["per_class_importance"].get(pred_label, [])
            top_3 = class_ranking[:4]
            drivers = []
            for item in top_3:
                feat_name = item["feature"]
                val = feats.get(feat_name) if feats else None
                drivers.append({
                    "feature": feat_name,
                    "value": round(float(val), 3) if val is not None else None,
                    "mean_abs_shap": item["mean_abs_shap"]
                })
            explainability["top_drivers"] = drivers

        # Evidence Ledger / Honest Limitations Disclosure (Phase 1.2)
        evidence_ledger = {
            "sensor_modality": "Single-channel reflective photoplethysmography (MAX30102 IR 880nm)",
            "spo2_available": False,
            "spo2_channel_status": "UNAVAILABLE (Single IR channel cannot compute clinical ratiometric SpO2)",
            "ecg_equivalence": "NOT EQUIVALENT (Optical pulse waves reflect microvascular blood volume changes, not myocardial electrical vectors)",
            "training_cohort": "MIMIC-III & PhysioNet CinC 2015 ICU cohorts (2,271 patients)",
            "source_confounding_warning": "High alert: Ventricular arrhythmias (VT/V_Flutter_Fib) derive exclusively from CinC 2015 ICU alarm records",
            "regulatory_status": "Investigational research prototype — not approved by FDA or CDSCO for clinical diagnosis"
        }

        return {
            "predicted_label": pred_label,
            "research_waveform_pattern": pred_label,
            "disclaimer": "Investigational screening prototype. Optical PPG patterns cannot substitute for 12-lead diagnostic ECG.",
            "confidence": confidence,
            "probabilities": {c: round(float(fused[i]), 4) for i, c in enumerate(self.classes)},
            "classical_probabilities": {c: round(float(probs_c[i]), 4) for i, c in enumerate(self.classes)} if probs_c is not None else None,
            "dl_probabilities": {c: round(float(probs_dl[i]), 4) for i, c in enumerate(self.classes)} if probs_dl is not None else None,
            "pipeline_mode": mode,
            "fusion_weights": {"classical": w_classical, "dl": w_dl},
            "explainability": explainability,
            "evidence_ledger": evidence_ledger
        }
