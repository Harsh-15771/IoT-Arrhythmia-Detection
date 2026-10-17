# 🫀 CardioTwin Sentinel — Master System Replication Blueprint
> **The Definitive Zero-Guesswork Engineering & Clinical Specification**  
> **Target Project:** CardioTwin Sentinel — Personalized Cardiovascular & Cardiometabolic Digital Twin  
> **Author & Lead Developer:** Harsh Mishra (Team Root Access) · VNIT Nagpur  
> **Target Event:** Digital Twin Challenge 2026 (Happiest Health)  
> **Repository:** `Harsh-15771/IoT-Arrhythmia-Detection` | **License:** MIT License

---

## 1. Executive Summary & Design Philosophy: The "Why"

### 1.1 The Clinical Problem in India
Cardiovascular disease (CVD) causes **28% of all deaths in India**. South Asians experience ischemic heart disease onset **10–15 years earlier** than Western populations (frequently presenting under age 50). India has over **160,000 Ayushman Bharat Health & Wellness Centres (AB-HWCs)** run by Community Health Officers (CHOs), yet primary healthcare facilities possess zero intelligent cardiac screening tools.

Current tools create an unsustainable trilemma:
1. **Consumer Wearables (Apple Watch, etc.):** Cost ₹41,900–₹89,900 (unaffordable for 95% of Indians), proprietary iOS lock-in, uncalibrated static population baselines.
2. **Clinical Holter Monitors:** Cost ₹5,000–₹12,000 per rental, multi-lead chest electrodes, require 2–3 days for manual cardiologist review.
3. **Consumer Pulse Oximeters:** Cost ₹600–₹1,200, but only output an instantaneous number with zero memory, zero personal baseline, and zero risk intelligence.

### 1.2 The CardioTwin Solution
An ultra-low-cost (**₹1,165 / ~$14**) edge IoT node and clinical digital twin that:
1. **Refuses population guessing:** Learns the patient's individual resting baseline via a 2-minute seated empirical calibration (Median + MAD).
2. **Decouples signal gating:** Blocks the AI when physics fails (finger-off, amplifier saturation, timing jitter), but passes genuine physiological arrhythmias (AFib, extreme rates) through to the AI.
3. **Dual-modality AI:** Fuses 27 physiological HRV biomarkers (XGBoost + Random Forest + ExtraTrees) with raw 100 Hz waveforms (Inception-1D CNN) into an 8-class rhythm screening output (**53.92% Macro-F1** across 2,271 patients under zero-leakage GroupKFold).
4. **Longitudinal "What-If" treatment simulator:** Recalibrates Framingham 10-year CVD risk with a $1.45\times$ South Asian multiplier and simulates pharmacological reductions (statins, beta-blockers, ACE inhibitors, smoking cessation).
5. **ABDM & FHIR R4 Ready:** Directly generates HL7 FHIR R4 bundles tagged with 14-digit ABHA IDs for national e-Sanjeevani tele-consultation.

---

## 2. Hardware Architecture & Circuit Schematic

### 2.1 Bill of Materials (BOM) — Total Unit Cost: ₹1,165 (~$14)
| Component | Exact Specification | Purpose | Cost (INR) |
|:---|:---|:---|:---:|
| **Microcontroller** | ESP32-WROOM-32D (Dual-Core Xtensa LX6 @ 240 MHz, 520 KB SRAM) | Core 1: 100 Hz ISR acquisition; Core 0: WiFi HTTP/TCP | ₹480 |
| **Optical Pulse Sensor** | MAX30102 (Maxim / Analog Devices) | Red (660nm) & IR (880nm) LEDs, 18-bit ADC, programmable 0–50mA LED drive | ₹220 |
| **Local Display** | SSD1306 or SH1106 0.96" OLED (128×64, I2C) | Live BPM, Signal Quality Index (SQI) bar, WiFi status, calibration HUD | ₹140 |
| **Power Supply** | TP4056 USB-C Li-Po Charge Module + 3.7V 650mAh Li-Po Cell | 6–8 hours continuous portable battery operation | ₹210 |
| **Enclosure & Clip** | 3D-Printed Biocompatible PLA finger clip + foam optical shield | Ambient light rejection, uniform contact pressure | ₹80 |
| **Wiring & Passives** | 4.7kΩ I2C pullup resistors, bypass capacitors, silicone leads | I2C signal integrity and transimpedance decoupling | ₹35 |
| **TOTAL** | **Complete CardioTwin Sentinel Hardware Node** | **Primary Care Mass Screening Device** | **₹1,165** |

