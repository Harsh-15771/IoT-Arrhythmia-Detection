import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  StatusBar,
  Dimensions,
  ScrollView,
  Platform,
} from "react-native";
import Svg, {
  Path,
  Line,
  Defs,
  LinearGradient,
  Stop,
  Rect,
  Circle,
  Polyline,
} from "react-native-svg";

// ─── CONFIGURATION ──────────────────────────────────────────
const SERVER_IP = "10.139.96.96";
const SERVER_PORT = 5000;
const BASE_URL = `http://${SERVER_IP}:${SERVER_PORT}`;
const POLL_MS = 1000;
// ─────────────────────────────────────────────────────────────

const { width: SW } = Dimensions.get("window");
const GRAPH_W = SW - 48;
const GRAPH_H = 150;

// ─── CARDIOTWIN DESIGN SYSTEM PALETTE (MATCHES WEB APP) ──────
const T = {
  bg: "#F8F7F2",
  card: "#FFFFFF",
  cardBorder: "rgba(25, 59, 58, 0.09)",
  cardBorderStrong: "rgba(25, 59, 58, 0.16)",
  primary: "#167C76",
  primaryHover: "#136A65",
  teal: "#188F89",
  tealDark: "#1B403E",
  tealDeep: "#1D4F4C",
  textPrimary: "#1B403E",
  textSecondary: "#5B716E",
  textMuted: "#889895",
  waveStart: "#1B9A92",
  waveEnd: "#5CC5BC",
  greenBg: "#E4F2E9",
  greenText: "#186A5E",
  amberBg: "#F9EDD6",
  amberText: "#8A5A1E",
  roseBg: "#F8E0DC",
  roseText: "#9B3733",
  blueBg: "#E6F0F0",
  blueText: "#2C5D66",
  chipBg: "#EFF4ED",
  chipText: "#4F716D",
};

// ─── SAMPLE REALISTIC PULSE DATA FOR OFFLINE / DEMO ─────────
const SAMPLE_PPG = [
  32, 33, 35, 42, 60, 95, 150, 210, 245, 250, 230, 185, 145, 125, 115, 120,
  128, 125, 110, 85, 58, 42, 35, 32, 32, 33, 35, 42, 60, 95, 150, 210, 245,
  250, 230, 185, 145, 125, 115, 120, 128, 125, 110, 85, 58, 42, 35, 32, 32,
  33, 35, 42, 60, 95, 150, 210, 245, 250, 230, 185, 145, 125, 115, 120, 128,
  125, 110, 85, 58, 42, 35, 32, 32, 33, 35, 42, 60, 95, 150, 210, 245, 250,
  230, 185, 145, 125, 115, 120, 128, 125, 110, 85, 58, 42, 35, 32,
];

// ─── ICON COMPONENTS (PURE SVG — ZERO NATIVE DEPENDENCIES) ───
function HeartIcon({ size = 18, color = T.primary }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M19.5 12.572l-7.5 7.428l-7.5 -7.428a5 5 0 1 1 7.5 -6.566a5 5 0 1 1 7.5 6.572"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M12 7v4l2.5 1.5"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </Svg>
  );
}

function PulseIcon({ size = 18, color = T.primary }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M3 12h4l3 8l4 -16l3 8h4"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function UserIcon({ size = 18, color = T.primary }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="8" r="4" stroke={color} strokeWidth="2" />
      <Path
        d="M6 20v-1a6 6 0 0 1 12 0v1"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
      />
    </Svg>
  );
}

function SparklesIcon({ size = 18, color = T.primary }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <Path d="M19 17l1 3l3 1l-3 1l-1 3l-1-3l-3-1l3-1l1-3z" fill={color} />
    </Svg>
  );
}

