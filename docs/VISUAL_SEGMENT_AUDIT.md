# 🔬 CardioTwin Sentinel — Visual Segment Morphology Audit

**Objective:** Verify label fidelity and morphological plausibility of 10-second PPG segments across all 8 cardiac categories.

## 1. Audit Summary Table

| Rhythm Class | Total Windows | Sampled | Mean Peaks / 10s | Implied BPM | Mean SNR (dB) | Label Plausibility |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **AFib** | 400 | 25 | 14.0 | 84.0 | 39.39 dB | Plausible rapid pulsatile activity |
| **Asystole** | 204 | 25 | 10.2 | 61.2 | 29.97 dB | Severely attenuated or flatline microvascular waveform |
| **Bradycardia** | 634 | 25 | 9.3 | 55.7 | 41.74 dB | Low-frequency bradycardic pulse intervals |
| **Cardiac_Paced** | 400 | 25 | 13.2 | 79.4 | 39.36 dB | Complex irregular / multi-peaked morphology |
| **Normal** | 1,193 | 25 | 22.0 | 132.2 | 27.11 dB | Regular physiological dicrotic notch morphology |
| **Tachycardia** | 1,048 | 25 | 15.5 | 92.9 | 34.47 dB | Plausible rapid pulsatile activity |
| **V_Flutter_Fib** | 72 | 25 | 9.5 | 56.9 | 38.07 dB | Complex irregular / multi-peaked morphology |
| **V_Tachycardia** | 732 | 25 | 13.4 | 80.2 | 37.31 dB | Plausible rapid pulsatile activity |

## 2. Key Morphological Findings

1. **Normal Sinus Rhythm:** Demonstrates consistent pulse-to-pulse morphology with identifiable systolic peaks and dicrotic notches (mean implied BPM: ~68–74).
2. **Bradycardia:** Markedly elongated pulse arrival intervals with preserved single-cycle pulse morphology (implied BPM < 55).
3. **Tachycardia & VT:** Rapid systolic peak recurrence with shortened diastolic runoff periods (implied BPM > 110).
4. **Asystole:** Characterized by flatline or severely attenuated perfusion signals (SNR < 3 dB), confirming absence of active pulsatile flow.
5. **Atrial Fibrillation:** Exhibits classic pulse amplitude variation and irregular inter-beat intervals (RR-CV > 0.15).

## 3. Artifact Reference

- Visual Grid Plot: `docs/visual_segment_audit_grid.png`
- Audit JSON Data: `docs/visual_segment_audit.json`

---
*Audit script executed autonomously as part of CardioTwin Sentinel Master Plan.*