### 2.2 Circuit Wiring Pinout
```
ESP32 DevKit V1                 MAX30102 Pulse Sensor
┌──────────────────┐            ┌──────────────────┐
│             3V3  ├───────────►│ VIN / VCC        │
│             GND  ├───────────►│ GND              │
│  GPIO 21 (SDA)   ├──────┬────►│ SDA              │
│  GPIO 22 (SCL)   ├───┬──┼────►│ SCL              │
│  GPIO 19 (INT)   │   │  │     │ INT (Optional)   │
└──────────────────┘   │  │     └──────────────────┘
                       │  │     SSD1306 / SH1106 OLED (128x64)
                       │  │     ┌──────────────────┐
                       │  └────►│ SDA              │
                       └───────►│ SCL              │
                                │ VCC (3.3V)       │
                                │ GND              │
                                └──────────────────┘
* Note: 4.7kΩ pull-up resistors connect SDA to 3.3V and SCL to 3.3V on the I2C bus.
```

### 2.3 FreeRTOS Dual-Core Task Allocation
- **Core 1 — `sampleTask` (Priority 5, Real-Time ISR):**
  - Configures MAX30102 via `Wire` at 400 kHz Fast I2C.
  - Sensor settings: LED current 6.0 mA, sample rate 100 Hz, pulse width 411 µs, ADC range 18-bit ($262{,}144$ counts).
  - Uses `esp_timer_get_time()` and `vTaskDelayUntil()` to guarantee a hard **10,000 µs (10 ms / 100 Hz)** period ($\pm 0.4$ ms jitter max).
  - Packs samples into thread-safe `PpgChunk` structures (50 samples per chunk = 500 ms).
  - Pushes completed chunks into a FreeRTOS `QueueHandle_t chunkQueue` (capacity: 10 chunks).
  - **Zero network or blocking calls are permitted on Core 1.**
- **Core 0 — `networkTask` (Priority 1, Background):**
  - Connects to Wi-Fi WPA2 (`WiFi.begin(ssid, password)`).
  - Pulls chunks from `chunkQueue`.
  - Serializes chunk payload into JSON:
    ```json
    {
      "device_id": "cardiotwin-esp32-01",
      "device_boot_id": "boot-a8f192b3",
      "seq": 142,
      "first_sample_ms": 1728954000120,
      "sample_count": 50,
      "dropped_buffers": 0,
      "device_bpm": 72.4,
      "values": [128450, 128910, 129400],
      "deltas_us": [10002, 9998, 10005]
    }
    ```
  - Posts payload to backend endpoint `POST /data` or `POST /ingest_telemetry`.
- **OLED UI Loop:** Runs on Core 1 background at ~8 FPS, displaying live pulse curve, calculated BPM, and connection indicator.

---

## 3. Decoupled 5-Part Signal Reliability Gate

### 3.1 Design Philosophy: Decoupled Gating
Traditional systems use a single quality metric and discard signals with irregular rhythms (such as Atrial Fibrillation or Ventricular Tachycardia) as "noisy". CardioTwin strictly separates:
- **Axis 1: Signal Quality Gate (May block AI):** Evaluates physical and optical integrity. Blocks inference when hardware fails.
- **Axis 2: Physiological Observation (Never blocks AI):** Preserves extreme rates and chaotic rhythm patterns for downstream screening.

