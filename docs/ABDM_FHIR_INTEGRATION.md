# 🏥 Ayushman Bharat Digital Mission (ABDM) & HL7 FHIR Integration Architecture

**CardioTwin Sentinel Interoperability Specification**  
**Standards:** HL7 FHIR R4, National Health Authority (NHA) India, LOINC, SNOMED-CT, ABDM Milestone M1/M2/M3

---

## 1. Overview & Regulatory Context

The **Ayushman Bharat Digital Mission (ABDM)**, established by the National Health Authority (NHA) of India, creates a unified digital health backbone for the country. Digital health solutions must avoid data silos and comply with **HL7 FHIR Release 4 (R4)** standards to enable seamless longitudinal health record sharing across public and private hospitals, primary health centres, and diagnostic laboratories.

CardioTwin Sentinel is designed from the ground up with an **open, FHIR-ready data architecture**. Every telemetry session, baseline calibration, and What-If scenario export maps directly to standardized FHIR resources linked to the citizen's **14-digit ABHA (Ayushman Bharat Health Account) ID**.

---

## 2. HL7 FHIR R4 Resource Mapping

| CardioTwin Sentinel Artifact | FHIR R4 Resource | Standard Coding System | Code & Display |
|:---|:---|:---|:---|
| **Resting Heart Rate (BPM)** | `Observation` | LOINC | `8867-4` ("Heart rate") |
| **Pulse Rate Variability (RMSSD)** | `Observation` | LOINC | `80404-7` ("R-R interval.standard deviation") |
| **Pulse Irregularity (RR-CV)** | `Observation` | SNOMED-CT | `361137007` ("Pulse rhythm finding") |
| **Personal Instability Index (0–100)** | `Observation` | Custom Extension | `ext-cardiotwin-instability-index` |
| **Recalibrated Framingham 10-Yr CVD Risk** | `RiskAssessment` | LOINC / SNOMED-CT | `79423-0` ("Cardiovascular disease 10Y risk") |
| **Screening Waveform Pattern (AFib/Tachy)** | `Observation` (or `Condition`) | SNOMED-CT | `49436004` ("Atrial fibrillation") |
| **Hardware Node Provenance** | `Device` | IEEE 11073 / GMDN | `cardiotwin-esp32-01` (Firmware v4.1.0) |

---

## 3. Sample FHIR R4 Export Bundle

When a clinician clicks **"Export Clinician Report"** in the CardioTwin Sentinel dashboard, the system can emit an ABDM-compliant FHIR `Bundle` (Type: `transaction` or `document`):

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
        "identifier": [
          {
            "system": "https://healthid.abdm.gov.in",
            "value": "91-8842-1029-4412"
          }
        ],
        "name": [{ "text": "Ramesh Patel" }],
        "gender": "male",
        "birthDate": "1971-04-12"
      }
    },
    {
      "fullUrl": "urn:uuid:device-sensor-001",
      "resource": {
        "resourceType": "Device",
        "id": "cardiotwin-esp32-node",
        "manufacturer": "CardioTwin Open Health Initiative",
        "modelNumber": "ESP32-MAX30102-v4.1",
        "version": [{ "value": "FreeRTOS DualCore 4.1.0" }],
        "type": {
          "coding": [{
            "system": "http://snomed.info/sct",
            "code": "466093004",
            "display": "Photoplethysmography sensor"
          }]
        }
      }
    },
    {
      "fullUrl": "urn:uuid:obs-instability-001",
      "resource": {
        "resourceType": "Observation",
        "status": "final",
        "category": [{
          "coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs"
          }]
        }],
        "code": {
          "coding": [{
            "system": "https://cardiotwin.org/fhir/codes",
            "code": "CARDIOTWIN-INSTABILITY",
            "display": "Cardiovascular Baseline Instability Index"
          }]
        },
        "subject": { "reference": "urn:uuid:patient-abha-001" },
        "effectiveDateTime": "2026-10-05T11:21:47+05:30",
        "valueQuantity": {
          "value": 14.2,
          "unit": "index (0-100)",
          "system": "http://unitsofmeasure.org",
          "code": "1"
        },
        "interpretation": [{
          "coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
            "code": "N",
            "display": "Stable within personal resting band"
          }]
        }],
        "note": [{
          "text": "Baseline calibrated at seated rest with 6 valid windows. Signal reliability verified by 5-part decoupled gate."
        }]
      }
    }
  ]
}
```

---

## 4. Privacy, Consent Management & Data Governance

1. **Local Calibration Privacy:** The 2-minute resting baseline calibration occurs **entirely on the local node/edge**. Raw high-frequency (100 Hz) optical PPG waveforms are discarded after feature extraction; only aggregated summary statistics (median BPM, MAD, RR-CV) are stored.
2. **Electronic Health Record (EHR) Consent Architecture:** Compliant with India's **Digital Personal Data Protection Act (DPDP 2023)** and ABDM Consent Manager (CM). Data sharing with district clinicians or tele-consultation portals requires explicit, time-bounded patient OTP consent via the ABHA network.

---

*Authored for the Digital Twin Challenge 2026 / Happiest Health by the CardioTwin Sentinel Engineering Team.*
