# 🔒 Privacy-Preserving & Federated-Ready Architecture Specification

**CardioTwin Sentinel Data Protection & Governance Architecture**  
**Standards:** Digital Personal Data Protection Act (DPDP 2023, India), HIPAA Security Rule, ABDM Consent Framework, Federated Learning (FedAvg)

---

## 1. Edge-First Personal Calibration (Zero Raw Waveform Leakage)

Traditional digital health solutions stream continuous physiological recordings to centralized cloud databases, exposing patients to privacy vulnerabilities and high bandwidth overhead. CardioTwin Sentinel enforces a strict **Edge-First Data Boundary**:

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
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Privacy Guarantees:
1. **Raw PPG Waveform Ephemerality:** Continuous microvascular photoplethysmograms are processed in rolling circular memory buffers and discarded after quality and feature extraction. No raw waveforms are permanently stored on cloud disks.
2. **Deterministic Pseudonymization:** All synthetic and clinical cohort records use de-identified patient handles (`PAT001`, `PAT002`) with decoupled electronic health record (EHR) demographics.
3. **No Biometric Fingerprinting:** Unlike facial recognition or voiceprints, personal baseline parameters (e.g. `median_bpm: 68.0`, `mad_bpm: 2.8`) cannot be reverse-engineered to identify a citizen without explicit ABHA linked metadata.

---

## 2. Federated Learning (FL) Readiness

CardioTwin Sentinel is architected to support **Federated Learning (FedAvg / FedProx)** across regional primary health networks (such as Ayushman Bharat HWCs and district hospitals) without aggregating sensitive clinical data:

### Architectural Workflow:
1. **Local Node Model Execution:** Each participating district clinic or edge gateway runs the unified dual-modality pipeline locally on its population cohort.
2. **Local Gradient & Loss Calculation:** Edge nodes compute weight gradients for the Inception-1D CNN or tree splits for the Classical Ensemble on verified local clinical cases.
3. **Secure Differential Privacy Aggregation:** Only encrypted model weight updates ($\Delta W$) with added Gaussian differential privacy noise ($\epsilon, \delta$) are transmitted to the central CardioTwin coordination server.
4. **Global Model Dispatch:** The updated global model checkpoint is redistributed back to participating nodes, improving screening accuracy on regional cardiac morphologies while keeping all patient health data strictly within local facility walls.

---

## 3. Compliance with India's DPDP Act (2023)

CardioTwin Sentinel adheres to the principles of the **Digital Personal Data Protection Act (DPDP 2023)**:
- **Purpose Limitation:** Pulse waveform telemetry is used strictly for real-time instability screening and clinical decision support.
- **Data Minimization:** Only 27 mathematical biomarkers and stability indices are stored for longitudinal review.
- **Storage Limitation:** Baselines expire after 30 days (`BASELINE_TTL_SECONDS = 30 * 86400`), enforcing automated purging and empirical recalibration.
- **Patient Autonomy:** Patients can cancel active calibration (`POST /baseline/cancel`) or reset signal gates (`POST /signal/gate/reset`) at any time.

---

*Authored for the Digital Twin Challenge 2026 / Happiest Health by the CardioTwin Sentinel Engineering Team.*