### 3.2 Gate Checks & Authoritative Thresholds
| Gate Check | Parameter / Formula | Failure Condition | Impact / Action |
|:---|:---|:---|:---|
| **1. Contact Amplitude** | Optical IR raw ADC counts | $\text{ADC} < 20{,}000$ (finger liftoff) | Status: `FINGER_OFF`. Blocks AI. Zero score. |
| **2. Transimpedance Saturation** | Maximum 18-bit ADC ceiling | $\text{ADC} > 260{,}000$ or clipping ratio $> 0.05$ | Status: `SENSOR_SATURATED`. Blocks AI. |
| **3. Sample Timing Jitter** | Standard deviation of timestamp deltas | $\text{Jitter} > 20\%$ or $\Delta t > 25\text{ ms}$ | Status: `POOR_TIMING`. Blocks AI. |
| **4. Pulse Morphology** | Bandpass 0.5–8.0 Hz Butterworth 4th-order | Less than 3 systolic peaks detected in 10s | Status: `POOR_CONTACT`. Blocks AI. |
| **5. Window Stability** | Consecutive quality windows | Consecutive good windows $< 3$ | Status: `STABILIZING`. Awaiting settling. |
| **Observation: Extreme Rate** | Peak-to-peak interval median | $\text{BPM} < 40$ or $\text{BPM} > 180$ | Passes to AI with tag `RECHECK_REQUIRED`. |
| **Observation: Irregularity** | Coefficient of variation: $\frac{\sigma(\text{RR})}{\mu(\text{RR})}$ | $\text{RR-CV} > 0.35$ | Passes to AI with tag `IRREGULAR_PULSE`. |

When quality checks 1–5 pass and $\ge 3$ consecutive windows are stable, `ai_screening_enabled = True` and status is `RELIABLE`.

---

## 4. Personal Baseline Engine & Instability Math

### 4.1 Truthful Baseline Guarantee
Uncalibrated users see:
- `instability_score: null`
- `status_label: "Personal baseline required"`
- `departure_flags: ["BASELINE_NOT_CALIBRATED"]`
The system strictly rejects static population norms (e.g. 72 BPM, 35 ms RMSSD) because resting physiology varies widely between individuals (48 BPM in endurance runners vs 82 BPM in sedentary individuals).

### 4.2 2-Minute Seated Calibration Protocol
- **Duration:** 120 seconds total.
- **Stabilization Window:** First 30 seconds are discarded (acclimatization period).
- **Collection Window:** Next 90 seconds collect 10-second non-overlapping windows.
- **Retention Requirement:** Must collect at least 6 clean, quality-gated windows ($\ge 66\%$ acceptance).
- **Baselines Computed:**
  $$\text{Median BPM} = \text{median}(\text{BPM}_1, \dots, \text{BPM}_n)$$
  $$\text{MAD BPM} = \text{median}(|\text{BPM}_i - \text{Median BPM}|) \times 1.4826$$
  $$\text{Median RR} = \text{median}(\text{RR}_1, \dots, \text{RR}_n)$$
  $$\text{Median RMSSD} = \text{median}(\text{RMSSD}_1, \dots, \text{RMSSD}_n)$$
  $$\text{Median RR-CV} = \text{median}(\text{RR-CV}_1, \dots, \text{RR-CV}_n)$$
- **Governance:** Baseline stores `device_boot_id`, sensor config, calibration timestamp, and an automated **30-day Time-To-Live (TTL)** expiration date.

### 4.3 Robust Z-Score Formulation
$$\text{Robust } Z = \frac{x_{\text{current}} - \text{Median}}{1.4826 \times \max(\text{MAD}, \text{min\_mad})}$$
Where $\text{min\_mad} = 2.0$ BPM (prevents division by zero in unusually uniform baselines).

### 4.4 Personal Instability Index (0–100) Formulation
The composite instability score combines 4 physiological dimensions:
$$I_{\text{raw}} = 0.35 \cdot S_{\text{rate}} + 0.25 \cdot S_{\text{irreg}} + 0.20 \cdot S_{\text{vagal}} + 0.20 \cdot S_{\text{temporal}}$$
Where:
- $S_{\text{rate}} = \min(100, |\text{Robust } Z_{\text{BPM}}| \times 15.0)$
- $S_{\text{irreg}} = \min(100, \max(0, \text{Robust } Z_{\text{RR-CV}}) \times 20.0)$
- $S_{\text{vagal}} = \min(100, \max(0, -Z_{\text{RMSSD}}) \times 20.0)$ (penalizes vagal parasympathetic withdrawal)
- $S_{\text{temporal}} = \text{Consensus departure across last 4 windows}$

