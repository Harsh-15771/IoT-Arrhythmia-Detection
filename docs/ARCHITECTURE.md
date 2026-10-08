# 🏛️ CardioTwin Sentinel — End-to-End System Architecture

**Comprehensive Technical Reference: Hardware, Telemetry Flow, Edge Computing, Privacy, and Interoperability**  
**Version:** 4.1.0-sentinel | **Target Context:** Primary Care Screening & Ayushman Bharat Health & Wellness Centres (AB-HWCs)

---

## 1. System Overview & Dual Clinical Streams

CardioTwin Sentinel is an evidence-aware cardiovascular digital twin that fuses longitudinal electronic health records (EHR) with high-frequency wearable optical telemetry (PPG) to track physiological instability, screen for dysrhythmias, and simulate pharmacological outcomes.

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

### Stream 1: Longitudinal Cardiometabolic State (Layer 1)
- **Clinical Baseline:** Sex-specific Framingham 10-Year General CVD Risk (D'Agostino et al., *Circulation* 2008).
- **Inputs:** Age, Gender, Systolic Blood Pressure (treated/untreated), Total Cholesterol, HDL-C, Smoking status, Type-2 Diabetes.
- **South Asian Calibration:** $1.45\times$ multiplier applied for South Asian diaspora (see [`CLINICAL_EVALUATION.md`](CLINICAL_EVALUATION.md)).
- **Guardrails:** Validated ages 30–74; outside this range, flagged with `age_extrapolated: true`.

### Stream 2: High-Frequency Continuous Telemetry (Layer 2)
- **Sensor Hardware:** ESP32 SoC + MAX30102 reflective pulse oximeter sampling at 100 Hz.
- **Edge Preprocessing:** Hardware ISR peak tracking, inter-beat interval (IBI) calculation, OLED rendering.
- **Signal Quality Gate (SQI):** Rejects signals with $SQI < 0.40$ or $\sigma < 0.05$ to suppress motion artifacts while preserving genuine arrhythmias.
- **27 Extracted Biomarkers:** 10-second sliding windows extract time-domain HRV (RMSSD, SDNN, pNN50, pNN20), morphology (pulse width, peak amp CV), and Welch spectral densities (LF, HF).
- **Rhythm Screening Core:** 8-class dual-modality model (`Normal`, `Tachycardia`, `Bradycardia`, `AFib`, `Cardiac_Paced`, `V_Tachycardia`, `V_Flutter_Fib`, `Asystole`) evaluated under patient-isolated GroupKFold (see [`MODEL_CARD.md`](MODEL_CARD.md)).

### Stream 3: Evidence-Aware Dynamic State Fusion (Layer 3)
Instead of conflating 10-year risk with acute fluctuations into a single unscientific number, CardioTwin maintains two distinct metrics:
1. **Baseline 10-Year CVD Risk (%):** Long-term atherosclerotic risk.
2. **Real-Time Instability Score (0–100):** Dynamic composite combining:
   - Acute rhythm distress: $\Pr(\text{Non-Normal}) \times 45.0$
   - Autonomic withdrawal: penalties for $\text{RMSSD} < 25\text{ ms}$
   - Hemodynamic perturbation: $\text{BPM} > 105$ or severe bradycardia
   - Hypoxia penalty: $\text{SpO}_2 < 94\%$
   - Smoothed via Exponential Moving Average ($\alpha = 0.35$).

---

## 2. Key Engineering Decisions & Rationale

| Decision | Alternative Considered | Engineering & Clinical Rationale |
|:---|:---|:---|
| **Dual-Modality Fusion** (Classical 38% + CNN 62%) | Single CNN or single tabular model | Combines explicit HRV physiological statistics (RMSSD, LF/HF) with raw micro-morphological wave features. Yields **53.92% Macro-F1** vs 51.81% (CNN) and 48.00% (Classical). |
| **Inception-1D CNN Architecture** | ResNet-1D, LSTM, Transformers | Concurrently extracts multi-scale temporal dynamics (systolic peaks, dicrotic notch, respiratory arrhythmia) across 4 kernel sizes (3, 7, 15, 31). Fast CPU inference (~4.2 ms / window, 393k params). |
| **Personal Seated Baseline** | Universal population norms (72 BPM) | Resting pulse varies biologically (48 BPM in athletes vs 84 BPM in hypertension). Optical PRV agrees with ECG HRV at seated rest. System returns `null` until 2-minute baseline is established. |
| **Median + MAD Departure Scoring** | Mean + Standard Deviation | Non-parametric statistics possess a 50% breakdown point, resisting transient sensor spikes or ectopic beats that distort sample mean and variance. |
| **Framingham + $1.45\times$ South Asian Recalibration** | Unadjusted Western Framingham | Addresses 10–15 year earlier onset of CAD in South Asians (INTERHEART, QRISK3, ACC/AHA guidelines). |

---

## 3. Hardware Architecture & Bill of Materials (BOM)

The hardware node runs FreeRTOS dual-core tasking: **Core 1** dedicated to 100 Hz optical sampling via hardware ISR timer; **Core 0** handles WiFi TCP/IP socket streaming and OLED updates.

### Hardware BOM Breakdown

| Component | Part & Specification | Cost (INR ₹) | Cost (USD $) | Key Function | Sourcing |
|:---|:---|:---:|:---:|:---|:---|
| **Microcontroller** | ESP32-WROOM-32D Dual-Core (240 MHz, 520 KB SRAM) | ₹480 | $5.80 | Dedicated FreeRTOS dual-core sampling & telemetry | Robu.in / Mouser |
| **Optical Pulse Sensor** | MAX30102 PPG Subsystem (Maxim/ADI) | ₹220 | $2.65 | Integrated LED + Photodiode + 18-bit ADC, programmable 0–50 mA drive | Quartz Components |
| **Local Status Display** | SSD1306 0.96" I2C OLED (128×64) | ₹140 | $1.70 | Real-time BPM, SQI bar, WiFi IP, calibration status | Robu.in |
| **Power Management** | TP4056 USB-C Charger + 3.7V 650mAh LiPo Cell | ₹210 | $2.55 | 6–8 hrs continuous battery operation, rechargeable via mobile adapter | Robu.in |
| **Interconnect & Passives** | 4.7kΩ pull-ups, silicone wire, decoupling caps | ₹35 | $0.42 | Signal conditioning and noise decoupling for high SNR | Local Market |
| **Ergonomic Finger Clip** | 3D-Printed Biocompatible PLA Enclosure + Foam | ₹80 | $0.95 | Ambient light shield & contact pressure stabilization | Rapid Prototyping |
| **Total Unit BOM** | **Complete CardioTwin Sentinel IoT Node** | **₹1,165** | **~$14.07** | **Fully functional IoT pulse screening device with real-time telemetry** | < ₹950 in 1k batch |

### Health-Economics Comparison

| Modality | Capital / Rental Cost | Deployment Barrier | CardioTwin Advantage |
|:---|:---:|:---|:---|
| **Commercial Smartwatch** (Apple Watch) | ₹41,900 – ₹89,900 | High consumer luxury; iOS lock-in; uncalibrated baseline | **>35× cheaper**; open web dashboard; empirical 2-min personal baseline |
| **24–48h Holter Monitor** | ₹5,000 – ₹12,000 / rental | Multi-lead chest electrodes; 2–3 day diagnostic review delay | **Zero-rental cost**; instant continuous departure detection |
| **Hospital Bedside Monitor** | ₹1,20,000 – ₹3,50,000 | Mains-powered, non-portable; requires ICU nursing staff | Ultra-portable (~60g); battery-powered; operable by rural CHOs |
| **OTC Pulse Oximeter** | ₹600 – ₹1,200 | Single instantaneous number; no baseline, zero longitudinal memory | Tracks **longitudinal stability**, detects sustained departures |

---

## 4. Privacy-Preserving & Edge-First Architecture

CardioTwin Sentinel enforces an **Edge-First Data Boundary** aligned with India's **Digital Personal Data Protection Act (DPDP 2023)** and HIPAA security standards:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LOCAL CLIENT / EDGE NODE                          │
│                                                                             │
│  [1] MAX30102 Optical Sensor (100 Hz Raw PPG Waveform)                      │
│             │                                                               │
│             ▼                                                               │
│  [2] Decoupled 5-Part Signal Reliability Gate                               │
│             │                                                               │
│             ▼                                                               │
│  [3] Feature Extraction (27 Biomarkers: Median, MAD, RR-CV, RMSSD, SQI)     │
│             │                                                               │
│             ▼                                                               │
│  [4] Personal Baseline Synthesis (Local Storage in client baseline JSON)    │
│             │                                                               │
│             ├───► [Raw 100 Hz Waveforms Immediately Discarded from RAM]     │
│             │                                                               │
│             ▼                                                               │
│  [5] Transmitted Payload: Only Aggregate Feature Vectors & Departure Flags  │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Waveform Ephemerality:** Raw 100 Hz waveforms reside only in rolling circular memory buffers and are purged after feature extraction. No raw waveforms are stored on cloud disks.
- **Deterministic Pseudonymization:** Patient handles (`PAT001`, `PAT002`) remain decoupled from identifiable demographic registries.
- **Federated Learning (FL) Readiness:** Architecture supports local gradient computation on edge gateways with encrypted weight updates ($\Delta W$) sent to coordination servers via FedAvg/FedProx, preserving patient data locality.
- **Storage Lifecycle:** Baselines enforce an automated 30-day Time-To-Live (`BASELINE_TTL_SECONDS = 30 * 86400`) requiring periodic recalibration.

---

## 5. ABDM & HL7 FHIR R4 Integration

Every telemetry session, calibrated baseline, and What-If scenario maps directly to **HL7 FHIR Release 4 (R4)** resources linked to the citizen's 14-digit **Ayushman Bharat Health Account (ABHA)** ID:

### FHIR R4 Resource Mapping

| CardioTwin Observation | FHIR Resource | Coding System | Code & Display |
|:---|:---|:---|:---|
| **Resting Heart Rate** | `Observation` | LOINC | `8867-4` ("Heart rate") |
| **Pulse Rate Variability (RMSSD)** | `Observation` | LOINC | `80404-7` ("R-R interval.standard deviation") |
| **Pulse Rhythm Finding** | `Observation` | SNOMED-CT | `361137007` ("Pulse rhythm finding") |
| **Personal Instability Index** | `Observation` | Custom Extension | `ext-cardiotwin-instability-index` |
| **10-Year Framingham CVD Risk** | `RiskAssessment` | LOINC | `79423-0` ("Cardiovascular disease 10Y risk") |
| **Screening Waveform Pattern** | `Observation` | SNOMED-CT | `49436004` ("Atrial fibrillation"), etc. |
| **Hardware Node Device** | `Device` | IEEE 11073 | `cardiotwin-esp32-01` (Firmware v4.1.0) |

### Sample FHIR R4 JSON Export Bundle

```json
{
  "resourceType": "Bundle",
  "id": "cardiotwin-session-bundle-20261005",
  "type": "collection",
  "timestamp": "2026-10-05T11:21:47+05:30",
  "entry": [
    {
      "fullUrl": "urn:uuid:patient-abha-001",
      "resource": {
        "resourceType": "Patient",
        "id": "abha-91-8842-1029-4412",
        "identifier": [{ "system": "https://healthid.abdm.gov.in", "value": "91-8842-1029-4412" }],
        "gender": "male",
        "birthDate": "1971-04-12"
      }
    },
    {
      "fullUrl": "urn:uuid:obs-instability-001",
      "resource": {
        "resourceType": "Observation",
        "status": "final",
        "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs" }] }],
        "code": { "coding": [{ "system": "https://cardiotwin.org/fhir/codes", "code": "CARDIOTWIN-INSTABILITY", "display": "Cardiovascular Baseline Instability Index" }] },
        "valueQuantity": { "value": 14.2, "unit": "index (0-100)", "system": "http://unitsofmeasure.org", "code": "1" },
        "interpretation": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "N", "display": "Stable within personal resting band" }] }]
      }
    }
  ]
}
```

---

## 6. Clinician Dashboard & Telemetry Flow

- **Backend:** Python Flask + Flask-SocketIO event server (Port 5000) orchestrating baseline state, multi-modal model inference, and What-If simulation.
- **Frontend:** Responsive React 19 + Vite dashboard with real-time Canvas oscilloscope rendering, SVG dynamic risk gauges, and session export.
- **Provenance Tags:**
  - `[LIVE_HARDWARE]` — Active streaming from physical ESP32 node.
  - `[RECORDED_REPLAY]` — Real-patient session CSV playback.
  - `[SIMULATION]` — Parameterized clinical stress scenarios.
- **Safety Boundary:** All UI screens display persistent disclaimers that PPG optical screening is non-diagnostic and requires confirmatory 12-lead ECG review.
