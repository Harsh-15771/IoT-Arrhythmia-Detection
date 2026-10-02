# CardioTwin Architecture Specification

## 1. System Vision & Product Definition
**CardioTwin** is an evidence-aware cardiovascular digital twin that fuses longitudinal patient EHR data with real-time wearable optical telemetry (PPG) to track physiological instability, screen for cardiac dysrhythmias, and simulate long-term pharmacological outcomes.

```
                      +------------------------------------------+
                      |         STREAM 1: PATIENT EHR            |
                      | Demographics, Vitals, Labs, Lifestyle,   |
                      | 10-Yr Framingham CVD Risk (D'Agostino)   |
                      +--------------------+---------------------+
                                           |
                                           v
+------------------------+      +--------------------+      +-------------------------+
| STREAM 2: IoT SENSORS  | ---> |   MULTIMODAL FUSION| ---> |  INTERACTIVE CLINICIAN  |
| ESP32 + MAX30102 PPG   |      |  DIGITAL TWIN CORE |      |        DASHBOARD        |
| 100 Hz Optical Pulse   |      | Layer 1: Base CVD  |      | Dynamic Trajectory      |
| SQI Artifact Rejection | ---> | Layer 2: Instability| ---> | What-If Simulator       |
| 27 Biomarkers + XGBoost|      | Layer 3: EMA State |      | Alert Auditing Panel    |
+------------------------+      +--------------------+      +-------------------------+
```

---

## 2. The Two Complementary Clinical Streams

### Stream 1: Longitudinal Cardiometabolic State (Layer 1)
- **Clinical Baseline:** Computed using the sex-specific Framingham 10-Year General Cardiovascular Disease Risk Profile (D'Agostino et al., *Circulation* 2008).
- **Inputs:** Age, Gender, Systolic Blood Pressure (treated vs untreated), Total Cholesterol, HDL-C, Smoking status, Type-2 Diabetes.
- **Exploratory South Asian Recalibration:** Applies a 1.45× adjustment factor supported by Indian epidemiological data (Bansal et al., 2020; Garg et al., 2017) to account for earlier-onset coronary disease in the South Asian diaspora.
- **Boundary Guardrails:** Evaluated between ages 30 and 74; outside this range, risks are extrapolated with explicit clinical flags (`age_extrapolated: True`).

### Stream 2: High-Frequency Continuous Telemetry (Layer 2)
- **Sensor Hardware:** ESP32 Microcontroller paired with a MAX30102 high-sensitivity reflective pulse oximetry sensor sampling at 100 Hz.
- **Edge Preprocessing:** Real-time pulse detection, peak tracking, IBI calculation, and local OLED rendering.
- **Ingestion Contract:** Transmits HTTP JSON payloads with dual key support (`values` and `samples`) to `/data` and `/ingest_telemetry`, while synchronizing state via `/command`.
- **Signal Quality Index (SQI) Safety Gating:** Optical signals with $SQI < 0.40$ or standard deviation $\sigma < 0.05$ are gated out to suppress spurious motion-induced alarms.
- **27 Extracted Biomarkers:** 10-second sliding windows extract time-domain HRV (RMSSD, SDNN, pNN50, pNN20), morphology (pulse width, peak amplitude CV), and Welch spectral densities (LF, HF, LF/HF ratio).
- **Rhythm Screening Core (v3 Authoritative):** 8-class XGBoost classifier (`Normal`, `Tachycardia`, `Bradycardia`, `AFib`, `Cardiac_Paced`, `V_Tachycardia`, `V_Flutter_Fib`, `Asystole`) trained with leak-free `StratifiedGroupKFold` across **2,271 unique patients (4,683 windows)**, grounded in 2,000 real MIMIC-III ICU patients, PhysioNet CinC 2015 true alarms, and BUT PPG optical noise recordings. Framed as an investigational screening prototype.

---

## 3. Evidence-Aware Dynamic State Fusion (Layer 3)
Rather than conflating a 10-year statistical probability with acute sensor fluctuations into an unscientific single metric, CardioTwin maintains two distinct clinical tiers:

1. **Baseline 10-Year CVD Risk ($\%$):** Reflects long-term atherosclerotic and vascular risk.
2. **Real-Time Physiological Instability Score ($0 - 100$):** A dynamic composite score combining:
   - Acute rhythm distress ($\text{Pr}(\text{Non-Normal Rhythm}) \times 45.0$)
   - Parasympathetic withdrawal / autonomic stress (penalties for RMSSD $< 25\,\text{ms}$)
   - Hemodynamic perturbation (tachycardia $> 105\,\text{BPM}$ or severe bradycardia)
   - Peripheral hypoxia (penalties for $\text{SpO}_2 < 94\%$)
   - Stabilized with exponential moving average smoothing ($\alpha = 0.35$).

---

## 4. Interactive "What-If" Treatment Outcome Simulator
Enables clinicians to model the projected impact of pharmacological and lifestyle therapies under sustained adherence (5–10 year horizon):
- **Statin Therapy (Atorvastatin 20mg):** Models a ~28% reduction in total cholesterol / LDL-C based on ACC/AHA trial meta-analyses.
- **Antihypertensive Therapy (Telmisartan 40mg):** Models a 12 mmHg reduction in systolic blood pressure.
- **Beta-Blockade (Metoprolol 25–50mg):** Models an 8 mmHg SBP reduction and 12 BPM heart rate reduction.
- **Smoking Cessation:** Recomputes Framingham risk eliminating the tobacco hazard.
- **Time Horizon Transparency:** Clearly labeled as projected 5–10 year risk reduction under sustained adherence — not an acute or instant drug effect.

---

## 5. Clinician Dashboard & Telemetry Architecture
- **Backend:** Python Flask + Flask-SocketIO event loop running on port 5000.
- **Frontend:** Modern responsive React + Vite application featuring glassmorphic telemetry cards, real-time Canvas PPG pulse waveform rendering, dynamic SVG risk gauges, and patient switching.
- **Data Provenance Indicators:** Explicit status tags identify the active data source:
  - `[LIVE_HARDWARE]` — Incoming ESP32 telemetry.
  - `[RECORDED_REPLAY]` — Replayed session CSV.
  - `[SIMULATION]` — Simulated clinical scenario.
- **Clinical Safety Disclaimers:** Visible screening alerts informing clinicians that all PPG findings require diagnostic 12-lead ECG review.