The raw score is smoothed with an Exponential Moving Average:
$$I_t = \alpha \cdot I_{\text{raw}} + (1 - \alpha) \cdot I_{t-1} \quad (\alpha = 0.35)$$

**Clinical Display Bands:**
- `0 – 20`: Stable (within individual resting variation)
- `20 – 40`: Mild departure
- `40 – 70`: Sustained physiological departure
- `70 – 100`: Review recommended

---

## 5. Dual-Modality AI Inference Engine

### 5.1 Training Cohort Provenance (Zero Synthetic ML Data)
- **Datasets:** MIMIC-III Waveform (~2,000 patients), Computing in Cardiology (CinC) 2015 Challenge (231 patients), Brno University BUT PPG v2.0 (39 patients), BIDMC PPG & Respiration.
- **Total Patients:** 2,271 unique ICU and ambulatory patients.
- **Total Windows:** 4,683 clean 10-second segments ($1{,}000$ samples @ 100 Hz).
- **8 Canonical Classes:** `Normal`, `Bradycardia`, `Tachycardia`, `AFib`, `Cardiac_Paced`, `V_Tachycardia`, `V_Flutter_Fib`, `Asystole`.
- **Validation Scheme:** Patient-isolated nested 5-Fold StratifiedGroupKFold (`groups = patient_id`). No patient ever appears in both training and testing folds.

### 5.2 27 Hand-Crafted Classical HRV Biomarkers
1. `bpm`: Mean pulse rate
2. `rr_mean`: Mean inter-beat interval (ms)
3. `rr_std`: Standard deviation of RR intervals
4. `rr_min`: Minimum RR interval
5. `rr_max`: Maximum RR interval
6. `rr_cv`: Coefficient of variation ($\text{rr\_std} / \text{rr\_mean}$)
7. `rmssd`: Root mean square of successive RR differences
8. `sdnn`: Standard deviation of normal-to-normal intervals
9. `pnn50`: Percentage of successive RR differences $> 50$ ms
10. `pnn20`: Percentage of successive RR differences $> 20$ ms
11. `rr_skew`: Skewness of RR interval distribution
12. `rr_kurt`: Kurtosis of RR interval distribution
13. `amp_mean`: Mean systolic peak amplitude
14. `amp_std`: Standard deviation of peak amplitudes
15. `amp_cv`: Amplitude coefficient of variation
16. `width_mean`: Mean systolic pulse width (ms)
17. `width_std`: Standard deviation of pulse widths
18. `sqi`: Signal Quality Index (kurtosis-weighted template SNR)
19. `lf_power`: Low-frequency power (0.04–0.15 Hz via Welch PSD)
20. `hf_power`: High-frequency power (0.15–0.40 Hz)
21. `lf_hf_ratio`: Autonomic balance proxy ($\text{lf\_power} / \text{hf\_power}$)
22. `vlf_power`: Very low frequency power (<0.04 Hz)
23. `total_power`: Total spectral power across all bands
24. `sampen`: Sample entropy of filtered waveform
25. `dicrotic_notch_ratio`: Relative amplitude of dicrotic deflection
26. `systolic_slope`: Mean rising slope of arterial upstroke
27. `diastolic_decay_tau`: Exponential decay constant of diastolic runoff

### 5.3 Modality A: Classical Super Ensemble
- Soft-voting ensemble combining **XGBoost Classifier** + **Random Forest** + **ExtraTrees**.
- Standardized via `StandardScaler`.
- Performance: **48.00% Macro-F1** (Accuracy: 58.32%).

