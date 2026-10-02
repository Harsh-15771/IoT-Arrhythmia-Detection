"""
CardioTwin - Multimodal Digital Twin Fusion Engine
Combines:
  Layer 1: Static EHR Patient Profile & Framingham CVD Base Risk (0-100%)
  Layer 2: Live Sensor Telemetry (BPM, RMSSD, SDNN, SpO2, Arrhythmia Probability)
  Layer 3: Bayesian Risk Trajectory & Dynamic Updating
  Simulator: Real-time "What-If" clinical intervention testing
"""

import time
import math
import json
from typing import Dict, Any, List, Optional

try:
    from framingham_risk import calculate_framingham_cvd_risk
except ImportError:
    from backend.framingham_risk import calculate_framingham_cvd_risk



class CardioTwin:
    def __init__(self, patient_ehr: Dict[str, Any]):
        self.patient = patient_ehr
        self.patient_id = patient_ehr.get("id", "UNKNOWN")
        self.name = patient_ehr.get("name", "Unknown Patient")
        
        # Layer 1: Baseline 10-Year Clinical Cardiovascular Risk (Framingham Model)
        self.base_risk_data = self._compute_base_risk()
        self.base_risk_score = float(self.base_risk_data.get("recalibrated_risk_pct", 15.0))
        self.base_clinical_risk_pct = self.base_risk_score
        
        # Data provenance state: 'INITIALIZED', 'LIVE_HARDWARE', 'RECORDED_REPLAY', or 'SIMULATION'
        self.data_source = "INITIALIZED"
        
        # Layer 2 & 3: Dynamic Physiological State & Telemetry
        self.current_vitals = {
            "bpm": float(patient_ehr.get("vitals", {}).get("resting_hr", 72)),
            "rmssd": 38.0,
            "sdnn": 45.0,
            "spo2": float(patient_ehr.get("vitals", {}).get("spo2_baseline", 98)),
            "signal_quality": 0.95,
            "arrhythmia_predicted": "Normal",
            "arrhythmia_probabilities": {"Normal": 0.92, "AFib": 0.02, "Tachycardia": 0.02, "Bradycardia": 0.015, "Cardiac_Paced": 0.01, "V_Tachycardia": 0.005, "V_Flutter_Fib": 0.005, "Asystole": 0.005}
        }
        
        # Real-time Evidence-Aware Physiological Instability Score (0 - 100)
        # Note: Kept separate from 10-year baseline Framingham risk percentage.
        self.physiological_instability_score = self.base_risk_score
        self.current_dynamic_risk = self.physiological_instability_score # Backwards-compatible alias
        
        # History buffers for trajectory graphs & audit log
        self.risk_history: List[Dict[str, Any]] = []
        self.alert_log: List[Dict[str, Any]] = []
        
        # Initial trajectory record
        self._record_history()

    def _compute_base_risk(self) -> Dict[str, Any]:
        p = self.patient
        v = p.get("vitals", {})
        l = p.get("labs", {})
        s = p.get("lifestyle", {})
        c = p.get("clinical_history", {})
        
        return calculate_framingham_cvd_risk(
            age=p.get("age", 50),
            gender=p.get("gender", "male"),
            systolic_bp=v.get("systolic_bp", 125),
            bp_treated=v.get("bp_treated", False),
            total_cholesterol=l.get("total_cholesterol", 190),
            hdl_cholesterol=l.get("hdl_cholesterol", 45),
            smoker=s.get("smoker", False),
            diabetes="Diabetes" in str(c.get("conditions", [])),
            is_south_asian=True
        )

    def update_telemetry(self, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates the Digital Twin with incoming PPG telemetry (Stream 2),
        calculates dynamic physiological instability score, and generates clinical screening alerts.
        """
        self.current_vitals.update(sensor_data)
        self.data_source = sensor_data.get("data_source", self.data_source if self.data_source != "INITIALIZED" else "LIVE_HARDWARE")
        
        bpm = float(self.current_vitals.get("bpm", 72))
        rmssd = float(self.current_vitals.get("rmssd", 35.0))
        spo2 = float(self.current_vitals.get("spo2", 98))
        sqi = float(self.current_vitals.get("signal_quality", 0.85))
        arrhythmia = str(self.current_vitals.get("arrhythmia_predicted", "Normal"))
        probs = self.current_vitals.get("arrhythmia_probabilities", {})

        # SQI Gating: If signal quality is insufficient or finger disconnected, do not trigger acute arrhythmia alarms
        is_signal_reliable = (sqi >= 0.40) and ("Insufficient" not in arrhythmia) and ("Disconnected" not in arrhythmia) and ("Buffering" not in arrhythmia)

        # 1. Acute Rhythm Risk Modulator (Layer 2)
        if is_signal_reliable:
            acute_event_prob = 1.0 - float(probs.get("Normal", 0.85))
        else:
            acute_event_prob = 0.05 # Gated fallback during noise

        # 2. Autonomic Tone Instability (RMSSD suppression reflects severe sympathetic drive)
        autonomic_penalty = 0.0
        if is_signal_reliable:
            if rmssd < 15.0:
                autonomic_penalty += 15.0
            elif rmssd < 25.0:
                autonomic_penalty += 8.0

        # 3. Hemodynamic Strain (Tachycardia / Severe Bradycardia)
        hr_penalty = 0.0
        if is_signal_reliable:
            if bpm > 130 or (bpm < 45 and bpm > 0):
                hr_penalty += 18.0
            elif bpm > 105 or (bpm < 55 and bpm > 0):
                hr_penalty += 8.0

        # 4. Peripheral Oxygen Desaturation (Hypoxia penalty)
        hypoxia_penalty = 0.0
        if spo2 < 90 and spo2 > 50:
            hypoxia_penalty += 25.0
        elif spo2 < 94 and spo2 > 50:
            hypoxia_penalty += 10.0

        # Dynamic Physiological Instability Formulation:
        # Fuses patient baseline CVD predisposition (30%) with real-time acute distress components (70%)
        prior_weight = 0.30
        acute_weight = 0.70
        acute_distress = (acute_event_prob * 45.0) + autonomic_penalty + hr_penalty + hypoxia_penalty
        raw_score = (self.base_risk_score * prior_weight) + (acute_distress * acute_weight)
        
        # Exponential moving average smoothing for trajectory stability
        alpha = 0.35
        self.physiological_instability_score = round(alpha * raw_score + (1.0 - alpha) * self.physiological_instability_score, 1)
        self.physiological_instability_score = max(1.0, min(99.0, self.physiological_instability_score))
        self.current_dynamic_risk = self.physiological_instability_score

        # Check for clinical screening alerts
        self._check_alerts(bpm, spo2, arrhythmia, sqi, self.physiological_instability_score, is_signal_reliable)

        # Record trajectory snapshot
        self._record_history()

        return self.get_status()

    def _check_alerts(self, bpm: float, spo2: float, arrhythmia: str, sqi: float, instability_score: float, is_reliable: bool):
        timestamp = time.strftime("%H:%M:%S")
        
        if not is_reliable:
            # Signal quality warning rather than false clinical alarm
            if len(self.alert_log) == 0 or self.alert_log[-1].get("category") != "SIGNAL_QUALITY":
                self.alert_log.append({
                    "time": timestamp,
                    "severity": "INFO",
                    "category": "SIGNAL_QUALITY",
                    "message": f"Signal Quality Warning (SQI: {sqi:.2f}): PPG waveform degraded by motion or contact resistance. Screening paused."
                })
            return

        # Clinical screening alerts — clearly framed as screening findings requiring ECG review
        if arrhythmia in ("V_Tachycardia", "V_Flutter_Fib", "Asystole"):
            self.alert_log.append({
                "time": timestamp,
                "severity": "CRITICAL",
                "category": "RHYTHM",
                "message": f"Critical Rhythm Screening: Possible {arrhythmia} detected on PPG. Urgent 12-lead ECG and clinical verification required!"
            })
        elif arrhythmia == "AFib":
            self.alert_log.append({
                "time": timestamp,
                "severity": "HIGH",
                "category": "RHYTHM",
                "message": "Atrial Fibrillation Pattern Detected: Optical pulse irregularity identified. 12-lead ECG confirmation recommended."
            })
        elif arrhythmia == "Cardiac_Paced":
            self.alert_log.append({
                "time": timestamp,
                "severity": "MODERATE",
                "category": "RHYTHM",
                "message": "Cardiac Paced / Conduction Block Pattern: Artificial pacing morphology detected. Verify patient device history."
            })
        elif instability_score >= 75.0:
            self.alert_log.append({
                "time": timestamp,
                "severity": "HIGH",
                "category": "INSTABILITY",
                "message": f"High Physiological Instability ({instability_score}/100): Marked autonomic stress and hemodynamic perturbation."
            })
        elif spo2 < 92 and spo2 > 50:
            self.alert_log.append({
                "time": timestamp,
                "severity": "MODERATE",
                "category": "OXYGENATION",
                "message": f"Hypoxia Warning: SpO2 decreased to {spo2:.0f}%. Verify airway and clinical status."
            })
        elif bpm > 130:
            self.alert_log.append({
                "time": timestamp,
                "severity": "MODERATE",
                "category": "HEMODYNAMICS",
                "message": f"Tachycardia Alert: Heart rate elevated to {bpm:.0f} BPM. Clinical assessment recommended."
            })

    def _record_history(self):
        self.risk_history.append({
            "timestamp": time.strftime("%H:%M:%S"),
            "dynamic_risk": self.physiological_instability_score,
            "instability_score": self.physiological_instability_score,
            "base_risk": self.base_risk_score,
            "bpm": self.current_vitals.get("bpm"),
            "rmssd": self.current_vitals.get("rmssd"),
            "spo2": self.current_vitals.get("spo2"),
            "sqi": self.current_vitals.get("signal_quality"),
            "data_source": self.data_source
        })
        if len(self.risk_history) > 60:
            self.risk_history.pop(0)

    def simulate_treatment(self, modifications: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interactive 'What-If' Intervention Simulator:
        Estimates long-term (5-10 year sustained therapeutic adherence) risk reduction
        based on evidence-based pharmacological and lifestyle modifications.
        Educational decision-support tool — not an autonomous clinical prescription.
        """
        virtual_patient = json.loads(json.dumps(self.patient))
        v = virtual_patient.get("vitals", {})
        l = virtual_patient.get("labs", {})
        s = virtual_patient.get("lifestyle", {})

        # Apply lifestyle modifications
        if "systolic_bp" in modifications:
            v["systolic_bp"] = float(modifications["systolic_bp"])
        if "smoker" in modifications:
            s["smoker"] = bool(modifications["smoker"])
        if "total_cholesterol" in modifications:
            l["total_cholesterol"] = float(modifications["total_cholesterol"])
        
        # Medication simulations with evidence-based assumptions
        added_meds = modifications.get("add_medications", [])
        hr_reduction = 0.0
        bp_reduction = 0.0
        chol_reduction_pct = 0.0
        interventions_applied = []

        for med in added_meds:
            med_lower = med.lower()
            if "metoprolol" in med_lower or "beta" in med_lower:
                hr_reduction += 12.0
                bp_reduction += 8.0
                interventions_applied.append("Beta-blocker (Metoprolol 25-50mg: ~8 mmHg SBP, ~12 BPM reduction)")
            elif "statin" in med_lower or "atorvastatin" in med_lower:
                chol_reduction_pct += 0.28 # 28% total cholesterol / LDL reduction per ACC/AHA statin trials
                interventions_applied.append("Moderate-intensity statin (Atorvastatin 20mg: ~28% total cholesterol reduction)")
            elif "ramipril" in med_lower or "telmisartan" in med_lower or "ace" in med_lower or "arb" in med_lower:
                bp_reduction += 12.0
                v["bp_treated"] = True
                interventions_applied.append("ACE-inhibitor / ARB (Telmisartan 40mg: ~12 mmHg SBP reduction)")

        v["systolic_bp"] = max(100.0, v.get("systolic_bp", 125) - bp_reduction)
        l["total_cholesterol"] = max(110.0, l.get("total_cholesterol", 190) * (1.0 - chol_reduction_pct))
        simulated_hr = max(50.0, self.current_vitals["bpm"] - hr_reduction)

        # Recalculate projected Layer 1 Framingham risk under sustained adherence
        sim_risk_data = calculate_framingham_cvd_risk(
            age=virtual_patient.get("age", 50),
            gender=virtual_patient.get("gender", "male"),
            systolic_bp=v["systolic_bp"],
            bp_treated=v.get("bp_treated", False),
            total_cholesterol=l["total_cholesterol"],
            hdl_cholesterol=l.get("hdl_cholesterol", 45),
            smoker=s.get("smoker", False),
            diabetes="Diabetes" in str(virtual_patient.get("clinical_history", {}).get("conditions", [])),
            is_south_asian=True
        )

        sim_base_risk = sim_risk_data["recalibrated_risk_pct"]
        risk_reduction_pct = round(self.base_risk_score - sim_base_risk, 1)

        return {
            "original_base_risk": self.base_risk_score,
            "projected_base_risk": sim_base_risk,
            "absolute_risk_reduction": risk_reduction_pct,
            "projected_vascular_age": sim_risk_data["vascular_age"],
            "simulated_heart_rate": round(simulated_hr, 1),
            "simulated_systolic_bp": round(v["systolic_bp"], 1),
            "time_horizon": "5 to 10-year sustained therapeutic adherence",
            "interventions_applied": interventions_applied,
            "clinical_summary": f"Estimated {abs(risk_reduction_pct)}% {'reduction' if risk_reduction_pct >= 0 else 'increase'} in 10-year CVD risk with sustained adherence. Projected vascular age: {sim_risk_data['vascular_age']} years.",
            "disclaimer": "Educational clinical decision support — not an autonomous prescription engine. All therapies require physician review."
        }

    def get_status(self) -> Dict[str, Any]:
        # Risk tiering
        score = self.physiological_instability_score
        if score >= 70.0:
            status_label = "Critical Alert"
        elif score >= 40.0:
            status_label = "Elevated Caution"
        elif score >= 20.0:
            status_label = "Moderate Instability"
        else:
            status_label = "Physiologically Stable"

        return {
            "patient_id": self.patient_id,
            "patient_name": self.name,
            "status_label": status_label,
            "data_source": self.data_source,
            "physiological_instability_score": self.physiological_instability_score,
            "current_dynamic_risk": self.current_dynamic_risk, # Backwards-compatible alias
            "base_clinical_risk": self.base_risk_score,
            "baseline_10yr_cvd_risk_pct": self.base_risk_score,
            "current_vitals": self.current_vitals,
            "patient_ehr": self.patient,
            "risk_history": self.risk_history[-30:],
            "recent_alerts": self.alert_log[-6:],
            "clinical_disclaimer": "CardioTwin provides non-diagnostic clinical decision support. PPG rhythm analysis is an observational screening tool requiring 12-lead ECG diagnostic confirmation."
        }

if __name__ == "__main__":
    import os
    pat_file = "synthetic_patients.json" if os.path.exists("synthetic_patients.json") else "backend/synthetic_patients.json"
    with open(pat_file, "r") as f:
        cohort = json.load(f)
    
    twin = CardioTwin(cohort[0])
    print("Initialized CardioTwin for:", twin.name)
    print("Base Risk:", twin.base_risk_score)
    
    # Test telemetry update
    res = twin.update_telemetry({
        "bpm": 88,
        "rmssd": 22.0,
        "spo2": 97,
        "arrhythmia_predicted": "Normal",
        "arrhythmia_probabilities": {"Normal": 0.88, "Tachycardia": 0.08, "AFib": 0.02, "Bradycardia": 0.02}
    })
    print("Dynamic Risk after telemetry:", res["current_dynamic_risk"])

    # Test What-If Simulator
    sim = twin.simulate_treatment({
        "add_medications": ["Metoprolol", "Atorvastatin"],
        "smoker": False
    })
    print("Simulation Outcome:", sim["clinical_summary"])