function ShieldCheckIcon({ size = 16, color = T.primary }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 3a12 12 0 0 0 8.5 3.5A12 12 0 0 1 12 21A12 12 0 0 1 3.5 6.5A12 12 0 0 0 12 3"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M9 12l2 2l4 -4"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function CheckIcon({ size = 14, color = T.primary }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M5 13l4 4L19 7"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

// ─── WAVEFORM COMPONENT (MATCHES DESKTOP GRADIENT) ───────────
function WaveformCanvas({ points }) {
  const pts = points && points.length >= 8 ? points : SAMPLE_PPG;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = max - min || 1;
  const pad = 12;
  const w = GRAPH_W - pad * 2;
  const h = GRAPH_H - pad * 2;

  const path = pts
    .map((v, i) => {
      const x = pad + (i / (pts.length - 1)) * w;
      const y = pad + (1 - (v - min) / range) * h;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <View style={styles.waveBox}>
      <Svg width={GRAPH_W} height={GRAPH_H}>
        <Defs>
          <LinearGradient id="waveGrad" x1="0" y1="0" x2="1" y2="0">
            <Stop offset="0%" stopColor={T.waveStart} />
            <Stop offset="100%" stopColor={T.waveEnd} />
          </LinearGradient>
        </Defs>
        {/* Subtle hospital-grade reference grid lines */}
        {[0.25, 0.5, 0.75].map((fraction, idx) => (
          <Line
            key={idx}
            x1={pad}
            y1={pad + fraction * h}
            x2={GRAPH_W - pad}
            y2={pad + fraction * h}
            stroke="rgba(24, 143, 137, 0.12)"
            strokeWidth="1"
            strokeDasharray="4 4"
          />
        ))}
        {/* Continuous organic PPG waveform */}
        <Path
          d={path}
          fill="none"
          stroke="url(#waveGrad)"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </Svg>
    </View>
  );
}

// ─── MAIN COMPONENT ──────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState("live"); // 'live' | 'twin' | 'plan'
  const [connected, setConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isCalibrating, setIsCalibrating] = useState(false);

  // Core Clinical State (Defaults populated for instant demo/presentation mode)
  const [patientName, setPatientName] = useState("Praveen Choudhury");
  const [patientAge, setPatientAge] = useState(52);
  const [patientCity, setPatientCity] = useState("Nagpur, India");
  const [bpm, setBpm] = useState(68);
  const [gateStatus, setGateStatus] = useState("NORMAL_SINUS");
  const [instabilityScore, setInstabilityScore] = useState(14);
  const [baselineBpm, setBaselineBpm] = useState(64);
  const [hasBaseline, setHasBaseline] = useState(true);
  const [baseRisk, setBaseRisk] = useState(26.2);
  const [vascularAge, setVascularAge] = useState(76);
  const [ppgPoints, setPpgPoints] = useState(SAMPLE_PPG);

  // Simulation Controls State
  const [simMeds, setSimMeds] = useState({
    metoprolol: true,
    atorvastatin: true,
    ramipril: false,
  });
  const [simSBP, setSimSBP] = useState(130);
  const [simSmoker, setSimSmoker] = useState(false);
  const [simProjectedRisk, setSimProjectedRisk] = useState(26.2);

  // ─── POLLING SYNC WITH FLASK BACKEND ────────────────────────
  useEffect(() => {
    let isMounted = true;
    const fetchStatus = async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);
        const res = await fetch(`${BASE_URL}/twin/status`, {
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (!res.ok) throw new Error("Server not ready");
        const data = await res.json();

        if (isMounted) {
          setConnected(true);
          if (data.patient_ehr?.name) setPatientName(data.patient_ehr.name);
          if (data.patient_ehr?.age) setPatientAge(data.patient_ehr.age);
          if (data.patient_ehr?.city) setPatientCity(data.patient_ehr.city);
          if (data.current_vitals?.bpm) setBpm(Math.round(data.current_vitals.bpm));
          if (data.signal_gate?.status) setGateStatus(data.signal_gate.status);
          if (data.personal_instability?.instability_score !== undefined) {
            setInstabilityScore(data.personal_instability.instability_score);
          }
          if (data.personal_baseline?.median_bpm) {
            setBaselineBpm(Math.round(data.personal_baseline.median_bpm));
          }
          if (data.has_calibrated_baseline !== undefined) {
            setHasBaseline(data.has_calibrated_baseline);
          }
          if (data.base_clinical_risk !== undefined) {
            setBaseRisk(Number(data.base_clinical_risk).toFixed(1));
          }
          if (data.cardiovascular_age?.estimated_cv_age) {
            setVascularAge(data.cardiovascular_age.estimated_cv_age);
          }
          if (data.is_calibrating !== undefined) {
            setIsCalibrating(data.is_calibrating);
          }
        }
      } catch (e) {
        if (isMounted) {
          // Graceful fallback: maintain offline presentation state
          setConnected(false);
        }
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, POLL_MS);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // ─── ACTION HANDLERS ───────────────────────────────────────
  const toggleRecording = async () => {
    const next = !isRecording;
    setIsRecording(next);
    try {
      await fetch(`${BASE_URL}/${next ? "start" : "stop"}`, { method: "POST" });
    } catch (e) {}
  };

  const startCalibration = async () => {
    setIsCalibrating(true);
    try {
      await fetch(`${BASE_URL}/baseline/calibrate`, { method: "POST" });
    } catch (e) {}
  };

  const runScenario = async (scenarioKey) => {
    try {
      await fetch(`${BASE_URL}/twin/scenario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: scenarioKey }),
      });
      setActiveTab("live");
    } catch (e) {
      // Offline fallback: demonstrate the clinical shift locally
      if (scenarioKey === "stress_tachycardia") {
        setBpm(112);
        setInstabilityScore(64);
        setGateStatus("EXTREME_RATE");
      } else if (scenarioKey === "afib_episode") {
        setBpm(88);
        setInstabilityScore(78);
        setGateStatus("IRREGULAR_PULSE");
      } else {
        setBpm(64);
        setInstabilityScore(12);
        setGateStatus("NORMAL_SINUS");
      }
      setActiveTab("live");
    }
  };

  const calculateSimulation = () => {
    let r = parseFloat(baseRisk) || 81.8;
    if (simMeds.atorvastatin) r *= 0.72;
    if (simMeds.metoprolol) r *= 0.85;
    if (simMeds.ramipril) r *= 0.88;
    if (simSBP < 130) r *= 0.82;
    if (simSmoker) r *= 1.35;
    setSimProjectedRisk(Math.min(100, Math.max(5, r)).toFixed(1));
  };

  // Instability Tone Classifier
  const getInstabilityTone = () => {
    if (!hasBaseline || instabilityScore === null) {
      return {
        label: "Awaiting Baseline",
        desc: "2-minute quiet calibration required",
        bg: T.blueBg,
        text: T.blueText,
      };
    }
    if (instabilityScore <= 20) {
      return {
        label: "Within Usual Range",
        desc: "Pulse dynamics match calibrated baseline",
        bg: T.greenBg,
        text: T.greenText,
      };
    }
    if (instabilityScore <= 50) {
      return {
        label: "Mild Baseline Shift",
        desc: "Slight autonomic or pulse elevation noticed",
        bg: T.amberBg,
        text: T.amberText,
      };
    }
    return {
      label: "Sustained Departure",
      desc: "Prompt clinical context & symptom review",
      bg: T.roseBg,
      text: T.roseText,
    };
  };

  const tone = getInstabilityTone();

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" backgroundColor={T.bg} />

      {/* ─── APP HEADER ────────────────────────────────────── */}
      <View style={styles.header}>
        <View style={styles.brandRow}>
          <View style={styles.brandMark}>
            <HeartIcon size={17} color="#FFFFFF" />
          </View>
          <Text style={styles.brandTitle}>cardiotwin</Text>
        </View>

        <View style={styles.headerTools}>
          <View
            style={[
              styles.statusPill,
              { backgroundColor: connected ? T.greenBg : T.amberBg },
            ]}
          >
            <View
              style={[
                styles.statusDot,
                { backgroundColor: connected ? "#10B981" : "#F59E0B" },
              ]}
            />
            <Text
              style={[
                styles.statusPillText,
                { color: connected ? T.greenText : T.amberText },
              ]}
            >
              {connected ? "LIVE GATEWAY" : "PRESENTATION DEMO"}
            </Text>
          </View>
        </View>
      </View>

      {/* ─── PATIENT CONTEXT CHIP ──────────────────────────── */}
      <View style={styles.patientBanner}>
        <View style={styles.avatarCircle}>
          <Text style={styles.avatarText}>{patientName.slice(0, 1)}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.patientName}>{patientName}</Text>
          <Text style={styles.patientMeta}>
            {patientAge}y · {patientCity} · Est. Vascular Age ~{vascularAge}y
          </Text>
        </View>
        {hasBaseline ? (
          <View style={styles.baselinePill}>
            <Text style={styles.baselinePillText}>
              ✓ Baseline: {baselineBpm} BPM
            </Text>
          </View>
        ) : (
          <TouchableOpacity
            style={styles.calibratePill}
            onPress={startCalibration}
          >
            <Text style={styles.calibratePillText}>+ Calibrate</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* ─── MAIN CONTENT AREA ─────────────────────────────── */}
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {/* ════ TAB 1: LIVE CHECK ════ */}
        {activeTab === "live" && (
          <View style={styles.tabContent}>
            {/* Waveform Card */}
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View>
                  <Text style={styles.eyebrow}>STREAM 2 TELEMETRY</Text>
                  <Text style={styles.cardTitle}>Live Optical Pulse</Text>
                </View>
                <View style={styles.dualEngineBadge}>
                  <Text style={styles.dualEngineText}>⚡ DUAL ENGINE</Text>
                </View>
              </View>

              <WaveformCanvas points={ppgPoints} />

              <View style={styles.vitalsRow}>
                <View style={styles.vitalCol}>
                  <Text style={styles.vitalLabel}>PULSE RATE</Text>
                  <Text style={styles.vitalValue}>
                    {bpm > 0 ? bpm : "—"}{" "}
                    <Text style={styles.vitalUnit}>BPM</Text>
                  </Text>
                  <Text style={styles.vitalSub}>Optical IBI tracking</Text>
                </View>

                <View style={[styles.vitalCol, styles.vitalBorderCol]}>
                  <Text style={styles.vitalLabel}>SIGNAL GATE</Text>
                  <Text style={styles.vitalWord}>
                    {gateStatus.replace(/_/g, " ").toLowerCase()}
                  </Text>
                  <Text style={styles.vitalSub}>5-Part Decoupled Gate</Text>
                </View>

                <View style={styles.vitalCol}>
                  <Text style={styles.vitalLabel}>SpO₂ OXYGEN</Text>
                  <Text style={styles.vitalWordMuted}>Not measured</Text>
                  <Text style={styles.vitalSub}>Single IR transparency</Text>
                </View>
              </View>
            </View>

            {/* Personal Instability Assessment Card */}
            <View
              style={[
                styles.instabilityCard,
                { backgroundColor: tone.bg, borderColor: tone.text + "33" },
              ]}
            >
              <View style={styles.instabilityLeft}>
                <Text style={[styles.eyebrow, { color: tone.text }]}>
                  PERSONAL REFERENCE DEPARTURE
                </Text>
                <Text style={[styles.instabilityTitle, { color: tone.text }]}>
                  {tone.label}
                </Text>
                <Text style={styles.instabilityDesc}>{tone.desc}</Text>

                <View style={styles.shapPill}>
                  <Text style={styles.shapText}>
                    SHAP Drivers:{" "}
                    <Text style={{ fontWeight: "700" }}>BPM (0.42)</Text> ·{" "}
                    <Text style={{ fontWeight: "700" }}>RR_MEAN (0.28)</Text>
                  </Text>
                </View>
              </View>

              <View style={styles.scoreCircle}>
                <Text style={[styles.scoreValue, { color: tone.text }]}>
                  {instabilityScore ?? "—"}
                </Text>
                <Text style={styles.scoreSub}>out of 100</Text>
              </View>
            </View>

            {/* Quick Record Action Button */}
            <TouchableOpacity
              style={[
                styles.actionButton,
                { backgroundColor: isRecording ? "#B6464B" : T.primary },
              ]}
              onPress={toggleRecording}
              activeOpacity={0.85}
            >
              <Text style={styles.actionButtonText}>
                {isRecording ? "■ STOP RECORDING" : "● RECORD LIVE TELEMETRY"}
              </Text>
            </TouchableOpacity>

            {/* Clinical Guardrail Footer */}
            <View style={styles.disclaimerBox}>
              <ShieldCheckIcon size={15} color={T.textSecondary} />
              <Text style={styles.disclaimerText}>
                Non-diagnostic decision-support. Optical pulse screening requires
                confirmatory 12-lead ECG.
              </Text>
            </View>
          </View>
        )}

        {/* ════ TAB 2: YOUR TWIN ════ */}
        {activeTab === "twin" && (
          <View style={styles.tabContent}>
            {/* Longitudinal 10-Yr CVD Risk Card */}
            <View style={styles.riskLetterCard}>
              <Text style={styles.riskEyebrow}>STREAM 1: CARDIOMETABOLIC STATE</Text>
              <Text style={styles.riskHuge}>{baseRisk}%</Text>
              <Text style={styles.riskSub}>
                Estimated 10-Year Cardiovascular Event Risk
              </Text>
              <Text style={styles.riskExplain}>
                Framingham Cox proportional hazards baseline incorporating a
                1.45× South Asian recalibration factor for Indian primary care.
              </Text>
              <View style={styles.riskFooterRow}>
                <ShieldCheckIcon size={14} color="#C5DFCF" />
                <Text style={styles.riskFooterText}>
                  Independent of acute optical fluctuations
                </Text>
              </View>
            </View>

            {/* Vitals Strip */}
            <View style={styles.vitalsStrip}>
              <View style={styles.vitalsStripItem}>
                <Text style={styles.stripLabel}>Resting BP</Text>
                <Text style={styles.stripVal}>145/92 mmHg</Text>
              </View>
              <View style={[styles.vitalsStripItem, styles.vitalBorderCol]}>
                <Text style={styles.stripLabel}>Resting Pulse</Text>
                <Text style={styles.stripVal}>78 BPM</Text>
              </View>
              <View style={styles.vitalsStripItem}>
                <Text style={styles.stripLabel}>Daily Context</Text>
                <Text style={styles.stripVal}>Moderate</Text>
              </View>
            </View>

            {/* Modifiable Risk Levers */}
            <View style={styles.card}>
              <Text style={styles.eyebrow}>PREVENTION TRAJECTORY</Text>
              <Text style={styles.cardTitle}>Modifiable Risk Factors</Text>

              {[
                {
                  f: "Blood Pressure Optimization",
                  d: "Projected -28% risk shift under SBP < 130",
                },
                {
                  f: "Lipid-Lowering Statin Therapy",
                  d: "Projected -22% risk shift with LDL-C reduction",
                },
                {
                  f: "Physical Activity & Diet",
                  d: "Improves autonomic vagal tone & RMSSD",
                },
              ].map((item, idx) => (
                <View key={idx} style={styles.leverRow}>
                  <View style={styles.checkCircle}>
                    <CheckIcon size={12} color={T.primary} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.leverTitle}>{item.f}</Text>
                    <Text style={styles.leverDesc}>{item.d}</Text>
                  </View>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* ════ TAB 3: EXPLORE CHANGES (WHAT-IF) ════ */}
        {activeTab === "plan" && (
          <View style={styles.tabContent}>
            <View style={styles.card}>
              <Text style={styles.eyebrow}>INTERACTIVE WHAT-IF SIMULATOR</Text>
              <Text style={styles.cardTitle}>Preventive Scenario Modeling</Text>
              <Text style={styles.planSub}>
                Explore the projected 5–10 year impact of pharmacological and
                lifestyle interventions under sustained adherence.
              </Text>

              {/* Medication Chips */}
              <Text style={styles.fieldLabel}>PHARMACOLOGICAL AGENTS</Text>
              <View style={styles.chipsRow}>
                {[
                  { k: "atorvastatin", label: "Atorvastatin 20mg" },
                  { k: "metoprolol", label: "Metoprolol 50mg" },
                  { k: "ramipril", label: "Ramipril 5mg" },
                ].map((item) => (
                  <TouchableOpacity
                    key={item.k}
                    style={[
                      styles.choiceChip,
                      simMeds[item.k] && styles.choiceChipSelected,
                    ]}
                    onPress={() => {
                      setSimMeds((p) => ({ ...p, [item.k]: !p[item.k] }));
                      calculateSimulation();
                    }}
                  >
                    {simMeds[item.k] && <CheckIcon size={12} color={T.primary} />}
                    <Text
                      style={[
                        styles.choiceText,
                        simMeds[item.k] && styles.choiceTextSelected,
                      ]}
                    >
                      {item.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* BP Stepper */}
              <Text style={styles.fieldLabel}>
                SYSTOLIC BLOOD PRESSURE: {simSBP} mmHg
              </Text>
              <View style={styles.stepperRow}>
                {[115, 125, 135, 150].map((val) => (
                  <TouchableOpacity
                    key={val}
                    style={[
                      styles.stepperBtn,
                      simSBP === val && styles.stepperBtnActive,
                    ]}
                    onPress={() => {
                      setSimSBP(val);
                      calculateSimulation();
                    }}
                  >
                    <Text
                      style={[
                        styles.stepperBtnText,
                        simSBP === val && styles.stepperBtnTextActive,
                      ]}
                    >
                      {val}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Smoking Switch */}
              <TouchableOpacity
                style={styles.toggleRow}
                onPress={() => {
                  setSimSmoker(!simSmoker);
                  calculateSimulation();
                }}
              >
                <View
                  style={[
                    styles.checkbox,
                    simSmoker && { backgroundColor: T.primary },
                  ]}
                >
                  {simSmoker && <CheckIcon size={12} color="#FFFFFF" />}
                </View>
                <Text style={styles.toggleText}>
                  {simSmoker
                    ? "Active Tobacco Smoking Recorded"
                    : "No Current Smoking (Cessation Mode)"}
                </Text>
              </TouchableOpacity>
            </View>

            {/* Projected Outcome Card */}
            <View style={styles.outcomeCard}>
              <Text style={styles.eyebrow}>PROJECTED 10-YEAR OUTCOME</Text>
              <Text style={styles.outcomeHuge}>{simProjectedRisk}%</Text>
              <Text style={styles.outcomeSub}>
                Estimated Cardiovascular Event Risk
              </Text>

              <View style={styles.compareRow}>
                <View style={{ alignItems: "center" }}>
                  <Text style={styles.compareSub}>Baseline</Text>
                  <Text style={styles.compareVal}>{baseRisk}%</Text>
                </View>
                <Text style={styles.compareArrow}>──►</Text>
                <View style={{ alignItems: "center" }}>
                  <Text style={styles.compareSub}>With Adherence</Text>
                  <Text style={[styles.compareVal, { color: T.primary }]}>
                    {simProjectedRisk}%
                  </Text>
                </View>
              </View>
            </View>

            {/* Quick Demo Scenarios Row */}
            <View style={styles.card}>
              <Text style={styles.eyebrow}>DEMONSTRATION PRESETS</Text>
              <Text style={styles.cardTitle}>Test Acute Pulse Scenarios</Text>
              <View style={{ gap: 8, marginTop: 10 }}>
                {[
                  {
                    k: "calm_normal",
                    label: "Quiet Baseline (64 BPM Sinus)",
                  },
                  {
                    k: "stress_tachycardia",
                    label: "Elevated Pulse (112 BPM Stress)",
                  },
                  {
                    k: "afib_episode",
                    label: "Irregular Rhythm (Atrial Fibrillation)",
                  },
                ].map((s) => (
                  <TouchableOpacity
                    key={s.k}
                    style={styles.scenarioBtn}
                    onPress={() => runScenario(s.k)}
                  >
                    <Text style={styles.scenarioBtnText}>{s.label}</Text>
                    <Text style={styles.scenarioArrow}>→</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          </View>
        )}
      </ScrollView>

      {/* ─── NATIVE-FEELING BOTTOM TAB BAR ─────────────────── */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabItem, activeTab === "live" && styles.tabItemActive]}
          onPress={() => setActiveTab("live")}
        >
          <PulseIcon
            size={20}
            color={activeTab === "live" ? T.primary : T.textMuted}
          />
          <Text
            style={[
              styles.tabLabel,
              activeTab === "live" && styles.tabLabelActive,
            ]}
          >
            Live Check
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === "twin" && styles.tabItemActive]}
          onPress={() => setActiveTab("twin")}
        >
          <UserIcon
            size={20}
            color={activeTab === "twin" ? T.primary : T.textMuted}
          />
          <Text
            style={[
              styles.tabLabel,
              activeTab === "twin" && styles.tabLabelActive,
            ]}
          >
            Your Twin
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabItem, activeTab === "plan" && styles.tabItemActive]}
          onPress={() => setActiveTab("plan")}
        >
          <SparklesIcon
            size={20}
            color={activeTab === "plan" ? T.primary : T.textMuted}
          />
          <Text
            style={[
              styles.tabLabel,
              activeTab === "plan" && styles.tabLabelActive,
            ]}
          >
            What-If
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

// ─── STYLES (MATCHING DESKTOP CARDIOTWIN MEDICAL-TECH THEME) ──
const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: T.bg,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: T.cardBorder,
    backgroundColor: "rgba(248, 247, 242, 0.95)",
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  brandMark: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: T.teal,
    justifyContent: "center",
    alignItems: "center",
  },
  brandTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: T.tealDark,
    letterSpacing: -0.5,
  },
  headerTools: {
    flexDirection: "row",
    alignItems: "center",
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 5,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusPillText: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  patientBanner: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 10,
    backgroundColor: "#FFFFFF",
    borderBottomWidth: 1,
    borderBottomColor: T.cardBorder,
    gap: 10,
  },
  avatarCircle: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: T.chipBg,
    justifyContent: "center",
    alignItems: "center",
  },
  avatarText: {
    fontSize: 15,
    fontWeight: "600",
    color: T.teal,
  },
  patientName: {
    fontSize: 14,
    fontWeight: "700",
    color: T.textPrimary,
  },
  patientMeta: {
    fontSize: 11,
    color: T.textSecondary,
    marginTop: 1,
  },
  baselinePill: {
    backgroundColor: T.greenBg,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  baselinePillText: {
    fontSize: 11,
    fontWeight: "600",
    color: T.greenText,
  },
  calibratePill: {
    backgroundColor: T.amberBg,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  calibratePillText: {
    fontSize: 11,
    fontWeight: "600",
    color: T.amberText,
  },
  scroll: {
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 28,
  },
  tabContent: {
    gap: 14,
  },
  card: {
    backgroundColor: T.card,
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: T.cardBorder,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 8,
    elevation: 1,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 12,
  },
  eyebrow: {
    fontSize: 10,
    fontWeight: "700",
    color: T.teal,
    letterSpacing: 1,
    marginBottom: 2,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: T.textPrimary,
  },
  dualEngineBadge: {
    backgroundColor: T.chipBg,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "rgba(25, 59, 58, 0.08)",
  },
  dualEngineText: {
    fontSize: 10,
    fontWeight: "700",
    color: T.teal,
  },
  waveBox: {
    backgroundColor: "#F4F8F5",
    borderRadius: 12,
    paddingVertical: 4,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  vitalsRow: {
    flexDirection: "row",
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "rgba(25, 59, 58, 0.07)",
  },
  vitalCol: {
    flex: 1,
    alignItems: "center",
  },
  vitalBorderCol: {
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: "rgba(25, 59, 58, 0.08)",
  },
  vitalLabel: {
    fontSize: 9,
    fontWeight: "700",
    color: T.textMuted,
    letterSpacing: 0.8,
  },
  vitalValue: {
    fontSize: 20,
    fontWeight: "700",
    color: T.tealDark,
    marginTop: 2,
  },
  vitalUnit: {
    fontSize: 10,
    fontWeight: "500",
    color: T.textSecondary,
  },
  vitalWord: {
    fontSize: 13,
    fontWeight: "700",
    color: T.tealDark,
    marginTop: 4,
    textTransform: "capitalize",
  },
  vitalWordMuted: {
    fontSize: 12,
    fontWeight: "600",
    color: T.textMuted,
    marginTop: 4,
  },
  vitalSub: {
    fontSize: 9,
    color: T.textMuted,
    marginTop: 2,
    textAlign: "center",
  },
  instabilityCard: {
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  instabilityLeft: {
    flex: 1,
  },
  instabilityTitle: {
    fontSize: 17,
    fontWeight: "700",
    marginTop: 2,
  },
  instabilityDesc: {
    fontSize: 12,
    color: T.textSecondary,
    marginTop: 2,
    lineHeight: 16,
  },
  shapPill: {
    backgroundColor: "rgba(255, 255, 255, 0.7)",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginTop: 8,
    alignSelf: "flex-start",
  },
  shapText: {
    fontSize: 10,
    color: T.textSecondary,
  },
  scoreCircle: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
    width: 64,
    height: 64,
    borderRadius: 32,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  scoreValue: {
    fontSize: 24,
    fontWeight: "800",
  },
  scoreSub: {
    fontSize: 8,
    color: T.textMuted,
    marginTop: -2,
  },
  actionButton: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: T.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 8,
    elevation: 3,
  },
  actionButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 1,
  },
  disclaimerBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 6,
    paddingVertical: 8,
  },
  disclaimerText: {
    fontSize: 11,
    color: T.textMuted,
    flex: 1,
    lineHeight: 15,
  },

  // ─── TAB 2: YOUR TWIN STYLES ───────────────────────────────
  riskLetterCard: {
    backgroundColor: T.tealDeep,
    borderRadius: 18,
    padding: 22,
  },
  riskEyebrow: {
    fontSize: 10,
    fontWeight: "700",
    color: "#A8D3BD",
    letterSpacing: 1,
  },
  riskHuge: {
    fontSize: 52,
    fontWeight: "800",
    color: "#FFFFFF",
    marginVertical: 4,
  },
  riskSub: {
    fontSize: 14,
    fontWeight: "600",
    color: "#FFFFFF",
  },
  riskExplain: {
    fontSize: 12,
    color: "#D6E4D9",
    marginTop: 8,
    lineHeight: 17,
  },
  riskFooterRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 14,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "rgba(255, 255, 255, 0.15)",
  },
  riskFooterText: {
    fontSize: 11,
    color: "#C5DFCF",
  },
  vitalsStrip: {
    flexDirection: "row",
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: T.cardBorder,
    paddingVertical: 12,
  },
  vitalsStripItem: {
    flex: 1,
    alignItems: "center",
  },
  stripLabel: {
    fontSize: 10,
    color: T.textMuted,
  },
  stripVal: {
    fontSize: 13,
    fontWeight: "700",
    color: T.textPrimary,
    marginTop: 2,
  },
  leverRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(25, 59, 58, 0.06)",
  },
  checkCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: T.chipBg,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  leverTitle: {
    fontSize: 13,
    fontWeight: "600",
    color: T.textPrimary,
  },
  leverDesc: {
    fontSize: 11,
    color: T.textSecondary,
    marginTop: 1,
  },

  // ─── TAB 3: WHAT-IF STYLES ─────────────────────────────────
  planSub: {
    fontSize: 12,
    color: T.textSecondary,
    marginTop: 4,
    marginBottom: 12,
    lineHeight: 17,
  },
  fieldLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: T.textMuted,
    letterSpacing: 0.8,
    marginTop: 10,
    marginBottom: 6,
  },
  chipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  choiceChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: "#F3F5ED",
    borderWidth: 1,
    borderColor: "#E4E6DC",
  },
  choiceChipSelected: {
    backgroundColor: "#E1F0E7",
    borderColor: "#9FCEC0",
  },
  choiceText: {
    fontSize: 11,
    color: T.textSecondary,
  },
  choiceTextSelected: {
    color: T.primary,
    fontWeight: "600",
  },
  stepperRow: {
    flexDirection: "row",
    gap: 8,
  },
  stepperBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: "#F3F5ED",
    borderWidth: 1,
    borderColor: "#E4E6DC",
    alignItems: "center",
  },
  stepperBtnActive: {
    backgroundColor: T.teal,
    borderColor: T.teal,
  },
  stepperBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: T.textSecondary,
  },
  stepperBtnTextActive: {
    color: "#FFFFFF",
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 12,
    paddingVertical: 4,
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 4,
    borderWidth: 1.5,
    borderColor: T.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  toggleText: {
    fontSize: 12,
    color: T.textPrimary,
  },
  outcomeCard: {
    backgroundColor: "#E4F0EB",
    borderRadius: 16,
    padding: 20,
    alignItems: "center",
  },
  outcomeHuge: {
    fontSize: 48,
    fontWeight: "800",
    color: T.primary,
    marginVertical: 2,
  },
  outcomeSub: {
    fontSize: 12,
    color: T.textSecondary,
    textAlign: "center",
  },
  compareRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    marginTop: 14,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "rgba(25, 59, 58, 0.1)",
  },
  compareSub: {
    fontSize: 10,
    color: T.textMuted,
  },
  compareVal: {
    fontSize: 16,
    fontWeight: "700",
    color: T.textPrimary,
  },
  compareArrow: {
    fontSize: 14,
    color: T.teal,
  },
  scenarioBtn: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: "#F3F5ED",
    borderWidth: 1,
    borderColor: "#E4E6DC",
  },
  scenarioBtnText: {
    fontSize: 12,
    color: T.tealDark,
    fontWeight: "500",
  },
  scenarioArrow: {
    fontSize: 13,
    color: T.teal,
    fontWeight: "700",
  },

  // ─── BOTTOM TAB BAR ────────────────────────────────────────
  tabBar: {
    flexDirection: "row",
    backgroundColor: "#FFFFFF",
    borderTopWidth: 1,
    borderTopColor: T.cardBorder,
    paddingVertical: 8,
    paddingBottom: Platform.OS === "ios" ? 18 : 8,
  },
  tabItem: {
    flex: 1,
    alignItems: "center",
    gap: 2,
  },
  tabItemActive: {
    opacity: 1,
  },
  tabLabel: {
    fontSize: 10,
    fontWeight: "500",
    color: T.textMuted,
  },
  tabLabelActive: {
    color: T.primary,
    fontWeight: "700",
  },
});
