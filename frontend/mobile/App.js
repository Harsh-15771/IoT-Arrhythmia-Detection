import { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  StatusBar,
  Dimensions,
  Animated,
  Easing,
  ScrollView,
} from "react-native";
import Svg, { Polyline, Line } from "react-native-svg";

// ─── CONFIG ──────────────────────────────────────────────
const SERVER_IP = "10.139.96.96"; // ← Your laptop's IPv4
const SERVER_PORT = 5000;
const BASE_URL = `http://${SERVER_IP}:${SERVER_PORT}`;
const POLL_MS = 800;
// ─────────────────────────────────────────────────────────

// AbortSignal.timeout is not available in Expo Go's JS engine,
// so we use a manual AbortController + setTimeout instead.
function fetchWithTimeout(url, options = {}, timeoutMs = 4000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() =>
    clearTimeout(timer),
  );
}

const { width: SW } = Dimensions.get("window");
const GRAPH_W = SW - 40;
const GRAPH_H = 180;

const C = {
  bg: "#080C14",
  card: "#0F1724",
  cardBorder: "#1A2540",
  green: "#00E5A0",
  red: "#FF4C6A",
  yellow: "#FFD166",
  blue: "#4CC9F0",
  purple: "#9B72CF",
  textPrimary: "#EDF2FF",
  textMuted: "#5A6A8A",
  graphLine: "#00E5A0",
  gridLine: "#1A2540",
};

