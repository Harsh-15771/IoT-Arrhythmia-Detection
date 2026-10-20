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
        self.data_source = "SIMULATION"
        
        # Layer 2 & 3: Dynamic Physiological State & Telemetry
        self.current_vitals = {
            "bpm": float(patient_ehr.get("vitals", {}).get("resting_hr", 72)),
            "rmssd": 38.0,
            "sdnn": 45.0,
            "spo2": float(patient_ehr.get("vitals", {}).get("spo2_baseline", 98)),
            "signal_quality": 0.95,
            "arrhythmia_predicted": "Normal",
            "arrhythmia_probabilities": {"Normal": 0.92, "AFib": 0.02, "Tachycardia": 0.02, "Bradycardia": 0.015, "Cardiac_Paced": 0.01, "V_Tachycardia": 0.005, "V_Flutter_Fib": 0.005, "Asystole": 0.005},
            "data_source": "SIMULATION"
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
        self.data_source = sensor_data.get("data_source", self.data_source)
        self.current_vitals["data_source"] = self.data_source
        
        bpm_val = self.current_vitals.get("bpm")
        bpm = float(bpm_val) if bpm_val is not None else 72.0
        rmssd_val = self.current_vitals.get("rmssd")
        rmssd = float(rmssd_val) if rmssd_val is not None else 35.0
        raw_spo2 = self.current_vitals.get("spo2")
        spo2 = float(raw_spo2) if raw_spo2 is not None else None
        sqi = float(self.current_vitals.get("signal_quality", 0.85))
        arrhythmia = str(self.current_vitals.get("arrhythmia_predicted", "Normal"))
        probs = self.current_vitals.get("arrhythmia_probabilities", {})

        # Signal Reliability Gating: If signal quality is insufficient, finger disconnected, or 5-part gate failed, do not trigger acute arrhythmia alarms
        gate_info = sensor_data.get("signal_gate") or self.current_vitals.get("signal_gate")
        gate_enabled = gate_info.get("ai_screening_enabled", True) if isinstance(gate_info, dict) else True
        is_signal_reliable = (
            (sqi >= 0.40) and 
            gate_enabled and 
            ("Verification:" not in arrhythmia) and 
            ("Insufficient" not in arrhythmia) and 
            ("Disconnected" not in arrhythmia) and 
            ("Buffering" not in arrhythmia)
        )

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
        if spo2 is not None:
            if 50 < spo2 < 90:
                hypoxia_penalty += 25.0
            elif 50 < spo2 < 94:
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

    def _check_alerts(self, bpm: float, spo2, arrhythmia: str, sqi: float, instability_score: float, is_reliable: bool):
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
        elif spo2 is not None and 50 < spo2 < 92:
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

    def _compute_ehr_vulnerability_coupling(
        self,
        bpm: Optional[float] = None,
        rmssd: Optional[float] = None,
        rr_cv: Optional[float] = None,
        pred_rhythm: str = "Normal"
    ) -> Dict[str, Any]:
        """
        Multimodal EHR-Coupled Vulnerability Substrate (Phase 3.1)
        Fuses static clinical history (medications, conditions, biomarkers)
        with real-time hemodynamic and autonomic telemetry.
        """
        coupling_flags = []
        flag_messages = []

        history = self.patient.get("clinical_history", {})
        conditions = [str(c) for c in history.get("conditions", [])]
        conditions_str = " ".join(conditions).lower()
        meds = history.get("medications", [])
        meds_str = json.dumps(meds).lower()
        labs = self.patient.get("labs", {})

        # 1. Pharmacological Beta-Blockade Escape Detection
        is_beta_blocker = any(
            b in meds_str for b in ["metoprolol", "bisoprolol", "carvedilol", "atenolol", "beta-blocker", "beta blocker"]
        )
        resting_hr = float(self.patient.get("vitals", {}).get("resting_hr", 70.0))
        has_escape = False

        if is_beta_blocker and bpm is not None and bpm > 0:
            if bpm >= 90.0 or bpm >= (resting_hr + 18.0):
                has_escape = True
                coupling_flags.append("BETA_BLOCKADE_ESCAPE")
                med_name = next(
                    (m.get("name", "Beta-Blocker") for m in meds if any(x in m.get("name", "").lower() for x in ["metoprolol", "bisoprolol", "carvedilol", "atenolol"])),
                    "Beta-Blocker"
                )
                flag_messages.append(
                    f"Elevated pulse ({bpm:.0f} BPM) despite active beta-blocker therapy ({med_name}) indicates sympathetic breakthrough."
                )

        # 2. Disease-Specific Rhythm & Autonomic Amplification
        has_afib_hx = any("atrial fibrillation" in c.lower() or "afib" in c.lower() for c in conditions)
        if has_afib_hx and rr_cv is not None and rr_cv >= 0.18:
            coupling_flags.append("SUBCLINICAL_AFIB_PRODROME")
            flag_messages.append(
                f"Elevated beat-to-beat variability (RR-CV {rr_cv*100:.1f}%) in diagnosed paroxysmal AFib patient suggests subclinical atrial fibrillation prodrome."
            )

        has_cad_or_t2dm = any(
            k in conditions_str for k in ["coronary artery disease", "post-pci", "cad", "type 2 diabetes", "diabetes mellitus"]
        ) or float(labs.get("hba1c", 0.0)) >= 7.0

        if has_cad_or_t2dm and rmssd is not None and rmssd > 0 and rmssd < 22.0:
            coupling_flags.append("AUTONOMIC_VAGAL_WITHDRAWAL")
            flag_messages.append(
                f"Severe vagal autonomic withdrawal (RMSSD {rmssd:.1f}ms) in high-risk cardiometabolic substrate."
            )

        # 3. EHR Substrate Multiplier (M_EHR in [1.00, 1.40])
        cad_term = 0.10 if ("coronary" in conditions_str or "post-pci" in conditions_str or "cad" in conditions_str) else 0.0
        hba1c_term = 0.08 if float(labs.get("hba1c", 0.0)) >= 7.0 else 0.0
        crp_term = 0.08 if float(labs.get("hs_crp", 0.0)) > 2.0 else 0.0
        escape_term = 0.14 if has_escape else 0.0

        m_ehr = 1.0 + cad_term + hba1c_term + crp_term + escape_term
        m_ehr = max(1.00, min(1.40, m_ehr))

        coupled_risk = round(min(99.0, self.physiological_instability_score * m_ehr), 1)
        tier = "HIGH" if m_ehr >= 1.25 else ("MODERATE" if m_ehr >= 1.10 else "LOW")

        return {
            "ehr_multiplier": round(m_ehr, 2),
            "coupling_flags": coupling_flags,
            "flag_messages": flag_messages,
            "beta_blockade_active": is_beta_blocker,
            "beta_blockade_escape": has_escape,
            "vulnerability_tier": tier,
            "ehr_coupled_risk_index": coupled_risk
        }

    def compute_proactive_forecast(self) -> Dict[str, Any]:
        """
        Proactive 2-Hour / 6-Hour Early Warning Forecaster & 7-Day Trend Context (Phase 3.2)
        Deterministically synthesizes patient-specific 7-day wearable trajectories from
        EHR vitals, labs, lifestyle, and live optical telemetry.
        """
        v = self.patient.get("vitals", {})
        l = self.patient.get("labs", {})
        s = self.patient.get("lifestyle", {})
        age = float(self.patient.get("age", 50))
        base_hr = float(v.get("resting_hr", 72.0))
        hba1c = float(l.get("hba1c", 5.4))
        hs_crp = float(l.get("hs_crp", 1.0))
        activity = str(s.get("physical_activity", "Moderate")).lower()

        # Deterministic patient-specific seed (zero randomness across reloads, unique per patient)
        pid_num = sum((idx + 1) * ord(ch) for idx, ch in enumerate(str(self.patient_id)))

        # EHR-derived physiological starting points (Day 1)
        base_rmssd = max(18.0, min(62.0, 54.0 - (age - 30.0) * 0.32 - (4.5 if hba1c >= 7.0 else 0.0) - (3.5 if hs_crp > 2.0 else 0.0)))
        base_sleep = max(72.0, min(95.0, 91.0 - (age - 30.0) * 0.12 - (3.5 if s.get("smoker") else 0.0)))
        if "active" in activity and "sedentary" not in activity:
            base_steps = 8400 + (pid_num % 1400)
        elif "sedentary" in activity:
            base_steps = 3800 + (pid_num % 1100)
        else:
            base_steps = 6100 + (pid_num % 1300)

        # EHR Coupling & Drift Severity
        coupling = self._compute_ehr_vulnerability_coupling(
            bpm=self.current_vitals.get("bpm"),
            rmssd=self.current_vitals.get("rmssd"),
            rr_cv=self.current_vitals.get("signal_gate", {}).get("rr_cv") if isinstance(self.current_vitals.get("signal_gate"), dict) else None,
            pred_rhythm=self.current_vitals.get("arrhythmia_predicted", "Normal")
        )
        m_ehr = coupling["ehr_multiplier"]

        is_drifting = (self.base_risk_score >= 20.0) or (self.physiological_instability_score >= 40.0) or (m_ehr >= 1.18)
        daily_hr_slope = (0.9 + 0.5 * (m_ehr - 1.0) * 4.0) if is_drifting else 0.0
        daily_rmssd_slope = (-2.1 - 1.2 * (m_ehr - 1.0) * 4.0) if is_drifting else 0.15
        daily_sleep_slope = -2.2 if is_drifting else 0.1
        daily_step_slope = -480 if is_drifting else 45

        daily_resting_hr, nocturnal_rmssd, sleep_efficiency, daily_steps = [], [], [], []
        for day in range(7):
            wave_jit = ((pid_num + day * 7) % 5 - 2) * 0.4
            hr_d = int(round(max(46.0, min(115.0, base_hr + day * daily_hr_slope + wave_jit))))
            rmssd_d = round(max(10.0, min(75.0, base_rmssd + day * daily_rmssd_slope - wave_jit * 0.8)), 1)
            sleep_d = round(max(58.0, min(97.0, base_sleep + day * daily_sleep_slope + wave_jit * 0.5)), 1)
            steps_d = int(max(1200, base_steps + day * daily_step_slope + int(wave_jit * 180)))

            daily_resting_hr.append(hr_d)
            nocturnal_rmssd.append(rmssd_d)
            sleep_efficiency.append(sleep_d)
            daily_steps.append(steps_d)

        # Anchor Day 7 to live validated telemetry when active
        live_bpm = self.current_vitals.get("bpm")
        live_rmssd = self.current_vitals.get("rmssd")
        if self.data_source in ("LIVE_HARDWARE", "SIMULATION") and live_bpm is not None and live_bpm > 0:
            daily_resting_hr[-1] = int(round(float(live_bpm)))
        if self.data_source in ("LIVE_HARDWARE", "SIMULATION") and live_rmssd is not None and live_rmssd > 0:
            nocturnal_rmssd[-1] = round(float(live_rmssd), 1)

        delta_rmssd_7d = nocturnal_rmssd[-1] - nocturnal_rmssd[0]
        slope_7d = max(0.0, -delta_rmssd_7d * 0.6)

        # Baseline acute instability
        i_t = float(self.physiological_instability_score)
        if self.current_vitals and self.current_vitals.get("personal_instability"):
            p_score = self.current_vitals["personal_instability"].get("instability_score")
            if p_score is not None:
                i_t = float(p_score)

        # Velocity across recent history (Fixed key: "instability_score")
        delta_i_recent = 0.0
        if len(self.risk_history) >= 3:
            delta_i_recent = float(
                self.risk_history[-1].get("instability_score", i_t) - self.risk_history[-3].get("instability_score", i_t)
            )

        pred_2h = max(0.0, min(100.0, i_t + (0.5 * delta_i_recent + 0.4 * slope_7d) * m_ehr))
        pred_6h = max(0.0, min(100.0, i_t + (1.2 * delta_i_recent + 1.1 * slope_7d) * m_ehr))

        if pred_2h >= 70.0 or i_t >= 70.0:
            horizon_status = "IMMINENT_DECOMPENSATION_2H"
        elif pred_6h >= 60.0:
            horizon_status = "HIGH_RISK_WITHIN_6H"
        elif pred_6h >= 35.0 or len(coupling["coupling_flags"]) > 0:
            horizon_status = "EARLY_PRODROMAL_DRIFT"
        else:
            horizon_status = "STABLE_HORIZON"

        if pred_6h >= 70.0 and pred_6h > i_t:
            rate_per_hr = (pred_6h - i_t) / 6.0
            hrs = (70.0 - i_t) / max(0.5, rate_per_hr)
            time_to_thresh = round(max(0.5, min(12.0, hrs)), 1)
        elif i_t >= 70.0:
            time_to_thresh = 0.0
        else:
            time_to_thresh = None

        if horizon_status in ("IMMINENT_DECOMPENSATION_2H", "HIGH_RISK_WITHIN_6H"):
            cur_bpm = round(self.current_vitals.get("bpm") or base_hr)
            pct_drop = abs(delta_rmssd_7d) / max(1.0, nocturnal_rmssd[0]) * 100.0
            narrative = (
                f"7-day nocturnal RMSSD decline ({nocturnal_rmssd[0]:.1f}ms -> {nocturnal_rmssd[-1]:.1f}ms, -{pct_drop:.0f}%) "
                f"combined with acute pulse response ({cur_bpm} BPM, M_EHR={m_ehr:.2f}x) projects high-risk hemodynamic "
                f"instability within {time_to_thresh or 2.5} hours."
            )
        elif horizon_status == "EARLY_PRODROMAL_DRIFT":
            flags_str = ", ".join(coupling["coupling_flags"]) if coupling["coupling_flags"] else "subtle autonomic drift"
            narrative = f"Early prodromal autonomic drift detected: nocturnal vagal trend ({nocturnal_rmssd[0]:.1f}ms -> {nocturnal_rmssd[-1]:.1f}ms) with {flags_str} indicates physiological vulnerability within 6 hours."
        else:
            narrative = f"7-day longitudinal trends (Resting HR ~{daily_resting_hr[-1]} BPM, Nocturnal RMSSD {nocturnal_rmssd[-1]:.1f}ms) demonstrate stable autonomic balance. No acute decompensation projected within 6 hours."

        return {
            "wearable_7d_summary": {
                "daily_resting_hr_7d": daily_resting_hr,
                "nocturnal_rmssd_7d": nocturnal_rmssd,
                "sleep_efficiency_pct_7d": sleep_efficiency,
                "daily_steps_7d": daily_steps
            },
            "predicted_instability_2h": round(pred_2h, 1),
            "predicted_instability_6h": round(pred_6h, 1),
            "adverse_event_horizon_status": horizon_status,
            "estimated_time_to_threshold_hrs": time_to_thresh,
            "forecast_narrative": narrative,
            "ehr_coupling": coupling
        }

    def simulate_treatment(self, modifications: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dual-Horizon Clinical Treatment Outcome Simulator (Phase 4.1)
        Distinguishes active EHR medications from new prescriptions.
        Provides both:
          1. 10-Year ASCVD Risk & Vascular Age projections (Long-Term Horizon)
          2. 24-Hour Hemodynamic & Vagal recovery projections (Short-Term Horizon)
        """
        virtual_patient = json.loads(json.dumps(self.patient))
        v = virtual_patient.get("vitals", {})
        l = virtual_patient.get("labs", {})
        s = virtual_patient.get("lifestyle", {})

        # Active EHR medications
        active_meds = self.patient.get("clinical_history", {}).get("medications", [])
        active_med_names = [m.get("name", "").lower() for m in active_meds]
        active_med_classes = [m.get("class", "").lower() for m in active_meds]

        # Apply lifestyle modifications
        if "systolic_bp" in modifications:
            v["systolic_bp"] = float(modifications["systolic_bp"])
        if "smoker" in modifications:
            s["smoker"] = bool(modifications["smoker"])
        if "total_cholesterol" in modifications:
            l["total_cholesterol"] = float(modifications["total_cholesterol"])
        if "hba1c" in modifications:
            l["hba1c"] = float(modifications["hba1c"])

        added_meds = modifications.get("add_medications", [])
        hr_reduction = 0.0
        bp_reduction = 0.0
        chol_reduction_pct = 0.0
        sglt2_applied = False
        interventions_applied = []

        is_already_on_bb = any("metoprolol" in nm or "beta" in cl for nm, cl in zip(active_med_names, active_med_classes))
        is_already_on_statin = any("statin" in nm or "statin" in cl for nm, cl in zip(active_med_names, active_med_classes))
        is_already_on_ace_arb = any("telmisartan" in nm or "ramipril" in nm or "arb" in cl or "ace" in cl for nm, cl in zip(active_med_names, active_med_classes))

        for med in added_meds:
            med_lower = med.lower()
            if "metoprolol" in med_lower or "beta" in med_lower:
                hr_reduction += 12.0
                bp_reduction += 8.0
                if is_already_on_bb:
                    interventions_applied.append("Beta-blocker Adherence & Titration (Metoprolol 50mg: ~8 mmHg SBP, ~12 BPM reduction)")
                else:
                    interventions_applied.append("Beta-blocker (Metoprolol 25-50mg: ~8 mmHg SBP, ~12 BPM reduction)")
            elif "statin" in med_lower or "atorvastatin" in med_lower:
                chol_reduction_pct += 0.28
                if is_already_on_statin:
                    interventions_applied.append("Statin Adherence & Titration (Atorvastatin 40mg: ~28% total cholesterol reduction)")
                else:
                    interventions_applied.append("Moderate-intensity statin (Atorvastatin 20mg: ~28% total cholesterol reduction)")
            elif "ramipril" in med_lower or "telmisartan" in med_lower or "ace" in med_lower or "arb" in med_lower:
                bp_reduction += 12.0
                v["bp_treated"] = True
                if is_already_on_ace_arb:
                    interventions_applied.append("ACE-inhibitor / ARB Optimization (Telmisartan 40mg: ~12 mmHg SBP reduction)")
                else:
                    interventions_applied.append("ACE-inhibitor / ARB (Telmisartan 40mg: ~12 mmHg SBP reduction)")
            elif "dapagliflozin" in med_lower or "sglt2" in med_lower or "empagliflozin" in med_lower:
                sglt2_applied = True
                bp_reduction += 4.0
                interventions_applied.append("SGLT2 Inhibitor (Dapagliflozin 10mg: -18% CVD event risk in T2DM/CAD, ~4 mmHg SBP)")
            elif "glycemic" in med_lower or "hba1c" in med_lower:
                interventions_applied.append("Glycemic Optimization (Target HbA1c < 6.5%: -10% relative microvascular CVD risk)")

        current_sbp = float(self.patient.get("vitals", {}).get("systolic_bp", 125))
        base_sbp = float(modifications["systolic_bp"]) if "systolic_bp" in modifications else current_sbp
        v["systolic_bp"] = max(90.0, base_sbp - bp_reduction)

        current_chol = float(self.patient.get("labs", {}).get("total_cholesterol", 190))
        base_chol = float(modifications["total_cholesterol"]) if "total_cholesterol" in modifications else current_chol
        l["total_cholesterol"] = max(110.0, base_chol * (1.0 - chol_reduction_pct))

        current_hr = float(self.current_vitals.get("bpm") if self.current_vitals.get("bpm") is not None else self.patient.get("vitals", {}).get("resting_hr", 72.0))
        simulated_hr = max(50.0, current_hr - hr_reduction)

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
        if sglt2_applied:
            # SGLT2i trial meta-analysis (EMPA-REG / DAPA-HF): 18% relative CVD risk reduction
            sim_base_risk = round(sim_base_risk * 0.82, 1)

        risk_reduction_pct = round(self.base_risk_score - sim_base_risk, 1)

        # 24-Hour Hemodynamic Twin Response
        rmssd_gain = 0.0
        if hr_reduction > 0:
            rmssd_gain += 8.5
        if not s.get("smoker", True) and self.patient.get("lifestyle", {}).get("smoker", False):
            rmssd_gain += 4.5

        projected_instability = max(5.0, self.physiological_instability_score - (risk_reduction_pct * 0.6) - (rmssd_gain * 0.4))

        return {
            "original_base_risk": self.base_risk_score,
            "current_baseline_risk": self.base_risk_score,
            "projected_base_risk": sim_base_risk,
            "simulated_baseline_risk": sim_base_risk,
            "projected_risk": sim_base_risk,
            "absolute_risk_reduction": risk_reduction_pct,
            "projected_vascular_age": sim_risk_data["vascular_age"],
            "current_heart_rate": round(current_hr, 1),
            "simulated_heart_rate": round(simulated_hr, 1),
            "current_systolic_bp": round(current_sbp, 1),
            "simulated_systolic_bp": round(v["systolic_bp"], 1),
            "projected_rmssd_gain_ms": round(rmssd_gain, 1),
            "projected_instability_score": round(projected_instability, 1),
            "active_ehr_medications": active_meds,
            "time_horizon": "Dual Horizon: 24-Hour Hemodynamic Response + 10-Year ASCVD Risk Reduction",
            "interventions_applied": interventions_applied,
            "clinical_summary": f"Estimated {abs(risk_reduction_pct)}% {'reduction' if risk_reduction_pct >= 0 else 'increase'} in 10-year CVD risk with sustained adherence. Projected vascular age: {sim_risk_data['vascular_age']} years. 24h resting pulse projected at {simulated_hr:.0f} BPM with +{rmssd_gain:.1f}ms vagal gain.",
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

        # Compute dynamic cardiovascular biological age
        cv_age_eval = None
        try:
            try:
                from framingham_risk import compute_cardiovascular_age
            except ImportError:
                from backend.framingham_risk import compute_cardiovascular_age
            vasc_age = self.patient.get("cardiovascular_risk", {}).get("vascular_age", self.patient.get("age", 50))
            cv_age_eval = compute_cardiovascular_age(
                chronological_age=self.patient.get("age", 50),
                vascular_age=vasc_age,
                resting_bpm=self.current_vitals.get("bpm"),
                rmssd=self.current_vitals.get("rmssd")
            )
        except Exception:
            cv_age_eval = None

        # Compute proactive horizon forecast and EHR coupling (Phase 3)
        forecast = self.compute_proactive_forecast()

        return {
            "patient_id": self.patient_id,
            "patient_name": self.name,
            "status_label": status_label,
            "data_source": self.data_source,
            "physiological_instability_score": self.physiological_instability_score,
            "current_dynamic_risk": self.current_dynamic_risk, # Backwards-compatible alias
            "base_clinical_risk": self.base_risk_score,
            "baseline_10yr_cvd_risk_pct": self.base_risk_score,
            "cardiovascular_age": cv_age_eval,
            "proactive_forecast": forecast,
            "ehr_coupling": forecast["ehr_coupling"],
            "personal_instability": self.current_vitals.get("personal_instability"),
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
