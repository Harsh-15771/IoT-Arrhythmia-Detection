# 💰 CardioTwin Sentinel — Hardware Bill of Materials (BOM) & Health-Economics Analysis

**Cost-Effectiveness & Scalability Analysis for Primary Healthcare in India**  
**Target Context:** Ayushman Bharat Health & Wellness Centres (AB-HWCs), Rural Sub-Centres, Tier-2/3 District Clinics

---

## 1. Hardware Bill of Materials (BOM)

CardioTwin Sentinel is engineered entirely with commercially available, low-cost, off-the-shelf microelectronics. The hardware architecture separates real-time 100 Hz optical sampling (Core 1) from non-blocking WiFi transmission (Core 0) on a single dual-core ESP32 SoC.

| Component | Part Description | Unit Cost (INR ₹) | Unit Cost (USD $) | Key Function / Specification | Sourcing Reference |
|:---|:---|:---:|:---:|:---|:---|
| **Microcontroller** | ESP32-WROOM-32D Dual-Core Xtensa LX6 (240 MHz, 520 KB SRAM) | ₹480 | $5.80 | Dedicated FreeRTOS dual-core tasking: Core 1 optical capture, Core 0 TCP/IP socket streaming | Robu.in / Mouser India |
| **Optical Pulse Sensor** | MAX30102 High-Sensitivity PPG Subsystem (Analog Devices / Maxim) | ₹220 | $2.65 | Integrated LED + photodiode + 18-bit delta-sigma ADC with programmable LED current (0–50 mA) | Quartz Components |
| **Local Status Display** | SSD1306 0.96" I2C Monochrome OLED (128×64) | ₹140 | $1.70 | Real-time status display: instantaneous BPM, SQI bar, WiFi IP, calibration status | Robu.in |
| **Power Management** | TP4056 Micro-USB / Type-C Li-Ion Charging Module + 3.7V 650mAh LiPo Cell | ₹210 | $2.55 | 6–8 hours untethered continuous monitoring; rechargeable via standard mobile charger | Robu.in |
| **Interconnect & Passive** | Pull-up resistors (4.7kΩ I2C), silicone insulated wire, decoupling capacitors | ₹35 | $0.42 | Signal conditioning and noise decoupling for high SNR pulse wave acquisition | Local Electronics Market |
| **Ergonomic Finger Clip** | 3D-Printed Biocompatible PLA Optical Enclosure + Soft Foam Lining | ₹80 | $0.95 | Shields ambient light (reducing optical artifact), stabilizes fingertip contact pressure | Rapid Prototyping Lab |
| **Total Unit BOM** | **Complete CardioTwin Sentinel Hardware Node** | **₹1,165** | **~$14.07** | Fully functional IoT pulse screening device with real-time WiFi telemetry | Scalable at volume (< ₹950 in 1k batch) |

---

## 2. Health-Economics Comparison: CardioTwin vs Existing Clinical Tools

Cardiovascular disease accounts for **28% of all deaths in India**, with >50% occurring prematurely in rural and semi-urban populations lacking tertiary hospital access. Existing monitoring technologies are either cost-prohibitive for mass screening or structurally ill-suited for rural primary care:

| Modality / Product | Capital / Rental Cost (INR) | Patient Access Model | Limitations in Indian Primary Care | CardioTwin Advantage |
|:---|:---:|:---|:---|:---|
| **Commercial Smartwatch** (Apple Watch Series 9 / Ultra) | ₹41,900 – ₹89,900 | High-income personal consumer luxury | Prohibitive cost for 95% of Indian population; proprietary iOS lock-in; uncalibrated generic baseline | **>35× cheaper**; open web dashboard; personal 2-minute empirical calibration |
| **24–48h Holter Monitor** | ₹5,000 – ₹12,000 per 24h rental | Tertiary hospital referral required | Multi-lead chest electrodes cause skin irritation; manual retrospective review (2–3 day delay) | **Zero-rental cost**; continuous real-time streaming; instantaneous automated baseline departure flags |
| **Hospital Bedside Monitor** (Philips / Mindray / Contec) | ₹1,20,000 – ₹3,50,000 | Inpatient ICU/Emergency only | Mains-powered, non-portable; requires trained ICU nursing staff | Ultra-portable (~60 grams); battery operated; deployable at rural Sub-Centre HWCs |
| **Consumer Pulse Oximeter** | ₹600 – ₹1,200 | OTC retail purchase | Displays only instantaneous number; no digital twin, no personal baseline, zero longitudinal memory | Tracks **longitudinal stability**, detects sustained departures, explains physiological shift |

---

## 3. Deployment Feasibility: Ayushman Bharat Health & Wellness Centres (AB-HWCs)

India’s flagship **Ayushman Bharat** initiative has operationalized over **160,000 Health and Wellness Centres** nationwide. CardioTwin Sentinel's low BOM and zero-cloud-dependency local calibration make it an ideal clinical screening companion for:

1. **Community Health Officers (CHOs) & ANMs:** Fast 2-minute resting pulse baseline calibration conducted during routine village hypertension surveys.
2. **Tele-Consultation Decision Support (e-Sanjeevani):** Clinician export JSON enables rural CHOs to transfer objective pulse stability records to district cardiologists via India's e-Sanjeevani telemedicine grid.
3. **Preventive Cardiometabolic Triage:** Distinguishes temporary exertion/stress spikes from sustained autonomic departures, preventing unnecessary emergency referrals while catching silent persistent tachycardia and irregular rhythms early.

---

*Authored for the Digital Twin Challenge 2026 / Happiest Health by the CardioTwin Sentinel Engineering Team.*