### 5.4 Modality B: Inception-1D Deep Convolutional CNN
- **Input:** Raw 1,000-sample 1D vector (10 seconds @ 100 Hz).
- **Architecture:**
  - *Stem:* `Conv1d(1, 32, k=7, p=3)` $\to$ `BatchNorm1d` $\to$ `ReLU` $\to$ `MaxPool1d(2)`.
  - *Inception Block 1:* Multi-scale branches with kernel sizes 3, 7, 15, and 31 (each producing 16 channels, concatenated to 64 channels) + $1\times 1$ conv shortcut.
  - *Pool 1:* `MaxPool1d(2)` $\to$ `Dropout(0.2)`.
  - *Inception Block 2:* Branches with kernel sizes 3, 7, 15, and 31 (each producing 32 channels, concatenated to 128 channels) + $1\times 1$ conv shortcut.
  - *Pool 2:* `MaxPool1d(2)` $\to$ `Dropout(0.3)`.
  - *Inception Block 3:* 128-channel multi-scale refinement.
  - *Head:* `AdaptiveAvgPool1d(1)` $\to$ `Flatten` $\to$ `Linear(128, 64)` $\to$ `ReLU` $\to$ `Dropout(0.3)` $\to$ `Linear(64, 8)`.
- **Total Parameters:** **393,224** (checkpoint size: 1.61 MB).
- **Inference Latency:** 4.2 ms on standard CPU.
- **Performance:** **51.81% Macro-F1** (Accuracy: 56.37%).

### 5.5 Dual-Modality Late Fusion
$$\mathbf{P}_{\text{final}} = 0.38 \cdot \mathbf{P}_{\text{classical}} + 0.62 \cdot \mathbf{P}_{\text{cnn}}$$
Weights were determined via nested inner-fold grid search.
**Final Honest Performance:** **53.92% Macro-F1** (Accuracy: 59.21%) on unseen patients.

### 5.6 Explainability via SHAP TreeExplainer
- Surfaces exact contributions of the 27 biomarkers for each prediction.
- Top global drivers:
  1. `bpm` (Mean $|SHAP| = 0.4201$)
  2. `rr_mean` (Mean $|SHAP| = 0.3412$)
  3. `rr_cv` (Mean $|SHAP| = 0.3120$)
  4. `pnn50` (Mean $|SHAP| = 0.2845$)
  5. `rmssd` (Mean $|SHAP| = 0.2610$)

### 5.7 Scientific Honesty & Confounding Audit
- 100% of VT and Asystole records originate from the CinC 2015 ICU dataset.
- A domain classifier predicting dataset origin from biomarkers hits **77.08% accuracy**.
- **Evidence Ledger:** Shipped with every prediction, explicitly stating:
  *"Optical PPG is not a 12-lead ECG. VT outputs reflect acute ventricular waveform disruption from ICU records and require confirmatory 12-lead ECG review."*

---

## 6. Longitudinal Cardiometabolic Engine & What-If Simulator

### 6.1 Framingham 10-Year General CVD Risk Formula
Based on D'Agostino et al. (*Circulation* 2008) Cox proportional hazards regression:
$$\text{Linear Predictor } L = \sum_{k} \beta_k \cdot \ln(X_k) - \mu$$
$$\text{Base Risk } = 1 - S_0(10)^{\exp(L)}$$

#### Coefficients Table:
| Factor | Male $\beta$ | Female $\beta$ |
|:---|:---:|:---:|
| $\ln(\text{Age})$ | 3.06117 | 2.32888 |
| $\ln(\text{Total Cholesterol})$ | 1.12370 | 1.20904 |
| $\ln(\text{HDL Cholesterol})$ | -0.93263 | -0.70833 |
| $\ln(\text{SBP Treated})$ | 1.99881 | 2.82263 |
| $\ln(\text{SBP Untreated})$ | 1.93303 | 2.76157 |
| Cigarette Smoker | 0.65451 | 0.52873 |
| Diabetes Mellitus | 0.57367 | 0.69154 |
| **Mean of Coefficients** $\mu$ | **23.9802** | **26.1931** |
| **Baseline Survival** $S_0(10)$ | **0.88936** | **0.95012** |

### 6.2 South Asian $1.45\times$ Recalibration
$$\text{Recalibrated Risk} = \min(100.0, \text{Base Risk} \times 1.45)$$
Rationale: INTERHEART study, QRISK3 guidelines, and Indian Heart Association documentation demonstrate South Asians have $1.4\times - 2.0\times$ higher atherosclerotic risk than Framingham European reference populations. A patient with 16.8% Framingham risk crosses the 20% high-risk guideline threshold to 24.4%, correctly triggering clinical statin and antihypertensive therapy.

