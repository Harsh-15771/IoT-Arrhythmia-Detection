"""
CardioTwin Sentinel — Executive Architecture PDF & Presentation PPTX Generator
Generates:
  1. docs/CardioTwin_Architecture_Diagram.pdf (2-Page Vector Engineering Blueprint)
  2. docs/CardioTwin_Presentation.pptx (12-Slide 16:9 Executive Jury Deck)
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.backends.backend_pdf import PdfPages

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---------------------------------------------------------------------------
# PATHS & EDITORIAL DESIGN TOKENS
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
ASSETS_DIR = os.path.join(DOCS_DIR, "_deck_assets")
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

PDF_OUT = os.path.join(DOCS_DIR, "CardioTwin_Architecture_Diagram.pdf")
PPTX_OUT = os.path.join(DOCS_DIR, "CardioTwin_Presentation.pptx")

# Editorial Medical Color Palette (Matches App.jsx & index.css)
HEX = {
    "bg": "#F7F5ED",
    "card": "#FFFFFF",
    "card_alt": "#EFECE1",
    "pine": "#1B403E",
    "pine_dark": "#122B2A",
    "teal": "#167C76",
    "teal_light": "#E3F2EE",
    "slate": "#58706D",
    "muted": "#829491",
    "border": "#D5DDD9",
    "amber": "#C87A19",
    "amber_bg": "#FDF2E1",
    "rose": "#B63A3A",
    "rose_bg": "#FAE5E3",
    "green": "#1D7A5F",
    "green_bg": "#E2F4EC",
}

def rgb(hex_str):
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ===========================================================================
# PART 1: GENERATE HIGH-RESOLUTION CHARTS FOR PPTX SLIDES
# ===========================================================================
def generate_chart_assets():
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    plt.rcParams["axes.edgecolor"] = HEX["border"]

    # 1. Waveform Comparison Chart (Normal Dicrotic vs AFib vs Clipped Motion)
    fig, axes = plt.subplots(3, 1, figsize=(6.5, 4.2), dpi=300, sharex=True)
    fig.patch.set_facecolor(HEX["card"])
    t = np.linspace(0, 3.0, 300)

    # Normal Sinus (72 BPM)
    phi_norm = (t * 1.2) % 1.0
    sig_norm = np.exp(-((phi_norm - 0.18) ** 2) / (2 * 0.06 ** 2)) + 0.35 * np.exp(-((phi_norm - 0.42) ** 2) / (2 * 0.08 ** 2))
    axes[0].plot(t, sig_norm, color=HEX["teal"], lw=2.2)
    axes[0].set_title("A. Clean Sinus Rhythm (72 BPM, Dicrotic Notch)  ->  GATE: PASS", loc="left", fontsize=9.5, fontweight="bold", color=HEX["pine"])

    # AFib Irregular Pulse (Chaotic intervals, variable stroke volume)
    sig_afib = np.zeros_like(t)
    peaks_t = [0.22, 0.58, 1.15, 1.48, 2.18, 2.52, 2.85]
    amps = [0.85, 0.60, 1.15, 0.70, 1.20, 0.65, 0.90]
    for pt, a in zip(peaks_t, amps):
        sig_afib += a * np.exp(-((t - pt) ** 2) / (2 * 0.055 ** 2))
    axes[1].plot(t, sig_afib, color=HEX["amber"], lw=2.2)
    axes[1].set_title("B. Atrial Fibrillation (RR-CV 22%, Variable Pulse Amp)  ->  GATE: PASS TO AI", loc="left", fontsize=9.5, fontweight="bold", color=HEX["amber"])

    # Sensor Saturation / Motion Artifact
    sig_sat = np.clip(0.6 + 0.9 * np.sin(2 * np.pi * 0.7 * t) + 0.7 * np.cos(2 * np.pi * 2.3 * t), 0, 1.15)
    axes[2].plot(t, sig_sat, color=HEX["rose"], lw=2.0)
    axes[2].axhline(1.15, color=HEX["rose"], ls="--", lw=1.0)
    axes[2].set_title("C. Optical Amplifier Saturation (>260k ADC Ceiling)  ->  GATE: BLOCK AI", loc="left", fontsize=9.5, fontweight="bold", color=HEX["rose"])
    axes[2].set_xlabel("Time (seconds @ 100 Hz)", fontsize=8.5, color=HEX["slate"])

    for ax in axes:
        ax.set_facecolor("#F9FAF7")
        ax.set_yticks([])
        ax.grid(True, linestyle=":", alpha=0.5, color=HEX["border"])

    plt.tight_layout()
    wave_path = os.path.join(ASSETS_DIR, "gate_waveforms.png")
    plt.savefig(wave_path, dpi=300)
    plt.close(fig)

    # 2. Benchmark & 3-Tier Clinical Actionability Chart
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.8), dpi=300)
    fig.patch.set_facecolor(HEX["bg"])

    # Left: 8-Class Ablation Tournament
    models = ["Random\nBaseline", "CRNN-\nBiLSTM", "Classical\nEnsemble", "ResNet-1D\nCNN", "Inception-1D\nCNN", "CardioTwin\nTemp-Fusion"]
    f1s = [12.50, 45.04, 48.00, 49.44, 51.81, 54.40]
    colors = ["#CBD5E1", "#94A3B8", "#64748B", "#475569", HEX["teal"], HEX["pine"]]
    bars = ax1.bar(models, f1s, color=colors, width=0.58)
    ax1.set_facecolor(HEX["card"])
    ax1.set_ylim(0, 66)
    ax1.set_ylabel("Macro-F1 (%) — 2,271 Patients", fontsize=9, fontweight="bold", color=HEX["pine"])
    ax1.set_title("8-Class Leak-Free GroupKFold Tournament", fontsize=10.5, fontweight="bold", color=HEX["pine"], pad=10)
    ax1.tick_params(axis="x", labelsize=8)
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    for b, v in zip(bars, f1s):
        ax1.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.1f}%", ha="center", fontsize=8.5, fontweight="bold", color=HEX["pine"])

    # Right: 3-Tier Clinical Actionability Metrics
    tiers = ["Tier 1: Normal\nSpecificity", "Tier 2: Anomaly\nRecall (Sensitivity)", "Tier 3: ICU Alarm\nSpecificity", "Overall 3-Tier\nTriage Accuracy"]
    t_vals = [98.83, 90.09, 92.95, 75.68]
    t_cols = [HEX["green"], HEX["teal"], HEX["amber"], HEX["pine"]]
    bars2 = ax2.barh(tiers[::-1], t_vals[::-1], color=t_cols[::-1], height=0.52)
    ax2.set_facecolor(HEX["card"])
    ax2.set_xlim(0, 112)
    ax2.set_xlabel("Verified Performance (%)", fontsize=9, fontweight="bold", color=HEX["pine"])
    ax2.set_title("3-Tier Clinical Actionability Benchmark", fontsize=10.5, fontweight="bold", color=HEX["pine"], pad=10)
    ax2.tick_params(axis="y", labelsize=8.5)
    ax2.grid(axis="x", linestyle="--", alpha=0.4)
    for b, v in zip(bars2, t_vals[::-1]):
        ax2.text(v + 1.5, b.get_y() + b.get_height() / 2, f"{v:.2f}%", va="center", fontsize=9, fontweight="bold", color=HEX["pine"])

    plt.tight_layout()
    bench_path = os.path.join(ASSETS_DIR, "benchmarks_chart.png")
    plt.savefig(bench_path, dpi=300)
    plt.close(fig)

    # 3. SHAP Top Biomarker Drivers Chart
    fig, ax = plt.subplots(figsize=(5.6, 3.6), dpi=300)
    fig.patch.set_facecolor(HEX["card"])
    ax.set_facecolor(HEX["card"])
    feats = ["sig_skew (Wave Asymmetry)", "peak_amp_mean (Perfusion)", "rr_mean (IBI Duration)", "bpm (Pulse Rate)", "pnn50 (AFib Irregularity)", "rr_min (Shortest Beat)", "rmssd (Vagal Tone)"]
    shap_vals = [0.4895, 0.4271, 0.3646, 0.3524, 0.2201, 0.1968, 0.1766]
    y_pos = np.arange(len(feats))
    bars3 = ax.barh(y_pos, shap_vals[::-1], color=HEX["teal"], height=0.58)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(feats[::-1], fontsize=8.5, fontweight="bold", color=HEX["pine"])
    ax.set_xlim(0, 0.58)
    ax.set_xlabel("Mean |SHAP| Impact (shap.TreeExplainer)", fontsize=8.5, color=HEX["slate"])
    ax.set_title("Global Biomarker Feature Attribution", fontsize=10, fontweight="bold", color=HEX["pine"])
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    for b, v in zip(bars3, shap_vals[::-1]):
        ax.text(v + 0.01, b.get_y() + b.get_height() / 2, f"{v:.3f}", va="center", fontsize=8, fontweight="bold", color=HEX["pine"])
    plt.tight_layout()
    shap_path = os.path.join(ASSETS_DIR, "shap_chart.png")
    plt.savefig(shap_path, dpi=300)
    plt.close(fig)

    return wave_path, bench_path, shap_path


# ===========================================================================
# PART 2: GENERATE 2-PAGE VECTOR ARCHITECTURE PDF
# ===========================================================================
def draw_box(ax, x, y, w, h, title, lines, header_bg=HEX["pine"], body_bg=HEX["card"], border_col=HEX["border"], title_size=9.5, body_size=7.8):
    # Main card
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", facecolor=body_bg, edgecolor=border_col, linewidth=1.2)
    ax.add_patch(box)
    # Header bar
    hh = 0.42
    hbox = FancyBboxPatch((x, y + h - hh), w, hh, boxstyle="round,pad=0.02,rounding_size=0.10", facecolor=header_bg, edgecolor=header_bg, linewidth=0.5)
    ax.add_patch(hbox)
    ax.text(x + 0.14, y + h - hh / 2 - 0.02, title, color="#FFFFFF", fontsize=title_size, fontweight="bold", va="center")

    # Body text lines
    curr_y = y + h - hh - 0.22
    for line in lines:
        if line.startswith("##"):
            ax.text(x + 0.14, curr_y, line[2:].strip(), color=HEX["teal"], fontsize=body_size + 0.3, fontweight="bold", va="top")
            curr_y -= 0.23
        else:
            ax.text(x + 0.14, curr_y, line, color=HEX["pine"], fontsize=body_size, va="top")
            curr_y -= 0.21


def generate_architecture_pdf():
    with PdfPages(PDF_OUT) as pdf:
        # -------------------------------------------------------------------
        # PAGE 1: END-TO-END 5-STAGE SYSTEM ARCHITECTURE PIPELINE
        # -------------------------------------------------------------------
        fig = plt.figure(figsize=(16, 9), dpi=300)
        fig.patch.set_facecolor(HEX["bg"])
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 16)
        ax.set_ylim(0, 9)
        ax.axis("off")

        # Top Banner
        header = FancyBboxPatch((0.4, 8.05), 15.2, 0.72, boxstyle="round,pad=0.02,rounding_size=0.10", facecolor=HEX["pine_dark"], edgecolor=HEX["pine_dark"])
        ax.add_patch(header)
        ax.text(0.65, 8.48, "CARDIOTWIN SENTINEL v4.1  —  END-TO-END MULTIMODAL DIGITAL TWIN ARCHITECTURE", color="#FFFFFF", fontsize=13.5, fontweight="bold", va="center")
        ax.text(0.65, 8.20, "Proactive Cardiovascular & Cardiometabolic Screening Pipeline  |  Team Root Access (Harsh Mishra · VNIT Nagpur)  |  Happiest Health Digital Twin Challenge 2026", color="#A8D3BD", fontsize=8.8, va="center")
        ax.text(15.35, 8.41, "PAGE 1 / 2", color="#FFFFFF", fontsize=9.5, fontweight="bold", ha="right", va="center")

        # 5 Stage Columns (Left to Right)
        # Stage 1: Dual Input Streams (x=0.4, w=2.75)
        draw_box(
            ax, 0.4, 4.65, 2.75, 3.15,
            "STREAM 1: STATIC & 7D EHR",
            [
                "##Clinical & Biochemical Record",
                "• Demographics, Vitals, BMI",
                "• Lipids: Total Chol, LDL, HDL, TG",
                "• Glycemic & Inflam: HbA1c, hs-CRP",
                "• Active Meds: Beta-Blocker, Statin",
                "##7-Day Wearable Trajectory",
                "• 7d Resting HR & Nocturnal RMSSD",
                "• 7d Sleep Efficiency (%) & Steps",
                "##Framingham x 1.45 South Asian",
                "• D'Agostino Cox PH 10-Yr Base Risk",
                "• Biological Vascular Age Model"
            ],
            header_bg=HEX["pine"]
        )

        draw_box(
            ax, 0.4, 1.25, 2.75, 3.15,
            "STREAM 2: 100 Hz EDGE NODE",
            [
                "##Hardware (BOM: INR 1,165 / $14)",
                "• ESP32-WROOM-32D (240 MHz)",
                "• MAX30102 Optical PPG (880nm IR)",
                "• SH1106 128x64 I2C OLED + LiPo",
                "##FreeRTOS Dual-Core Split",
                "• Core 1 (Prio 5): 10,000 us ISR",
                "  Deterministic 100 Hz -> chunkQueue",
                "• Core 0 (Prio 1): Async WiFi POST",
                "##Telemetry Integrity Contract",
                "• seq, device_boot_id, deltas_us[]",
                "• Zero network stalls on Core 1"
            ],
            header_bg=HEX["teal"]
        )

        # Stage 2: Decoupled 5-Part Signal Gate (x=3.5, w=2.75)
        draw_box(
            ax, 3.5, 1.25, 2.75, 6.55,
            "STAGE 2: DECOUPLED GATE",
            [
                "##Why Decoupled Gating Matters",
                "Standard filters reject irregular",
                "beats as noise—discarding AFib.",
                "CardioTwin separates physics",
                "from physiology:",
                "",
                "##Axis 1: Physical Gate (Blocks AI)",
                "1. Contact Floor: ADC < 20,000",
                "   -> Status: FINGER_OFF",
                "2. Amp Ceiling: ADC > 260,000",
                "   or Clipping > 5% -> SATURATED",
                "3. Timing Jitter: |fs - 100| > 15Hz",
                "   or Drops > 5% -> POOR_TIMING",
                "4. Morphology: < 3 systolic peaks",
                "   in 10s (0.5-8Hz Butterworth)",
                "5. Stability: Requires >= 3",
                "   consecutive clean 10s windows",
                "",
                "##Axis 2: Physiology (Passes to AI)",
                "• Extreme Rate (<40 or >180 BPM)",
                "  -> Passes with RECHECK tag",
                "• Chaotic Intervals (RR-CV > 0.35)",
                "  -> Passes as IRREGULAR_RHYTHM"
            ],
            header_bg=HEX["pine"]
        )

        # Stage 3: Dual-Modality AI Engine (x=6.6, w=2.95)
        draw_box(
            ax, 6.6, 1.25, 2.95, 6.55,
            "STAGE 3: DUAL-MODALITY AI",
            [
                "##Training Cohort (Zero Synthetic)",
                "• 2,271 Unique ICU/Amb Patients",
                "• 4,683 Windows (10s @ 100 Hz)",
                "• MIMIC-III + CinC 2015 + BUT + BIDMC",
                "• Patient-Isolated GroupKFold (k=5)",
                "",
                "##Modality A: Classical Ensemble",
                "• 27 HRV, Spectral & Morph Features",
                "• XGBoost + Random Forest + ET",
                "• Standalone Macro-F1: 48.00%",
                "",
                "##Modality B: Inception-1D CNN",
                "• Raw 1,000-Sample 1D Waveform",
                "• 4 Parallel Kernels (3, 7, 15, 31)",
                "• 393,224 Params (1.61 MB, 4.2ms)",
                "• Standalone Macro-F1: 51.81%",
                "",
                "##Temperature-Scaled Late Fusion",
                "• 0.38 Classical (Tc=0.85) +",
                "  0.62 Inception-1D (Tdl=1.15)",
                "• 8-Class Macro-F1: 54.40%",
                "• 3-Tier Triage Acc: 75.68%",
                "• Normal Specificity: 98.83%",
                "• Tier-2 Anomaly Recall: 90.09%"
            ],
            header_bg=HEX["teal"]
        )

        # Stage 4: Proactive Digital Twin Core (x=9.9, w=2.85)
        draw_box(
            ax, 9.9, 1.25, 2.85, 6.55,
            "STAGE 4: DIGITAL TWIN CORE",
            [
                "##2-Min Seated Personal Baseline",
                "• 30s settling + >=6 clean windows",
                "• Non-parametric Median + MAD",
                "• Robust Z-Score departure index",
                "• 30-day TTL & device_id lock",
                "",
                "##EHR Vulnerability Coupling (M_EHR)",
                "• Couples Stream 1 EHR + Stream 2:",
                "• Beta-Blockade Escape (BPM >= 90",
                "  despite active Metoprolol)",
                "• Subclinical AFib Prodrome",
                "• Autonomic Vagal Withdrawal",
                "• M_EHR Multiplier: 1.00x - 1.40x",
                "",
                "##2h / 6h Proactive Forecaster",
                "• Fuses 7-day nocturnal RMSSD",
                "  slope + acute dI/dt velocity",
                "• Predicts Time-to-Decompensation",
                "  2 to 6 hours before crisis",
                "",
                "##Dual-Horizon What-If Simulator",
                "• 24-Hr Hemodynamic Twin Response",
                "• 10-Yr ASCVD Risk (SGLT2i, Statin,",
                "  Beta-Blocker, ACE-I, SBP, Smoking)"
            ],
            header_bg=HEX["pine"]
        )

        # Stage 5: Clinician Portal & FHIR R4 (x=13.1, w=2.5)
        draw_box(
            ax, 13.1, 1.25, 2.5, 6.55,
            "STAGE 5: CLINICIAN & FHIR",
            [
                "##Clinician Command Portal",
                "• React 19 + Socket.IO Live UI",
                "• React Native Mobile Companion",
                "• 100 Hz SVG Oscilloscope",
                "• Live HRV Strip (RMSSD, SDNN,",
                "  RR-CV, Kurtosis SQI)",
                "• 8-Biomarker EHR Lab Panel",
                "• 7-Day Wearable Sparklines",
                "",
                "##Explainability & Honesty",
                "• SHAP TreeExplainer top drivers",
                "• Machine-Readable Evidence",
                "  Ledger (No fake SpO2, PPG!=ECG,",
                "  77.08% ICU source audit)",
                "",
                "##ABDM & HL7 FHIR R4 Export",
                "• GET /fhir/export Bundle",
                "• 14-Digit ABHA ID Linked",
                "• LOINC 8867-4, 80404-7, 79423-0",
                "• e-Sanjeevani Tele-Consult Ready",
                "",
                "##DPDP Act 2023 Edge Privacy",
                "• Raw waveforms purged in RAM"
            ],
            header_bg=HEX["teal"]
        )

        # Connecting Arrows between stages
        arrow_y = [6.2, 2.8, 4.5, 4.5, 4.5]
        pairs = [(3.15, 3.5, 6.2), (3.15, 3.5, 2.8), (6.25, 6.6, 4.5), (9.55, 9.9, 4.5), (12.75, 13.1, 4.5)]
        for x1, x2, y_pos in pairs:
            ax.annotate("", xy=(x2, y_pos), xytext=(x1, y_pos), arrowprops=dict(arrowstyle="->,head_width=0.25,head_length=0.25", lw=2.2, color=HEX["teal"]))

        # Bottom KPI Strip
        kpis = [
            ("INR 1,165 (~$14)", "Complete Edge Hardware BOM"),
            ("100 Hz / +-0.4ms", "FreeRTOS Core 1 ISR Sampling"),
            ("2,271 Patients", "Zero-Leakage GroupKFold Cohort"),
            ("98.83% / 90.09%", "Normal Spec / Tier-2 Anomaly Recall"),
            ("2h & 6h Horizon", "Proactive Decompensation Forecast"),
            ("54 / 54 Passing", "Automated Unit & Target Validation Tests")
        ]
        kw = 2.45
        for idx, (val, lbl) in enumerate(kpis):
            kx = 0.4 + idx * 2.55
            kbox = FancyBboxPatch((kx, 0.25), kw, 0.75, boxstyle="round,pad=0.02,rounding_size=0.08", facecolor=HEX["pine_dark"], edgecolor=HEX["teal"], linewidth=1.0)
            ax.add_patch(kbox)
            ax.text(kx + kw / 2, 0.70, val, color="#A8D3BD", fontsize=10.5, fontweight="bold", ha="center", va="center")
            ax.text(kx + kw / 2, 0.42, lbl, color="#FFFFFF", fontsize=7.5, ha="center", va="center")

        pdf.savefig(fig)
        plt.close(fig)

        # -------------------------------------------------------------------
        # PAGE 2: HARDWARE SCHEMATIC, MATHEMATICAL FORMULAS & FHIR MAPPING
        # -------------------------------------------------------------------
        fig = plt.figure(figsize=(16, 9), dpi=300)
        fig.patch.set_facecolor(HEX["bg"])
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 16)
        ax.set_ylim(0, 9)
        ax.axis("off")

        header2 = FancyBboxPatch((0.4, 8.05), 15.2, 0.72, boxstyle="round,pad=0.02,rounding_size=0.10", facecolor=HEX["pine_dark"], edgecolor=HEX["pine_dark"])
        ax.add_patch(header2)
        ax.text(0.65, 8.48, "CARDIOTWIN SENTINEL v4.1  —  HARDWARE SCHEMATIC, MATHEMATICAL FORMULATION & FHIR R4 SPECIFICATION", color="#FFFFFF", fontsize=13, fontweight="bold", va="center")
        ax.text(0.65, 8.20, "Zero-Guesswork Engineering Reference  |  17 REST Endpoints + WebSocket Telemetry  |  54 Automated Verification Tests", color="#A8D3BD", fontsize=8.8, va="center")
        ax.text(15.35, 8.41, "PAGE 2 / 2", color="#FFFFFF", fontsize=9.5, fontweight="bold", ha="right", va="center")

        # Left Column: Hardware Schematic & BOM
        draw_box(
            ax, 0.4, 1.1, 4.8, 6.7,
            "1. HARDWARE PINOUT & BILL OF MATERIALS (INR 1,165)",
            [
                "##I2C Circuit Pinout (400 kHz Fast Mode + 4.7k Pull-ups)",
                "• ESP32 3V3 / GND  ----->  MAX30102 VIN / GND & OLED VCC / GND",
                "• ESP32 GPIO 21 (SDA) -->  MAX30102 SDA & SH1106 OLED SDA",
                "• ESP32 GPIO 22 (SCL) -->  MAX30102 SCL & SH1106 OLED SCL",
                "• TP4056 + 650mAh LiPo ->  ESP32 VIN / GND (6-8h Portable Run)",
                "",
                "##Sensor Configuration (MAX30102 Register Setup)",
                "• Wavelength: 880nm Infrared LED @ 6.0 mA Drive Current",
                "• ADC Resolution: 18-bit (262,144 counts), 411 us Pulse Width",
                "• Sampling Rate: 100.0 Hz (10,000 us hard timer period)",
                "",
                "##Component Cost Breakdown (Single Unit vs 1k Batch)",
                "• ESP32-WROOM-32D Dual-Core MCU:           INR 480  ($5.80)",
                "• MAX30102 Optical PPG Subsystem:          INR 220  ($2.65)",
                "• SSD1306 / SH1106 0.96\" I2C OLED:        INR 140  ($1.70)",
                "• TP4056 USB-C Charger + 650mAh LiPo:      INR 210  ($2.55)",
                "• Biocompatible 3D PLA Finger Clip + Foam: INR  80  ($0.95)",
                "• 4.7k Pull-ups, Bypass Caps, Silicone:    INR  35  ($0.42)",
                "------------------------------------------------------------",
                "##TOTAL UNIT BOM: INR 1,165 (~$14.07) | < INR 950 @ 1,000 units"
            ],
            header_bg=HEX["pine"]
        )

        # Middle Column: Core Mathematical Formulations
        draw_box(
            ax, 5.5, 1.1, 5.2, 6.7,
            "2. DIGITAL TWIN MATHEMATICAL FORMULATIONS",
            [
                "##A. Non-Parametric Personal Baseline & Robust Z-Score",
                "• Empirical 2-Min Seated Calibration (6+ clean 10s windows):",
                "  Robust_Z(x) = (x_current - Median) / (1.4826 * max(MAD, min_mad))",
                "  (50% statistical breakdown point; immune to transient spikes)",
                "",
                "##B. Multimodal Personal Instability Index (0 - 100)",
                "• I_raw = 0.35*S_rate + 0.25*S_irreg + 0.20*S_vagal + 0.20*S_persist",
                "• EMA Smoothing: I_t = 0.35 * I_raw + 0.65 * I_(t-1)",
                "",
                "##C. EHR-Coupled Vulnerability Substrate Multiplier (M_EHR)",
                "• M_EHR = 1.0 + 0.10*I(CAD/PCI) + 0.08*I(HbA1c>=7.0)",
                "              + 0.08*I(hs-CRP>2.0) + 0.14*I(Beta-Blockade Escape)",
                "• Beta-Blockade Escape fires when BPM >= 90 despite active",
                "  Metoprolol / Bisoprolol therapy (sympathetic breakthrough).",
                "",
                "##D. 2-Hour & 6-Hour Proactive Horizon State Extrapolation",
                "• I_hat(t + dt) = clip(I_t + (b_acute*dI_dt + b_7d*Slope_7d) * M_EHR)",
                "• Fuses 7-day nocturnal RMSSD decay slope with acute velocity.",
                "",
                "##E. South Asian Recalibrated Framingham 10-Yr Cox PH Risk",
                "• Base_Risk = 1 - S0(10)^exp(Sum(beta_k * ln(X_k)) - mu)",
                "• Recalibrated_Risk = min(99.0%, Base_Risk * 1.45)"
            ],
            header_bg=HEX["teal"]
        )

        # Right Column: ABDM FHIR R4 & API Contract
        draw_box(
            ax, 11.0, 1.1, 4.6, 6.7,
            "3. ABDM HL7 FHIR R4 & API CONTRACT",
            [
                "##HL7 FHIR R4 Resource Mapping (GET /fhir/export)",
                "• Patient: 14-digit ABHA ID (healthid.abdm.gov.in)",
                "• Device: cardiotwin-esp32-01 (Firmware v4.1.0)",
                "• Observation (HR): LOINC 8867-4 (beats/min)",
                "• Observation (RMSSD): LOINC 80404-7 (ms)",
                "• Observation (Rhythm): SNOMED-CT 361137007",
                "• Observation (Instability): CARDIOTWIN-INSTABILITY",
                "• RiskAssessment (10Y CVD + 6H Forecast): LOINC 79423-0",
                "",
                "##Primary Backend REST & WebSocket Endpoints",
                "• POST /data & /ingest_telemetry (ESP32 50-sample chunks)",
                "• GET  /twin/status (Full fused EHR + Live + 2h/6h state)",
                "• POST /twin/simulate (Dual-Horizon 24h + 10yr What-If)",
                "• POST /twin/scenario (Inject AFib, Tachy, Motion, Liftoff)",
                "• POST /baseline/calibrate & GET /baseline/status",
                "• GET  /signal/gate & GET /telemetry/integrity",
                "• GET  /explainability/shap & /transparency/evidence_ledger",
                "",
                "##Automated Test Verification Suite (54 / 54 Passing)",
                "• test_cardiotwin.py (40 unit & API contract tests)",
                "• test_instability_target_validation.py (14 target tests)"
            ],
            header_bg=HEX["pine"]
        )

        ax.text(8.0, 0.45, "Clinical Regulatory Boundary: CardioTwin Sentinel is an investigational clinical decision-support prototype. Single-channel optical PPG is not a 12-lead ECG and requires confirmatory physician review.", color=HEX["slate"], fontsize=8.5, style="italic", ha="center")

        pdf.savefig(fig)
        plt.close(fig)

    print(f"[+] Generated 2-Page Vector Architecture PDF -> {PDF_OUT}")


# ===========================================================================
# PART 3: GENERATE 12-SLIDE EXECUTIVE PRESENTATION PPTX
# ===========================================================================
def add_slide_chrome(slide, prs, section_tag, title_text, subtitle_text, page_num):
    # Warm parchment background
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = rgb(HEX["bg"])
    bg.line.fill.background()

    # Top thin teal accent bar
    top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.08))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = rgb(HEX["teal"])
    top_bar.line.fill.background()

    # Section Eyebrow Tag
    tb_tag = slide.shapes.add_textbox(Inches(0.65), Inches(0.32), Inches(10), Inches(0.3))
    tf_tag = tb_tag.text_frame
    tf_tag.word_wrap = True
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = section_tag.upper()
    p_tag.font.size = Pt(10)
    p_tag.font.bold = True
    p_tag.font.color.rgb = rgb(HEX["teal"])
    p_tag.font.name = "Calibri"

    # Main Action Title
    tb_title = slide.shapes.add_textbox(Inches(0.65), Inches(0.58), Inches(12.0), Inches(0.65))
    tf_title = tb_title.text_frame
    tf_title.word_wrap = True
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.size = Pt(25)
    p_title.font.bold = True
    p_title.font.color.rgb = rgb(HEX["pine"])
    p_title.font.name = "Georgia"

    # Subtitle
    if subtitle_text:
        tb_sub = slide.shapes.add_textbox(Inches(0.65), Inches(1.12), Inches(12.0), Inches(0.4))
        tf_sub = tb_sub.text_frame
        tf_sub.word_wrap = True
        p_sub = tf_sub.paragraphs[0]
        p_sub.text = subtitle_text
        p_sub.font.size = Pt(13)
        p_sub.font.color.rgb = rgb(HEX["slate"])
        p_sub.font.name = "Calibri"

    # Footer Bar
    tb_foot = slide.shapes.add_textbox(Inches(0.65), Inches(7.05), Inches(12.0), Inches(0.3))
    tf_foot = tb_foot.text_frame
    p_foot = tf_foot.paragraphs[0]
    p_foot.text = f"CardioTwin Sentinel v4.1  ·  Team Root Access (Harsh Mishra, VNIT Nagpur)  ·  Investigational Decision-Support Prototype (Non-Diagnostic)          {page_num} / 12"
    p_foot.font.size = Pt(9.5)
    p_foot.font.color.rgb = rgb(HEX["muted"])
    p_foot.font.name = "Calibri"


def add_card(slide, x, y, w, h, title, bullets, header_hex=None, bg_hex=HEX["card"], border_hex=HEX["border"], title_pt=14, body_pt=11.5):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    card.adjustments[0] = 0.04
    card.fill.solid()
    card.fill.fore_color.rgb = rgb(bg_hex)
    card.line.color.rgb = rgb(border_hex)
    card.line.width = Pt(1)

    curr_y = y + 0.16
    if header_hex:
        hbar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.44))
        hbar.adjustments[0] = 0.04
        hbar.fill.solid()
        hbar.fill.fore_color.rgb = rgb(header_hex)
        hbar.line.fill.background()
        tb_h = slide.shapes.add_textbox(Inches(x + 0.16), Inches(y + 0.06), Inches(w - 0.32), Inches(0.34))
        p_h = tb_h.text_frame.paragraphs[0]
        p_h.text = title
        p_h.font.size = Pt(12.5)
        p_h.font.bold = True
        p_h.font.color.rgb = RGBColor(255, 255, 255)
        p_h.font.name = "Calibri"
        curr_y = y + 0.54
    elif title:
        tb_t = slide.shapes.add_textbox(Inches(x + 0.18), Inches(curr_y), Inches(w - 0.36), Inches(0.4))
        tf_t = tb_t.text_frame
        tf_t.word_wrap = True
        p_t = tf_t.paragraphs[0]
        p_t.text = title
        p_t.font.size = Pt(title_pt)
        p_t.font.bold = True
        p_t.font.color.rgb = rgb(HEX["pine"])
        p_t.font.name = "Georgia"
        curr_y += 0.42

    if bullets:
        tb_b = slide.shapes.add_textbox(Inches(x + 0.18), Inches(curr_y), Inches(w - 0.36), Inches(h - (curr_y - y) - 0.12))
        tf_b = tb_b.text_frame
        tf_b.word_wrap = True
        for idx, b_text in enumerate(bullets):
            p = tf_b.paragraphs[0] if idx == 0 else tf_b.add_paragraph()
            p.text = b_text
            p.font.size = Pt(body_pt)
            p.font.color.rgb = rgb(HEX["pine"] if b_text.startswith("•") else HEX["slate"])
            p.font.bold = b_text.startswith("★") or b_text.startswith("▸")
            p.font.name = "Calibri"
            p.space_after = Pt(5)


def add_metric_box(slide, x, y, w, h, big_num, label, sublabel="", accent_hex=HEX["teal"], bg_hex=HEX["card"]):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.adjustments[0] = 0.06
    box.fill.solid()
    box.fill.fore_color.rgb = rgb(bg_hex)
    box.line.color.rgb = rgb(HEX["border"])
    box.line.width = Pt(1)

    tb = slide.shapes.add_textbox(Inches(x + 0.15), Inches(y + 0.12), Inches(w - 0.3), Inches(h - 0.24))
    tf = tb.text_frame
    tf.word_wrap = True

    p1 = tf.paragraphs[0]
    p1.text = big_num
    p1.font.size = Pt(30)
    p1.font.bold = True
    p1.font.color.rgb = rgb(accent_hex)
    p1.font.name = "Georgia"

    p2 = tf.add_paragraph()
    p2.text = label
    p2.font.size = Pt(11.5)
    p2.font.bold = True
    p2.font.color.rgb = rgb(HEX["pine"])
    p2.font.name = "Calibri"
    p2.space_before = Pt(2)

    if sublabel:
        p3 = tf.add_paragraph()
        p3.text = sublabel
        p3.font.size = Pt(9.5)
        p3.font.color.rgb = rgb(HEX["slate"])
        p3.font.name = "Calibri"


def generate_presentation_pptx(wave_img, bench_img, shap_img):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # -----------------------------------------------------------------------
    # SLIDE 1: TITLE & EXECUTIVE SUMMARY
    # -----------------------------------------------------------------------
    s1 = prs.slides.add_slide(blank)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = rgb(HEX["pine_dark"])
    bg1.line.fill.background()

    tb = s1.shapes.add_textbox(Inches(0.8), Inches(0.85), Inches(11.5), Inches(4.2))
    tf = tb.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "HAPPIEST HEALTH  ·  DIGITAL TWIN CHALLENGE 2026"
    p0.font.size = Pt(12)
    p0.font.bold = True
    p0.font.color.rgb = rgb("#A8D3BD")

    p1 = tf.add_paragraph()
    p1.text = "CardioTwin Sentinel"
    p1.font.size = Pt(50)
    p1.font.bold = True
    p1.font.color.rgb = RGBColor(255, 255, 255)
    p1.font.name = "Georgia"
    p1.space_before = Pt(10)

    p2 = tf.add_paragraph()
    p2.text = "An Ultra-Low-Cost (₹1,165) Proactive Cardiovascular & Cardiometabolic Digital Twin"
    p2.font.size = Pt(20)
    p2.font.color.rgb = rgb("#DCECE3")
    p2.space_before = Pt(8)

    p3 = tf.add_paragraph()
    p3.text = "Fusing Longitudinal EHR + 7-Day Wearable Trajectories + 100 Hz Edge Optical Telemetry to Predict Adverse Cardiac Decompensation Hours in Advance."
    p3.font.size = Pt(14)
    p3.font.color.rgb = rgb("#9AB8B2")
    p3.space_before = Pt(14)

    # 4 Hero KPIs on Cover
    cover_kpis = [
        ("₹1,165 (~$14)", "Edge IoT Hardware Node", "ESP32 FreeRTOS + MAX30102 100Hz"),
        ("98.83% / 90.09%", "Normal Spec / Anomaly Recall", "2,271 Patients (Zero-Leakage CV)"),
        ("2h & 6h Horizon", "Proactive Early Warning", "EHR-Coupled + 7d Nocturnal HRV"),
        ("ABDM FHIR R4", "e-Sanjeevani Ready", "LOINC / SNOMED + 54 Passing Tests")
    ]
    for i, (k_val, k_lbl, k_sub) in enumerate(cover_kpis):
        add_metric_box(s1, 0.8 + i * 2.95, 4.65, 2.75, 1.55, k_val, k_lbl, k_sub, accent_hex=HEX["teal"], bg_hex=HEX["bg"])

    tb_aut = s1.shapes.add_textbox(Inches(0.8), Inches(6.55), Inches(11.5), Inches(0.5))
    p_aut = tb_aut.text_frame.paragraphs[0]
    p_aut.text = "Team Root Access (Solo)  ·  Harsh Mishra  ·  Visvesvaraya National Institute of Technology (VNIT), Nagpur  ·  MIT Open-Source License"
    p_aut.font.size = Pt(11.5)
    p_aut.font.bold = True
    p_aut.font.color.rgb = rgb("#A8D3BD")

    # -----------------------------------------------------------------------
    # SLIDE 2: THE CLINICAL PROBLEM IN INDIA
    # -----------------------------------------------------------------------
    s2 = prs.slides.add_slide(blank)
    add_slide_chrome(s2, prs, "01 · Clinical Problem Statement", "India's Cardiovascular Crisis Faces an Unsustainable Screening Trilemma", "South Asians experience coronary artery disease 10–15 years earlier, yet 160,000+ primary care centres lack intelligent triage tools.", 2)

    add_metric_box(s2, 0.65, 1.70, 3.8, 1.55, "28% of Deaths", "Leading Cause of Mortality in India", "High burden of silent AFib & premature CAD", HEX["rose"], HEX["rose_bg"])
    add_metric_box(s2, 4.75, 1.70, 3.8, 1.55, "10–15 Years", "Earlier Onset in South Asians", "Western Framingham scores underestimate risk", HEX["amber"], HEX["amber_bg"])
    add_metric_box(s2, 8.85, 1.70, 3.8, 1.55, "160,000+ HWCs", "Ayushman Bharat Primary Centres", "Zero low-cost longitudinal screening tools", HEX["teal"], HEX["teal_light"])

    add_card(s2, 0.65, 3.50, 5.85, 3.3, "Why Existing Devices Fail Primary Care", [
        "• Consumer Smartwatches (₹41,900–₹89,900): Unaffordable for 95% of rural/semi-urban patients; proprietary iOS lock-in; uncalibrated population defaults.",
        "• Clinical 24–48h Holter Monitors (₹5,000–₹12,000/rental): Requires hospital referral, chest electrodes, and 2–3 days for manual review.",
        "• OTC Pulse Oximeters (₹600–₹1,200): Outputs a single instantaneous number with zero memory, zero personal baseline, and zero EHR context."
    ], header_hex=HEX["pine"])

    add_card(s2, 6.80, 3.50, 5.85, 3.3, "The CardioTwin Sentinel Solution", [
        "★ ₹1,165 (~$14) Edge IoT Node + Stateful Clinical Digital Twin.",
        "• Learns each patient's own resting physiology via a 2-minute seated empirical calibration (Median + MAD).",
        "• Fuses Static EHR (labs, active medications, South Asian 1.45x Framingham) with Dynamic 100 Hz PPG & 7-day wearable sleep/HRV trajectories.",
        "• Predicts hemodynamic decompensation 2 to 6 hours in advance and simulates Dual-Horizon What-If treatment outcomes."
    ], header_hex=HEX["teal"])

    # -----------------------------------------------------------------------
    # SLIDE 3: 5-STAGE SYSTEM ARCHITECTURE
    # -----------------------------------------------------------------------
    s3 = prs.slides.add_slide(blank)
    add_slide_chrome(s3, prs, "02 · System Architecture Overview", "Five-Stage Multimodal Digital Twin Pipeline", "Seamless fusion of Static EHR (Stream 1) and High-Frequency Wearable Telemetry (Stream 2).", 3)

    stages = [
        ("01 · EDGE HARDWARE", "ESP32 + MAX30102", [
            "• ₹1,165 ($14) unit BOM",
            "• Core 1: 100 Hz ISR timer",
            "• Core 0: Async WiFi POST",
            "• SH1106 OLED live HUD",
            "• Microsecond jitter deltas"
        ], HEX["pine"]),
        ("02 · SIGNAL GATE", "5-Part Decoupled Gate", [
            "• Blocks finger-off (<20k)",
            "• Blocks saturation (>260k)",
            "• Blocks timing drops",
            "★ Passes AFib & extreme",
            "  rates through to AI"
        ], HEX["teal"]),
        ("03 · DUAL AI ENGINE", "Trees + Inception-1D", [
            "• 27 HRV/Spectral features",
            "• XGB + RF + ExtraTrees",
            "• 393K-param 1D-CNN",
            "• Temp-Scaled Late Fusion",
            "• SHAP TreeExplainer XAI"
        ], HEX["pine"]),
        ("04 · TWIN CORE", "EHR x Live Coupling", [
            "• 2-min Median+MAD baseline",
            "• M_EHR substrate coupling",
            "• Beta-Blockade Escape",
            "• 2h/6h Proactive Forecast",
            "• Dual-Horizon What-If"
        ], HEX["teal"]),
        ("05 · CLINICIAN UI", "Portal & ABDM FHIR", [
            "• React 19 Web Dashboard",
            "• React Native Mobile App",
            "• Evidence Ledger honesty",
            "• HL7 FHIR R4 Bundle export",
            "• DPDP Act 2023 privacy"
        ], HEX["pine"])
    ]
    for i, (st_head, st_sub, st_bullets, st_col) in enumerate(stages):
        add_card(s3, 0.65 + i * 2.45, 1.75, 2.30, 4.0, st_head, [f"▸ {st_sub}"] + st_bullets, header_hex=st_col, body_pt=10.5)

    add_card(s3, 0.65, 5.95, 12.0, 0.95, "", [
        "★ Data Stream Fusion Contract:  [Stream 1: Synthetic Indian EHR Cohort (100 patients, Labs, Meds, 1.45x Framingham)]  +  [Stream 2: 100 Hz ESP32 PPG + 7-Day Sleep/Nocturnal RMSSD]  --->  Proactive 2h/6h Early Warning & Dual-Horizon What-If Simulation."
    ], bg_hex=HEX["teal_light"], border_hex=HEX["teal"], body_pt=11.5)

    # -----------------------------------------------------------------------
    # SLIDE 4: STAGE 1 - EDGE HARDWARE & FREERTOS
    # -----------------------------------------------------------------------
    s4 = prs.slides.add_slide(blank)
    add_slide_chrome(s4, prs, "03 · Stage 1: Edge Hardware & Firmware", "₹1,165 ($14) Node Engineered Around a Hard 10,000 µs Real-Time Deadline", "FreeRTOS dual-core task isolation prevents WiFi network retries from ever distorting optical waveform morphology.", 4)

    add_card(s4, 0.65, 1.70, 5.8, 2.45, "Core 1: Real-Time Acquisition (Priority 5)", [
        "• Samples MAX30102 (880nm IR, 18-bit ADC) at exactly 100.0 Hz using esp_timer_get_time() + vTaskDelayUntil(10ms).",
        "• Pushes 50-sample chunks (500ms) with per-sample microsecond deltas (deltas_us[]) into lock-free FreeRTOS chunkQueue.",
        "• Zero HTTP or blocking socket calls permitted on Core 1."
    ], header_hex=HEX["pine"])

    add_card(s4, 0.65, 4.35, 5.8, 2.45, "Core 0: Async Telemetry & Integrity (Priority 1)", [
        "• Pulls completed chunks from chunkQueue and streams keep-alive JSON payloads to POST /data.",
        "• Transmits device_boot_id and monotonic sequence numbers to detect hardware reboots, packet gaps, or duplicates.",
        "• Background loop drives local 128x64 OLED at ~8 FPS."
    ], header_hex=HEX["teal"])

    add_card(s4, 6.75, 1.70, 5.9, 5.10, "Bill of Materials & Health-Economics Advantage", [
        "▸ Complete Hardware Node BOM: ₹1,165 (~$14.07) | < ₹950 @ 1k units",
        "  • ESP32-WROOM-32D Dual-Core MCU (240 MHz):  ₹480",
        "  • MAX30102 Optical PPG Sensor (18-bit ADC): ₹220",
        "  • TP4056 USB-C Charger + 650mAh LiPo (6-8h): ₹210",
        "  • SH1106 0.96\" I2C OLED Display:            ₹140",
        "  • 3D-Printed Biocompatible PLA Clip + Passives: ₹115",
        "",
        "▸ Deployment Comparison vs. Commercial Modalities:",
        "  • Apple Watch Series 9 (₹41,900+): >35x more expensive, iOS locked.",
        "  • Clinical Holter (₹5,000+/rental): 2–3 day delay, non-reusable leads.",
        "  • OTC Oximeter (₹800): Instantaneous number only, zero intelligence."
    ], header_hex=HEX["pine_dark"])

    # -----------------------------------------------------------------------
    # SLIDE 5: STAGE 2 - DECOUPLED 5-PART SIGNAL GATE
    # -----------------------------------------------------------------------
    s5 = prs.slides.add_slide(blank)
    add_slide_chrome(s5, prs, "04 · Stage 2: Decoupled Signal Reliability Gate", "Physical Failures Block the AI. Genuine Arrhythmias Pass Through.", "Conventional quality filters discard irregular rhythms as 'noise'—blindfolding the AI during Atrial Fibrillation.", 5)

    add_card(s5, 0.65, 1.70, 5.6, 2.45, "Axis 1: Physical Reliability (May Block AI)", [
        "1. Finger-Off / Liftoff: Optical IR < 20,000 ADC -> FINGER_OFF.",
        "2. Transimpedance Saturation: ADC > 260,000 (>5% clipped) -> SATURATED.",
        "3. Sample Timing Jitter: |fs - 100Hz| > 15Hz or drops -> POOR_TIMING.",
        "4. Pulse Morphology & Stability: <3 systolic peaks or <3 clean windows."
    ], header_hex=HEX["rose"])

    add_card(s5, 0.65, 4.35, 5.6, 2.45, "Axis 2: Physiological Observation (Never Blocks AI)", [
        "★ Chaotic Beat Intervals (RR-CV > 0.35): Tagged as IRREGULAR_RHYTHM and passed directly to Dual-Modality AI to capture AFib.",
        "★ Extreme Rates (<40 or >180 BPM): Tagged RECHECK_REQUIRED and passed to AI for severe bradycardia / tachycardia screening.",
        "★ Verified in 54 Automated Tests: 100% finger-off rejection, 0 false alarms."
    ], header_hex=HEX["green"])

    s5.shapes.add_picture(wave_img, Inches(6.50), Inches(1.70), width=Inches(6.15))

    # -----------------------------------------------------------------------
    # SLIDE 6: STAGE 3 - DUAL-MODALITY AI & BENCHMARKS
    # -----------------------------------------------------------------------
    s6 = prs.slides.add_slide(blank)
    add_slide_chrome(s6, prs, "05 · Stage 3: Dual-Modality AI & Clinical Triage Benchmark", "Temperature-Scaled Fusion Across 2,271 Real Patients (Zero Leakage)", "Combining 27 hand-crafted physiological HRV biomarkers with multi-scale 1D convolutional waveform morphology.", 6)

    s6.shapes.add_picture(bench_img, Inches(0.65), Inches(1.65), width=Inches(8.1))

    add_card(s6, 8.95, 1.65, 3.7, 5.15, "Two-Level Validation Rigor", [
        "▸ 3-Tier Clinical Actionability:",
        "• 98.83% Normal Specificity (eliminates clinician false-alarm fatigue).",
        "• 90.09% Tier-2 Recall on Actionable Rate & Atrial Anomalies (AFib, Brady, Tachy, Paced).",
        "• 75.68% Overall Triage Accuracy.",
        "",
        "▸ 8-Class Research Granularity:",
        "• 54.40% Macro-F1 (4.35x random guess) under strict patient-isolated StratifiedGroupKFold.",
        "• 393K-param Inception-1D runs in 4.2 ms on standard CPU."
    ], header_hex=HEX["pine"])

    # -----------------------------------------------------------------------
    # SLIDE 7: EXPLAINABLE AI (SHAP) & SCIENTIFIC HONESTY
    # -----------------------------------------------------------------------
    s7 = prs.slides.add_slide(blank)
    add_slide_chrome(s7, prs, "06 · Explainable AI & Scientific Honesty", "Every Screening Output Explains Why—and Declares What It Cannot Know", "Clinicians receive game-theoretic SHAP biomarker attributions alongside a machine-readable Evidence Ledger.", 7)

    s7.shapes.add_picture(shap_img, Inches(0.65), Inches(1.70), width=Inches(5.8))

    add_card(s7, 6.65, 1.70, 6.0, 2.45, "Cross-Dataset Source Confounding Audit", [
        "• We audited 4 clinical databases (MIMIC-III, CinC 2015, BUT PPG, BIDMC).",
        "• A domain classifier predicting dataset origin from biomarkers alone hits 77.08% accuracy—proving that 100% of VT/Asystole records carry CinC 2015 ICU hardware signatures.",
        "• Instead of hiding this behind inflated claims, CardioTwin discloses it in every API response and frames VT as an urgent ECG referral flag."
    ], header_hex=HEX["amber"])

    add_card(s7, 6.65, 4.35, 6.0, 2.45, "Machine-Readable Evidence Ledger", [
        "• PPG != 12-Lead ECG: Optical microvascular pulse waves cannot measure electrical P-waves, QRS duration, or ST-segment elevation.",
        "• SpO2 Transparency: Single-wavelength 880nm IR cannot physically compute ratiometric SpO2—explicitly declared UNAVAILABLE, never fabricated.",
        "• Multi-Window Consensus: Requires >=3/4 recent windows + asymmetric confidence thresholds (0.75 for VT/VFib vs 0.50 for Sinus)."
    ], header_hex=HEX["pine"])

    # -----------------------------------------------------------------------
    # SLIDE 8: PERSONAL BASELINE & EHR VULNERABILITY COUPLING
    # -----------------------------------------------------------------------
    s8 = prs.slides.add_slide(blank)
    add_slide_chrome(s8, prs, "07 · Stage 4A: Personal Baseline & True Multimodal Coupling", "Conditioning Acute Optical Sensitivity on the Patient's EHR Substrate", "A +22 BPM pulse rise in a healthy 27-year-old is benign; in a 63-year-old Post-PCI patient on Metoprolol, it is Beta-Blockade Escape.", 8)

    add_card(s8, 0.65, 1.70, 5.85, 5.10, "1. Empirical 2-Minute Seated Baseline (Zero Guessing)", [
        "• Why Population Norms Fail: Resting HR is 48 BPM in endurance runners vs 84 BPM in sedentary patients.",
        "• Uncalibrated Guardrail: Returns instability_score: null ('Personal baseline required') until calibrated.",
        "• 2-Minute Protocol: 30s settling + >=6 clean 10s windows.",
        "• Non-Parametric Fingerprint: Computes personal Median & MAD for BPM, RMSSD, and RR-CV (50% breakdown point against outliers).",
        "• Governance: 30-day TTL expiration + automatic invalidation on device_id or LED current change."
    ], header_hex=HEX["pine"])

    add_card(s8, 6.80, 1.70, 5.85, 5.10, "2. Multimodal EHR Vulnerability Coupling (M_EHR)", [
        "★ Stream 1 (EHR) Dynamically Modulates Stream 2 (Live PPG):",
        "• Pharmacological Beta-Blockade Escape: Detects pulse >= 90 BPM despite active Metoprolol / Bisoprolol therapy (sympathetic breakthrough).",
        "• Subclinical AFib Prodrome: Amplifies RR-CV >= 18% in patients with documented Paroxysmal AFib history.",
        "• Autonomic Vagal Withdrawal: Flags RMSSD < 22ms in Post-PCI CAD or uncontrolled Type-2 Diabetes (HbA1c >= 7.0%).",
        "• Substrate Multiplier M_EHR in [1.00x, 1.40x]: Scales acute instability and proactive horizon velocity by clinical fragility."
    ], header_hex=HEX["teal"])

    # -----------------------------------------------------------------------
    # SLIDE 9: PROACTIVE 2H / 6H FORECASTER & 7-DAY WEARABLE TRENDS
    # -----------------------------------------------------------------------
    s9 = prs.slides.add_slide(blank)
    add_slide_chrome(s9, prs, "08 · Stage 4B: Proactive 2-Hour & 6-Hour Adverse Event Forecaster", "Predicting Hemodynamic Decompensation Before Crisis Strikes", "Directly fulfills the challenge prompt by fusing 7-day wearable sleep & nocturnal HRV trends with real-time state velocity.", 9)

    add_card(s9, 0.65, 1.70, 5.9, 5.10, "7-Day Wearable Trajectory Inputs (Stream 2 Longitudinal)", [
        "• Continuous 7-Day Tracking across 4 Wearable Streams:",
        "  1. Nocturnal RMSSD (ms): Tracks multi-day parasympathetic decay (e.g., 42ms -> 22ms over 7 nights preceding decompensation).",
        "  2. Daily Resting Heart Rate (BPM): Captures creeping sympathetic creep (e.g., 68 -> 78 BPM).",
        "  3. Sleep Efficiency (%): Identifies nocturnal fragmentation (88% -> 71%).",
        "  4. Daily Step Count: Captures functional exercise intolerance.",
        "• Visualized via 4 interactive SVG Sparklines on the Clinician Twin tab."
    ], header_hex=HEX["pine"])

    add_card(s9, 6.85, 1.70, 5.8, 5.10, "State-Space Horizon Extrapolation (2h & 6h Forecast)", [
        "▸ Mathematical Horizon Model:",
        "  I_hat(t + dt) = clip(I_t + (b_acute * dI/dt + b_7d * Slope_7d) * M_EHR)",
        "",
        "▸ 4 Clinical Early-Warning Horizon States:",
        "  • STABLE_HORIZON: Concordant 7d HRV & resting pulse.",
        "  • EARLY_PRODROMAL_DRIFT: Subtle vagal suppression + EHR flag.",
        "  • HIGH_RISK_WITHIN_6H: Projected instability crosses 60/100.",
        "  • IMMINENT_DECOMPENSATION_2H: Projected instability >= 70/100,",
        "    outputting exact Estimated Time-to-Threshold (e.g., ~2.5 hours)."
    ], header_hex=HEX["amber"])

    # -----------------------------------------------------------------------
    # SLIDE 10: DUAL-HORIZON WHAT-IF SIMULATOR
    # -----------------------------------------------------------------------
    s10 = prs.slides.add_slide(blank)
    add_slide_chrome(s10, prs, "09 · Stage 4C: Dual-Horizon 'What-If' Treatment Simulator", "Connecting 24-Hour Hemodynamic Twin Response with 10-Year ASCVD Prevention", "EHR-aware simulation distinguishes active prescriptions (Adherence/Titration) from new therapies like SGLT2 Inhibitors.", 10)

    add_card(s10, 0.65, 1.70, 5.85, 5.10, "South Asian 1.45x Recalibration & EHR Awareness", [
        "• Standard Framingham (derived on Western cohorts) underestimates South Asian risk by 40–50%. Applying the 1.45x WHO/ACC multiplier shifts a 16.8% patient to 24.4% (crossing the 20% statin threshold).",
        "• Smart EHR Medication Detection: Inspects patient_ehr.medications. For PAT001 (already on Metoprolol 50mg & Atorvastatin 40mg), levers model Adherence & Titration rather than duplicate prescriptions.",
        "• New Cardiometabolic Levers: Adds Dapagliflozin 10mg (SGLT2i: -18% CVD risk in T2DM/CAD), Ramipril/Telmisartan, SBP target, and Smoking Cessation."
    ], header_hex=HEX["pine"])

    add_card(s10, 6.80, 1.70, 5.85, 5.10, "Dual-Horizon Simulation Output (PAT001 Case Study)", [
        "▸ Horizon 1: Long-Term 10-Year ASCVD Trajectory",
        "  • Baseline Recalibrated Risk: 81.8% (Post-PCI CAD, SBP 143, HbA1c 7.4%, 1.45x Multiplier)",
        "  • Optimized Protocol Risk:    34.8% (-64.2% Absolute Risk Reduction)",
        "  • Biological Vascular Age:    85 yrs  --->  68 yrs (-17 yrs shift)",
        "",
        "▸ Horizon 2: Short-Term 24-Hour Hemodynamic Twin Response",
        "  • Simulated Resting Pulse:    70 BPM  --->  58 BPM (Beta-blockade)",
        "  • Simulated Systolic BP:      143 mmHg ---> 121 mmHg",
        "  • Autonomic Vagal Recovery:   +13.0 ms RMSSD gain",
        "  • Projected Instability:      Drops into Stable band (<20/100)"
    ], header_hex=HEX["teal"])

    # -----------------------------------------------------------------------
    # SLIDE 11: CLINICIAN DASHBOARD, ABDM FHIR R4 & EDGE PRIVACY
    # -----------------------------------------------------------------------
    s11 = prs.slides.add_slide(blank)
    add_slide_chrome(s11, prs, "10 · Stage 5: Clinician Command Portal & ABDM Interoperability", "Built for Doctor Decision Support and National e-Sanjeevani Tele-Consultation", "4-Tab React 19 Web Portal + React Native Mobile Companion + 1-Click HL7 FHIR R4 Bundle Export.", 11)

    add_card(s11, 0.65, 1.70, 6.0, 5.10, "Clinician Command Portal (React 19 + Mobile Companion)", [
        "• Tab 1 — Home: Patient care story, biological vascular age, baseline freshness badge.",
        "• Tab 2 — Your Twin: 8-Biomarker Clinical Lab Panel (Total Chol, LDL, HDL, TG, Glucose, HbA1c, hs-CRP, BP with abnormal flags), Active Pharmacotherapy Table, and 7-Day Wearable Sparklines.",
        "• Tab 3 — Live Check: 100 Hz SVG oscilloscope, 4-metric HRV strip (RMSSD, SDNN, RR-CV, SQI), Dual-Modality AI & Persistence panel, SHAP drivers, and Proactive 2h/6h Early Warning Banner.",
        "• Tab 4 — Explore Changes: Dual-Horizon What-If simulator + guided scenario injectors (Quiet Baseline, Tachycardia, AFib, Motion, Liftoff)."
    ], header_hex=HEX["pine"])

    add_card(s11, 6.90, 1.70, 5.75, 5.10, "ABDM HL7 FHIR R4 Export & DPDP 2023 Privacy", [
        "▸ Live Endpoint: GET /fhir/export generates a standard FHIR R4 Bundle:",
        "  • Patient: Linked to 14-digit ABHA ID (healthid.abdm.gov.in)",
        "  • Observation: Heart Rate (LOINC 8867-4) & RMSSD (LOINC 80404-7)",
        "  • Observation: Pulse Rhythm (SNOMED-CT 361137007) & Instability",
        "  • RiskAssessment: 10Y Framingham + 6H Decompensation (LOINC 79423-0)",
        "",
        "▸ Edge-First Privacy (India DPDP Act 2023 Aligned):",
        "  • Waveform Ephemerality: Raw 100 Hz samples exist only in rolling RAM buffers and are purged immediately after 27-biomarker extraction.",
        "  • Deterministic Pseudonymization (PAT001..PAT100) + 30-day TTL."
    ], header_hex=HEX["teal"])

    # -----------------------------------------------------------------------
    # SLIDE 12: VERIFICATION SCORECARD & LIVE DEMO ROADMAP
    # -----------------------------------------------------------------------
    s12 = prs.slides.add_slide(blank)
    add_slide_chrome(s12, prs, "11 · Verification Rigor & Live Demonstration Walkthrough", "54 Automated Tests Passing (100% Success) Across Hardware, AI & Clinical Rules", "Complete reproducibility from ESP32 FreeRTOS C++ firmware to Python ML backend and React 19 UI.", 12)

    add_card(s12, 0.65, 1.70, 6.2, 5.10, "Controlled Physiological Target Validation Matrix", [
        "▸ Verified in tests/test_instability_target_validation.py & test_cardiotwin.py:",
        "  1. Quiet Seated Baseline      ---> Stable (Score 0–20, 0 false flags)",
        "  2. Finger Liftoff / Flatline  ---> Gated (FINGER_OFF, Score: null)",
        "  3. Hand Motion / Clipping     ---> Gated (SENSOR_SATURATED, Score: null)",
        "  4. Standing Transition        ---> Mild Departure (Score 20–40)",
        "  5. Post-Standing Recovery     ---> Returns to Stable (<20 within 3 windows)",
        "  6. Sustained Tachycardia      ---> Sustained Departure (Score 40–100, Review)",
        "  7. Irregular Pulse (AFib)     ---> Passes Gate -> Review Recommended",
        "  8. FHIR R4 & Proactive 2h/6h  ---> Verified Schema & EHR Coupling"
    ], header_hex=HEX["pine"])

    add_card(s12, 7.10, 1.70, 5.55, 5.10, "End-to-End Live Video Demo Flow", [
        "1. Hardware & Firmware Proof: Show ESP32 + MAX30102 + OLED node running Dual-Core FreeRTOS @ 100 Hz.",
        "2. Patient Twin Load: Load PAT001 (Praveen Choudhury, 63M, Post-PCI CAD, HbA1c 7.4%, hs-CRP 3.61) & inspect 7-day nocturnal RMSSD decline.",
        "3. Live Check & Gate Stress-Test: Trigger 2-min calibration, inject Calm Sinus -> Stress Tachycardia (Beta-Blockade Escape fires) -> AFib Episode (2h/6h Proactive Early Warning triggers).",
        "4. Dual-Horizon What-If & FHIR R4: Simulate Dapagliflozin + Statin + SBP target (99% -> 34.8% risk) and export HL7 FHIR R4 Bundle."
    ], header_hex=HEX["teal"])

    prs.save(PPTX_OUT)
    print(f"[+] Generated 12-Slide Executive Presentation PPTX -> {PPTX_OUT}")


if __name__ == "__main__":
    w_img, b_img, s_img = generate_chart_assets()
    generate_architecture_pdf()
    generate_presentation_pptx(w_img, b_img, s_img)