function PPGGraph({ data, isRecording }) {
  if (!data || data.length < 2) {
    return (
      <View
        style={[
          styles.graphBox,
          { justifyContent: "center", alignItems: "center" },
        ]}
      >
        <Text
          style={{ color: C.textMuted, fontFamily: "monospace", fontSize: 12 }}
        >
          {isRecording ? "Waiting for signal..." : "No data yet"}
        </Text>
      </View>
    );
  }
  const display = data.slice(-80);
  const min = Math.min(...display);
  const max = Math.max(...display);
  const range = max - min || 1;
  const pad = 10;
  const W = GRAPH_W - pad * 2;
  const H = GRAPH_H - pad * 2;
  const points = display
    .map((v, i) => {
      const x = pad + (i / (display.length - 1)) * W;
      const y = pad + (1 - (v - min) / range) * H;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <View style={styles.graphBox}>
      <Svg width={GRAPH_W} height={GRAPH_H}>
        {[0.25, 0.5, 0.75].map((t, i) => (
          <Line
            key={i}
            x1={pad}
            y1={pad + t * H}
            x2={GRAPH_W - pad}
            y2={pad + t * H}
            stroke={C.gridLine}
            strokeWidth="1"
            strokeDasharray="3,5"
          />
        ))}
        <Polyline
          points={points}
          fill="none"
          stroke={C.graphLine}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </Svg>
    </View>
  );
}

function StatCard({ label, value, unit, color }) {
  return (
    <View style={[styles.statCard, { borderColor: color + "33" }]}>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      {unit ? (
        <Text style={[styles.statUnit, { color: color + "99" }]}>{unit}</Text>
      ) : null}
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

export default function App() {
  const [appState, setAppState] = useState("idle");
  const [ppgData, setPpgData] = useState([]);
  const [prediction, setPrediction] = useState("---");
  const [confidence, setConfidence] = useState(0);
  const [bpm, setBpm] = useState(0);
  const [alertFlag, setAlertFlag] = useState(false);
  const [sampleCount, setSampleCount] = useState(0);
  const [statusMsg, setStatusMsg] = useState("Ready");
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState("");
  const [csvPath, setCsvPath] = useState("");
  const [isFetchingResult, setIsFetchingResult] = useState(false);

  // Use a ref so the poll callback always sees latest appState
  const appStateRef = useRef(appState);
  useEffect(() => {
    appStateRef.current = appState;
  }, [appState]);

  const alertAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (alertFlag) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(alertAnim, {
            toValue: 1.03,
            duration: 700,
            easing: Easing.ease,
            useNativeDriver: true,
          }),
          Animated.timing(alertAnim, {
            toValue: 1,
            duration: 700,
            easing: Easing.ease,
            useNativeDriver: true,
          }),
        ]),
      ).start();
    } else {
      alertAnim.stopAnimation();
      alertAnim.setValue(1);
    }
  }, [alertFlag]);

  // ── Core result-apply function (shared by poll and manual fetch) ──
  const applyResult = (data) => {
    // Accept any truthy prediction string (including "Normal")
    const pred = data.prediction ?? "";
    if (pred && pred !== "---") {
      setPrediction(pred);
      setConfidence(data.confidence ?? 0);
      setBpm(data.bpm ?? 0);
      setAlertFlag(data.alert ?? false);
      if (data.csv_path) setCsvPath(data.csv_path);
      setAppState("result");
      setError("");
      return true;
    }
    return false;
  };

  // ── Poll /stream — also auto-detects when analysis is done ──
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetchWithTimeout(`${BASE_URL}/stream`, {}, 2000);
        const data = await res.json();
        setConnected(true);
        setError("");

        if (data.ppg && data.ppg.length > 0) setPpgData(data.ppg);
        if (data.bpm !== undefined) setBpm(data.bpm);
        if (data.alert !== undefined) setAlertFlag(data.alert);
        if (data.sample_count !== undefined) setSampleCount(data.sample_count);
        if (data.status_msg) setStatusMsg(data.status_msg);

        // ── AUTO-TRANSITION: if we're analysing and server says done, fetch result ──
        if (appStateRef.current === "analysing" && data.is_running === false) {
          // Fetch /status to get the ML result
          try {
            const sRes = await fetchWithTimeout(`${BASE_URL}/status`, {}, 3000);
            const sData = await sRes.json();
            applyResult(sData);
          } catch (e) {
            // Will retry next poll cycle
            console.warn("Auto-fetch result failed:", e.message);
          }
        }
      } catch (e) {
        setConnected(false);
        setError("Cannot reach server — check IP & WiFi");
        console.warn("Poll error:", e.message);
      }
    };
    const id = setInterval(poll, POLL_MS);
    poll(); // immediate first call
    return () => clearInterval(id);
  }, []);

  // ── Manual GET RESULT button ──
  const fetchResult = async () => {
    setIsFetchingResult(true);
    setError("");
    try {
      const res = await fetchWithTimeout(`${BASE_URL}/status`, {}, 5000);

      if (!res.ok) {
        setError(`Server error: HTTP ${res.status}`);
        return;
      }

      const data = await res.json();
      console.log("GET RESULT response:", JSON.stringify(data)); // debug log

      const applied = applyResult(data);
      if (!applied) {
        // prediction is missing or "---" — tell the user
        setStatusMsg(
          data.status_msg
            ? `Not ready: ${data.status_msg}`
            : "Analysis not ready yet — try again in a moment",
        );
      }
    } catch (e) {
      console.error("fetchResult error:", e.message);
      setError(`Fetch failed: ${e.message}`);
    } finally {
      setIsFetchingResult(false);
    }
  };

  const handleStart = async () => {
    setError("");
    try {
      const res = await fetch(`${BASE_URL}/start`, { method: "POST" });
      const data = await res.json();
      setAppState("recording");
      setPpgData([]);
      setPrediction("---");
      setConfidence(0);
      setBpm(0);
      setAlertFlag(false);
      setSampleCount(0);
      setStatusMsg("Recording...");
      if (data.csv) setCsvPath(data.csv);
    } catch (e) {
      console.error("Start error:", e.message);
      setError(`Cannot start: ${e.message}`);
    }
  };

  const handleStop = async () => {
    setError("");
    try {
      await fetch(`${BASE_URL}/stop`, { method: "POST" });
      setAppState("analysing");
      setStatusMsg("Analysing… tap GET RESULT when ready");
    } catch (e) {
      console.error("Stop error:", e.message);
      setError(`Cannot stop: ${e.message}`);
    }
  };

  const handleReset = () => {
    setAppState("idle");
    setPpgData([]);
    setPrediction("---");
    setConfidence(0);
    setBpm(0);
    setAlertFlag(false);
    setSampleCount(0);
    setStatusMsg("Ready");
    setCsvPath("");
    setError("");
  };

  const predColor =
    prediction === "Normal"
      ? C.green
      : prediction === "---"
        ? C.textMuted
        : C.red;

  const secs = (sampleCount / 100).toFixed(1);

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor={C.bg} />
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>PPG Monitor</Text>
            <Text style={styles.headerSub}>Heart Disease Detection</Text>
          </View>
          <View style={{ alignItems: "center", gap: 4 }}>
            <View
              style={[
                styles.dot,
                { backgroundColor: connected ? C.green : C.red },
              ]}
            />
            <Text
              style={[styles.connLabel, { color: connected ? C.green : C.red }]}
            >
              {connected ? "LIVE" : "OFF"}
            </Text>
          </View>
        </View>

        {/* Error */}
        {!!error && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>⚠ {error}</Text>
          </View>
        )}

        {/* Graph */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionLabel}>LIVE PPG WAVEFORM</Text>
            {appState === "recording" && (
              <Text
                style={[
                  styles.badge,
                  { backgroundColor: C.red + "22", color: C.red },
                ]}
              >
                ● REC {secs}s
              </Text>
            )}
          </View>
          <PPGGraph data={ppgData} isRecording={appState === "recording"} />
        </View>

        {/* Stats */}
        <View style={styles.statsRow}>
          <StatCard
            label="HEART RATE"
            value={bpm > 0 ? Math.round(bpm) : "--"}
            unit="bpm"
            color={C.blue}
          />
          <StatCard
            label="SAMPLES"
            value={sampleCount > 0 ? sampleCount : "--"}
            unit={sampleCount > 0 ? `${secs}s` : ""}
            color={C.purple}
          />
          <StatCard
            label="CONFIDENCE"
            value={confidence > 0 ? `${(confidence * 100).toFixed(0)}%` : "--"}
            color={C.yellow}
          />
        </View>

        {/* Result Card */}
        {appState === "analysing" ? (
          <View style={[styles.resultCard, { borderColor: C.yellow + "44" }]}>
            <Text style={styles.resultLabel}>ANALYSING</Text>
            <Text style={[styles.resultValue, { color: C.yellow }]}>
              Please wait...
            </Text>
            <Text style={styles.resultSub}>
              Running ML model on recorded data
            </Text>
          </View>
        ) : appState === "result" ? (
          <Animated.View
            style={[
              styles.resultCard,
              {
                borderColor: predColor + "55",
                transform: [{ scale: alertAnim }],
              },
            ]}
          >
            {alertFlag && (
              <View style={styles.alertBadge}>
                <Text style={styles.alertBadgeText}>⚠ ALERT</Text>
              </View>
            )}
            <Text style={styles.resultLabel}>DIAGNOSIS</Text>
            <Text style={[styles.resultValue, { color: predColor }]}>
              {prediction}
            </Text>
            <Text style={[styles.confidenceText, { color: predColor + "99" }]}>
              {(confidence * 100).toFixed(1)}% confidence • BPM:{" "}
              {Math.round(bpm)}
            </Text>
            <Text style={styles.resultSub}>
              {prediction === "Normal"
                ? "✓ No abnormalities detected in your PPG signal"
                : `${prediction} pattern detected in your PPG signal.\nPlease consult a doctor.`}
            </Text>
            {!!csvPath && (
              <Text style={styles.csvNote}>
                💾 {csvPath.split(/[\\/]/).pop()}
              </Text>
            )}
          </Animated.View>
        ) : (
          <View style={[styles.resultCard, { borderColor: C.cardBorder }]}>
            <Text style={styles.resultLabel}>DIAGNOSIS</Text>
            <Text style={[styles.resultValue, { color: C.textMuted }]}>
              ---
            </Text>
            <Text style={styles.resultSub}>
              {appState === "idle"
                ? "Press START, place finger on sensor, then press STOP"
                : "Recording in progress..."}
            </Text>
          </View>
        )}

        {/* Buttons */}
        <View style={styles.btnArea}>
          {appState === "idle" && (
            <TouchableOpacity
              style={[styles.btn, { backgroundColor: C.green }]}
              onPress={handleStart}
              activeOpacity={0.8}
            >
              <Text style={styles.btnText}>▶ START RECORDING</Text>
            </TouchableOpacity>
          )}

          {appState === "recording" && (
            <TouchableOpacity
              style={[styles.btn, { backgroundColor: C.red }]}
              onPress={handleStop}
              activeOpacity={0.8}
            >
              <Text style={styles.btnText}>■ STOP & ANALYSE</Text>
            </TouchableOpacity>
          )}

          {appState === "analysing" && (
            <View style={{ gap: 10 }}>
              <View
                style={[
                  styles.btn,
                  {
                    backgroundColor: C.yellow + "22",
                    borderWidth: 1,
                    borderColor: C.yellow,
                  },
                ]}
              >
                <Text style={[styles.btnText, { color: C.yellow }]}>
                  ⏳ ANALYSING...
                </Text>
              </View>
              <TouchableOpacity
                style={[
                  styles.btn,
                  {
                    backgroundColor: isFetchingResult
                      ? C.green + "11"
                      : C.green + "22",
                    borderWidth: 1,
                    borderColor: C.green,
                    opacity: isFetchingResult ? 0.6 : 1,
                  },
                ]}
                onPress={fetchResult}
                activeOpacity={0.8}
                disabled={isFetchingResult}
              >
                <Text style={[styles.btnText, { color: C.green }]}>
                  {isFetchingResult ? "⏳ FETCHING..." : "↓ GET RESULT"}
                </Text>
              </TouchableOpacity>
            </View>
          )}

          {appState === "result" && (
            <TouchableOpacity
              style={[
                styles.btn,
                {
                  backgroundColor: C.blue + "22",
                  borderWidth: 1,
                  borderColor: C.blue,
                },
              ]}
              onPress={handleReset}
              activeOpacity={0.8}
            >
              <Text style={[styles.btnText, { color: C.blue }]}>
                ↺ NEW RECORDING
              </Text>
            </TouchableOpacity>
          )}
        </View>

        <Text style={styles.statusMsg}>{statusMsg}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  scroll: { paddingHorizontal: 20, paddingBottom: 30 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 18,
  },
  headerTitle: {
    color: C.textPrimary,
    fontSize: 22,
    fontWeight: "800",
    fontFamily: "monospace",
  },
  headerSub: {
    color: C.textMuted,
    fontSize: 11,
    fontFamily: "monospace",
    marginTop: 2,
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  connLabel: { fontSize: 9, fontFamily: "monospace", letterSpacing: 1 },
  errorBanner: {
    backgroundColor: "#200A10",
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.red + "44",
  },
  errorText: { color: C.red, fontSize: 11, fontFamily: "monospace" },
  section: { marginBottom: 14 },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  sectionLabel: {
    color: C.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    fontFamily: "monospace",
  },
  badge: {
    fontSize: 10,
    fontFamily: "monospace",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 20,
  },
  graphBox: {
    backgroundColor: C.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: C.cardBorder,
    height: GRAPH_H,
    overflow: "hidden",
  },
  statsRow: { flexDirection: "row", gap: 8, marginBottom: 14 },
  statCard: {
    flex: 1,
    backgroundColor: C.card,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    alignItems: "center",
  },
  statValue: { fontSize: 18, fontWeight: "800", fontFamily: "monospace" },
  statUnit: { fontSize: 10, fontFamily: "monospace" },
  statLabel: {
    color: C.textMuted,
    fontSize: 9,
    letterSpacing: 1,
    marginTop: 2,
    fontFamily: "monospace",
  },
  resultCard: {
    backgroundColor: C.card,
    borderRadius: 16,
    borderWidth: 1,
    padding: 20,
    marginBottom: 20,
    alignItems: "center",
  },
  alertBadge: {
    backgroundColor: C.red + "22",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 4,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: C.red,
  },
  alertBadgeText: {
    color: C.red,
    fontSize: 11,
    fontWeight: "800",
    fontFamily: "monospace",
    letterSpacing: 1,
  },
  resultLabel: {
    color: C.textMuted,
    fontSize: 10,
    letterSpacing: 2,
    marginBottom: 8,
    fontFamily: "monospace",
  },
  resultValue: { fontSize: 36, fontWeight: "900", fontFamily: "monospace" },
  confidenceText: { fontSize: 12, fontFamily: "monospace", marginTop: 4 },
  resultSub: {
    color: C.textMuted,
    fontSize: 12,
    marginTop: 10,
    textAlign: "center",
    lineHeight: 18,
  },
  csvNote: {
    color: C.textMuted,
    fontSize: 10,
    marginTop: 10,
    fontFamily: "monospace",
  },
  btnArea: { marginBottom: 14 },
  btn: { paddingVertical: 18, borderRadius: 50, alignItems: "center" },
  btnText: {
    color: C.bg,
    fontSize: 15,
    fontWeight: "900",
    letterSpacing: 2,
    fontFamily: "monospace",
  },
  statusMsg: {
    color: C.textMuted,
    fontSize: 11,
    textAlign: "center",
    fontFamily: "monospace",
    marginBottom: 10,
  },
  cardBorder: { color: C.cardBorder },
});