### 6.3 What-If Treatment Simulator Formulas
Simulates evidence-based Relative Risk Reductions (RRR) under sustained adherence:
| Clinical Intervention | Relative Risk Reduction | Pharmacological / Clinical Basis |
|:---|:---:|:---|
| **High-Intensity Statin** (Atorvastatin 20–40mg) | **28% RRR** ($\times 0.72$) | CTT Meta-Analysis (1 mmol/L LDL-C reduction) |
| **Beta-Blocker** (Metoprolol 50mg) | **15% RRR** ($\times 0.85$) | Autonomic tone stabilization |
| **ACE Inhibitor / ARB** (Ramipril 5mg / Telmisartan) | **12% RRR** ($\times 0.88$) | HOPE Study (Cardiovascular protection) |
| **Systolic BP Reduction to $<130$ mmHg** | **18% RRR** ($\times 0.82$) | SPRINT Trial (Intensive blood pressure control) |
| **Smoking Cessation** | **35% RRR** ($\times 0.65$) | 5-Year Tobacco Cessation Longitudinal Curve |
| **Combined Adherent Protocol** | **Up to 68% RRR** | Multiplicative joint survival modeling |

---

## 7. Backend API Architecture & Telemetry Contract

### 7.1 Tech Stack
- **Runtime:** Python 3.11
- **Server:** Flask 3.0 + Flask-SocketIO 5.3 (eventlet / threading engine)
- **Machine Learning:** PyTorch 2.0+, scikit-learn 1.4+, XGBoost 2.0+, SciPy 1.13+, NumPy 1.26+

### 7.2 Primary REST Endpoints
| Method | Endpoint | Description | Request Payload | Response Key Fields |
|:---|:---|:---|:---|:---|
| `GET` | `/` | API Health & Feature Inventory | None | `status: "healthy", version: "4.1.0"` |
| `GET` | `/patients` | Get synthetic Indian patient cohort | None | `patients: [...]` (100 patients) |
| `POST` | `/patient/select` | Switch active digital twin | `{"patient_id": "PAT001"}` | `active_twin: {...}` |
| `GET` | `/twin/status` | Complete digital twin state | None | `patient_ehr, current_vitals, personal_instability, signal_gate, evidence_ledger` |
| `POST` | `/twin/simulate` | Run What-If pharmacological simulation | `{"statin": true, "sbp": 125, "smoker": false}` | `simulated_risk, relative_risk_reduction` |
| `POST` | `/twin/scenario` | Inject clinical demonstration scenario | `{"scenario": "afib_episode"}` | `updated_status` (broadcasts via WebSocket) |
| `POST` | `/baseline/calibrate` | Trigger 2-minute empirical calibration | `{"duration_sec": 120}` | `calibration_status: "started"` |
| `POST` | `/baseline/cancel` | Cancel active calibration | None | `status: "cancelled"` |
| `GET` | `/baseline/status` | Read current baseline & parameters | None | `has_baseline, median_bpm, mad_bpm` |
| `POST` | `/data` | Ingest ESP32 raw 50-sample telemetry | `{"values": [...], "deltas_us": [...]}` | `status: "ok", chunks_received` |
| `GET` | `/signal/gate` | Read 5-part signal reliability gate | None | `status, ai_screening_enabled, metrics` |
| `GET` | `/explainability/shap` | Read precomputed SHAP knowledge | None | `feature_importance, class_drivers` |
| `GET` | `/fhir/export` | Export session as HL7 FHIR R4 Bundle | None | Complete FHIR JSON collection bundle |

### 7.3 Real-Time WebSocket Events
- `telemetry_update` — Emitted immediately whenever a new 10s window is evaluated or scenario is injected.
- `live_waveform` — Emitted at 100 Hz to drive the frontend real-time oscilloscope canvas.
- `patient_switched` — Emitted when a new patient profile is loaded.

---

## 8. Frontend Clinical Dashboard & Mobile Companion

### 8.1 Web App (`frontend/web/`)
- **Framework:** React 19 + Vite + Socket.IO Client + Lucide React.
- **Design System:** Editorial clinical aesthetic (warm parchment background `#F8F7F2`, deep pine text `#1B403E`, medical teal accent `#167C76`).
- **4 Primary Clinical Tabs:**
  1. **Home:** Patient demographics, quiet baseline reference, biological vascular age card.
  2. **Twin Profile:** Longitudinal Framingham perspective, 10-year risk trajectory, risk factor breakdown.
  3. **Live Check:** Real-time 100 Hz oscilloscope canvas, signal gate status HUD, Instability Index meter, SHAP feature attributions.
  4. **What-If Plan:** Pharmacological levers (Atorvastatin, Metoprolol, Ramipril, SBP stepper, smoking cessation) with live projected risk curves.

### 8.2 Mobile App (`frontend/mobile/`)
- **Framework:** React Native (Expo) + pure SVG icons + HTTP polling (`POLL_MS = 1000`).
- **Functionality:** Mirrors the 3 operational views (Live, Twin, Plan), allows initiating calibration and injecting scenarios on the go, synchronizing with the web dashboard via the backend.

---

## 9. Verification & Automated Test Suite

The project includes **49 automated tests** passing with 100% success rate (`python -m unittest discover -s tests -p "test_*.py"`):
- `tests/test_cardiotwin.py` (35 tests):
  - API server contract, route response schemas, telemetry ingestion.
  - Clinical Framingham calculation and boundary handling (ages 30–74).
  - Personal baseline rules (invalidation after 30 days, device ID mismatch, minimum 6 windows).
  - Decoupled signal gate (saturation, finger-off, sample timing drops).
  - Dual-modality predictor loading and late fusion arithmetic.
  - Multi-window temporal persistence consensus.
- `tests/test_instability_target_validation.py` (14 tests):
  - Quiet seated baseline $\to$ Stable ($0–20$).
  - Finger-off sensor $\to$ Gated (measurement unreliable).
  - Hand movement artifact $\to$ Gated.
  - Standing transition $\to$ Mild temporary departure ($20–40$).
  - Post-standing recovery $\to$ Return toward baseline ($<20$).
  - Sustained high pulse $\to$ Sustained physiological departure ($40–100$).
  - Irregular pulse pattern (AFib) $\to$ Review recommended.

---

## 10. How to Recreate This Project From Scratch (Step-by-Step)

```
STEP 1: REPRODUCE HARDWARE NODE
1. Solder ESP32-WROOM-32D to MAX30102 via I2C (GPIO 21 SDA, GPIO 22 SCL) with 4.7kΩ pullups.
2. Connect SSD1306 OLED to the same I2C bus.
3. Wire TP4056 + 3.7V LiPo cell to ESP32 VIN and GND.
4. Flash `hardware/esp32_ppg_sender/esp32_ppg_sender.ino` using Arduino IDE with FreeRTOS.

STEP 2: CONFIGURE PYTHON BACKEND
1. Create Python 3.11 virtual environment: `python -m venv venv`.
2. Install dependencies: `pip install flask flask-socketio torch torchvision xgboost scikit-learn numpy scipy pandas shap joblib matplotlib wfdb`.
3. Verify all 49 tests pass: `python -m unittest discover -s tests -p "test_*.py" -v`.
4. Launch backend: `python backend/api_server.py` (runs on `http://127.0.0.1:5000`).

STEP 3: LAUNCH CLINICAL DASHBOARD
1. Navigate to `frontend/web/`: `cd frontend/web`.
2. Install npm dependencies: `npm install`.
3. Launch development server: `npm run dev` (opens on `http://localhost:5173`).

STEP 4: EXECUTE CLINICAL DEMONSTRATION WORKFLOW
1. Select patient `PAT001` (Devendra Patel, 58M, smoker, SBP 148).
2. Click "Start Calibration" -> Wait 120s seated rest -> Baseline established.
3. Stream live pulse -> Observe real-time waveform and Instability Index.
4. Remove finger -> Observe instant Signal Gate rejection (`FINGER_OFF`, AI blocked).
5. Switch to "What-If" tab -> Prescribe Atorvastatin + SBP reduction -> Observe risk drop from 24.4% to 14.1%.
6. Click "Export FHIR R4 Bundle" -> Download JSON file for e-Sanjeevani referral.
```
