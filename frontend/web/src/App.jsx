import React, { useState, useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import { 
  Heart, Activity, AlertTriangle, ShieldCheck, UserCheck, 
  Pill, Sliders, Play, RefreshCw, Zap, TrendingUp, Radio, 
  MapPin, Clock, Info, CheckCircle2, ChevronDown
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:5000';

export default function App() {
  // State
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('PAT001');
  const [twinStatus, setTwinStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  
  // Waveform buffer
  const [waveformPoints, setWaveformPoints] = useState([]);
  
  // What-If Simulator State
  const [simMeds, setSimMeds] = useState({
    metoprolol: false,
    atorvastatin: false,
    ramipril: false
  });
  const [simSBP, setSimSBP] = useState(135);
  const [simSmoker, setSimSmoker] = useState(false);
  const [simResult, setSimResult] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);

  // Scenario loading
  const [scenarioLoading, setScenarioLoading] = useState(false);

  // 1. Initial Load: Fetch Patients List
  useEffect(() => {
    fetch(`${API_BASE}/patients`)
      .then(res => res.json())
      .then(data => {
        setPatients(data.patients || []);
        if (data.active_patient_id) {
          setSelectedPatientId(data.active_patient_id);
        }
      })
      .catch(err => console.error("Failed to load patients:", err));
  }, []);

  // 2. Fetch Twin Status & Poll as Fallback
  const fetchStatus = () => {
    fetch(`${API_BASE}/twin/status`)
      .then(res => res.json())
      .then(data => {
        setTwinStatus(data);
        if (data.patient_ehr?.vitals?.systolic_bp) {
          setSimSBP(data.patient_ehr.vitals.systolic_bp);
        }
        if (data.patient_ehr?.lifestyle?.smoker !== undefined) {
          setSimSmoker(data.patient_ehr.lifestyle.smoker);
        }
      })
      .catch(err => console.error("Failed to fetch twin status:", err));
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2500);
    return () => clearInterval(interval);
  }, [selectedPatientId]);

  // 3. Setup WebSocket Connection
  useEffect(() => {
    const socket = io(API_BASE, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 10
    });

    socket.on('connect', () => {
      setConnected(true);
      console.log("[WebSocket] Connected to CardioTwin API");
    });

    socket.on('disconnect', () => {
      setConnected(false);
      console.log("[WebSocket] Disconnected");
    });

    socket.on('telemetry_update', (data) => {
      setTwinStatus(data);
    });

    socket.on('live_waveform', (data) => {
      if (data.chunk && data.chunk.length > 0) {
        setWaveformPoints(prev => {
          const updated = [...prev, ...data.chunk];
          return updated.slice(-180);
        });
      }
    });

    socket.on('patient_switched', (data) => {
      setTwinStatus(data);
      setSelectedPatientId(data.patient_id);
    });

    return () => socket.disconnect();
  }, []);

  // Handlers
  const handlePatientSelect = (pid) => {
    setSelectedPatientId(pid);
    fetch(`${API_BASE}/patient/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_id: pid })
    })
      .then(res => res.json())
      .then(data => {
        if (data.status) {
          setTwinStatus(data.status);
          setSimResult(null);
        }
      });
  };

  const handleScenario = (scenarioKey) => {
    setScenarioLoading(true);
    fetch(`${API_BASE}/twin/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario: scenarioKey })
    })
      .then(res => res.json())
      .then(data => {
        if (data.updated_status) {
          setTwinStatus(data.updated_status);
        }
        setScenarioLoading(false);
      })
      .catch(() => setScenarioLoading(false));
  };

  const runSimulation = () => {
    setIsSimulating(true);
    const addedMeds = [];
    if (simMeds.metoprolol) addedMeds.push('Metoprolol');
    if (simMeds.atorvastatin) addedMeds.push('Atorvastatin');
    if (simMeds.ramipril) addedMeds.push('Ramipril');

    fetch(`${API_BASE}/twin/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        add_medications: addedMeds,
        systolic_bp: simSBP,
        smoker: simSmoker
      })
    })
      .then(res => res.json())
      .then(data => {
        setSimResult(data.simulation);
        setIsSimulating(false);
      })
      .catch(() => setIsSimulating(false));
  };

  // Helper colors
  const getRiskColor = (risk) => {
    if (risk >= 70) return '#EF4444';
    if (risk >= 35) return '#F59E0B';
    return '#10B981';
  };

  const getStatusBadgeClass = (status) => {
    if (status?.includes('Critical')) return 'badge-critical';
    if (status?.includes('Caution') || status?.includes('Moderate')) return 'badge-caution';
    return 'badge-optimal';
  };

  // v3 8-Class Rhythm Helpers
  const formatArrhythmiaLabel = (label) => {
    if (!label) return 'Normal Sinus Rhythm';
    if (label === 'AFib') return 'Atrial Fibrillation (AFib)';
    if (label === 'Cardiac_Paced') return 'Cardiac Paced / AV Block';
    if (label === 'V_Tachycardia') return 'Ventricular Tachycardia (VT)';
    if (label === 'V_Flutter_Fib') return 'Ventricular Flutter / Fib';
    if (label === 'Asystole') return 'Asystole Alert';
    if (label === 'Bradycardia') return 'Bradycardia (<60 BPM)';
    if (label === 'Tachycardia') return 'Tachycardia (>100 BPM)';
    if (label === 'Normal') return 'Normal Sinus Rhythm';
    return label;
  };

  const getArrhythmiaColor = (label) => {
    if (!label || label === 'Normal') return '#34D399';
    if (label.includes('Buffering') || label.includes('Insufficient') || label.includes('Sensor Disconnected')) return '#FBBF24';
    if (label === 'AFib') return '#C084FC';
    if (label === 'Cardiac_Paced') return '#38BDF8';
    if (label === 'Bradycardia' || label === 'Tachycardia') return '#F59E0B';
    return '#F87171';
  };

  const p = twinStatus?.patient_ehr || {};
  const v = twinStatus?.current_vitals || {};
  const dynamicRisk = twinStatus?.current_dynamic_risk || 25;
  const baseRisk = twinStatus?.base_clinical_risk || 20;

  // SVG waveform renderer
  const renderWaveformSVG = () => {
    if (waveformPoints.length < 2) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-dim)', textAlign: 'center' }}>
          <Radio size={24} color="#06B6D4" style={{ marginBottom: '6px', opacity: 0.7 }} />
          <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#E2E8F0' }}>
            Awaiting Optical PPG Stream (100 Hz)
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            ESP32 /data endpoint ready • Trigger a demo scenario above to simulate
          </span>
        </div>
      );
    }
    const width = 600;
    const height = 140;
    const minVal = Math.min(...waveformPoints);
    const maxVal = Math.max(...waveformPoints);
    const range = (maxVal - minVal) || 1;

    const pointsStr = waveformPoints.map((val, idx) => {
      const x = (idx / (waveformPoints.length - 1)) * width;
      const y = height - ((val - minVal) / range) * (height - 30) - 15;
      return `${x},${y}`;
    }).join(' ');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '100%' }}>
        <defs>
          <linearGradient id="waveGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#06B6D4" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#06B6D4" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        {/* Subtle grid lines */}
        <line x1="0" y1={height * 0.25} x2={width} y2={height * 0.25} stroke="rgba(56, 75, 112, 0.25)" strokeDasharray="3,3" />
        <line x1="0" y1={height * 0.50} x2={width} y2={height * 0.50} stroke="rgba(56, 75, 112, 0.35)" strokeDasharray="3,3" />
        <line x1="0" y1={height * 0.75} x2={width} y2={height * 0.75} stroke="rgba(56, 75, 112, 0.25)" strokeDasharray="3,3" />
        
        {/* Glowing PPG Trace */}
        <polyline
          fill="none"
          stroke="#06B6D4"
          strokeWidth="2.5"
          points={pointsStr}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ filter: 'drop-shadow(0 0 6px #06B6D4)' }}
        />
      </svg>
    );
  };

  // Trajectory history SVG chart
  const renderTrajectorySVG = () => {
    const history = twinStatus?.risk_history || [];
    if (history.length < 2) return <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>Gathering trajectory samples...</p>;
    
    const width = 640;
    const height = 90;
    const pointsStr = history.map((item, idx) => {
      const x = (idx / (history.length - 1)) * width;
      const y = height - (item.dynamic_risk / 100) * height;
      return `${x},${y}`;
    }).join(' ');

    return (
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '100%' }}>
        <polyline
          fill="none"
          stroke="#F59E0B"
          strokeWidth="2"
          points={pointsStr}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {history.map((item, idx) => {
          const x = (idx / (history.length - 1)) * width;
          const y = height - (item.dynamic_risk / 100) * height;
          return (
            <circle
              key={idx}
              cx={x}
              cy={y}
              r="3"
              fill={getRiskColor(item.dynamic_risk)}
              style={{ filter: `drop-shadow(0 0 4px ${getRiskColor(item.dynamic_risk)})` }}
            />
          );
        })}
      </svg>
    );
  };

  return (
    <div style={{ padding: '20px 28px', maxWidth: '1600px', margin: '0 auto' }}>
      
      {/* ── TOP NAVIGATION & HEADER ── */}
      <header style={{ 
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
        marginBottom: '22px', flexWrap: 'wrap', gap: '16px' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ 
            background: 'linear-gradient(135deg, #EF4444 0%, #DC2626 100%)', 
            borderRadius: '12px', padding: '10px', display: 'flex', alignItems: 'center',
            boxShadow: '0 0 20px rgba(239, 68, 68, 0.45)' 
          }}>
            <Heart size={26} color="#FFFFFF" className="pulsing-heart" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#FFFFFF' }}>
                CardioTwin
              </h1>
              <span className="badge badge-info" style={{ fontSize: '0.68rem', padding: '2px 8px' }}>
                v3.0 • Investigational Prototype
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Real-Time Cardiovascular AI Replica & Clinical Simulation Engine
            </p>
          </div>
        </div>

        {/* Middle: Patient Selector Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ 
            display: 'flex', alignItems: 'center', gap: '8px', 
            background: 'var(--bg-secondary)', padding: '6px 14px', borderRadius: '10px',
            border: '1px solid var(--border-color)'
          }}>
            <UserCheck size={16} color="var(--accent-cyan)" />
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Active Twin:</span>
            <select
              value={selectedPatientId}
              onChange={(e) => handlePatientSelect(e.target.value)}
              style={{
                background: 'transparent',
                color: '#FFFFFF',
                border: 'none',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              {patients.map(pt => (
                <option key={pt.id} value={pt.id} style={{ background: '#111827', color: '#FFFFFF' }}>
                  {pt.name} ({pt.age}y, {pt.city}) — {pt.risk_category} Risk
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Right: Demo Scenarios & Connection Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Data Source Provenance Badge */}
          <div style={{ 
            display: 'flex', alignItems: 'center', gap: '6px', 
            background: twinStatus?.data_source === 'LIVE_HARDWARE' ? 'rgba(16, 185, 129, 0.15)' : (twinStatus?.data_source === 'SIMULATION' ? 'rgba(139, 92, 246, 0.15)' : 'rgba(100, 116, 139, 0.15)'), 
            padding: '6px 12px', borderRadius: '8px',
            border: `1px solid ${twinStatus?.data_source === 'LIVE_HARDWARE' ? 'rgba(16, 185, 129, 0.4)' : (twinStatus?.data_source === 'SIMULATION' ? 'rgba(139, 92, 246, 0.4)' : 'rgba(100, 116, 139, 0.4)')}`
          }}>
            <Radio size={14} color={twinStatus?.data_source === 'LIVE_HARDWARE' ? '#10B981' : (twinStatus?.data_source === 'SIMULATION' ? '#A78BFA' : '#94A3B8')} />
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: twinStatus?.data_source === 'LIVE_HARDWARE' ? '#34D399' : (twinStatus?.data_source === 'SIMULATION' ? '#C4B5FD' : '#CBD5E1') }}>
              {twinStatus?.data_source === 'LIVE_HARDWARE' ? '● SOURCE: LIVE ESP32 (100Hz)' : (twinStatus?.data_source === 'SIMULATION' ? '● SOURCE: SIMULATED SCENARIO' : '● SOURCE: STANDBY / INITIALIZED')}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              onClick={() => handleScenario('stress_tachycardia')}
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#F87171',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                padding: '6px 10px',
                borderRadius: '8px',
                fontSize: '0.72rem',
                fontWeight: 600
              }}
            >
              ⚡ Stress Tachycardia
            </button>
            <button
              onClick={() => handleScenario('afib_episode')}
              style={{
                background: 'rgba(168, 85, 247, 0.15)',
                color: '#C084FC',
                border: '1px solid rgba(168, 85, 247, 0.3)',
                padding: '6px 10px',
                borderRadius: '8px',
                fontSize: '0.72rem',
                fontWeight: 600
              }}
            >
              💓 Atrial Fibrillation
            </button>
            <button
              onClick={() => handleScenario('hypoxia_event')}
              style={{
                background: 'rgba(245, 158, 11, 0.15)',
                color: '#FBBF24',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                padding: '6px 10px',
                borderRadius: '8px',
                fontSize: '0.72rem',
                fontWeight: 600
              }}
            >
              ⚠️ Hypoxia Drop
            </button>
            <button
              onClick={() => handleScenario('calm_normal')}
              style={{
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#34D399',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                padding: '6px 10px',
                borderRadius: '8px',
                fontSize: '0.72rem',
                fontWeight: 600
              }}
            >
              ✅ Calm Normal
            </button>
          </div>
        </div>
      </header>

      {/* ── MAIN DASHBOARD GRID ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr 380px', gap: '20px', marginBottom: '20px' }}>
        
        {/* ── LEFT PANEL: PATIENT DIGITAL TWIN AVATAR & CLINICAL PROFILE ── */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Virtual Patient Replica
            </span>
            <span className={`badge ${getStatusBadgeClass(twinStatus?.status_label)}`}>
              {twinStatus?.status_label || 'Optimal'}
            </span>
          </div>

          {/* Patient Header */}
          <div style={{ textAlign: 'center', padding: '10px 0 16px', borderBottom: '1px solid var(--border-color)' }}>
            <div style={{
              width: '68px', height: '68px', margin: '0 auto 10px', borderRadius: '50%',
              background: 'linear-gradient(135deg, #1E293B 0%, #334155 100%)',
              border: `2px solid ${getRiskColor(dynamicRisk)}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: `0 0 16px ${getRiskColor(dynamicRisk)}40`
            }}>
              <Heart size={34} color={getRiskColor(dynamicRisk)} className="pulsing-heart" />
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#FFFFFF', marginBottom: '4px' }}>
              {twinStatus?.patient_name || 'Patient'}
            </h3>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <span>{p.age} Yrs • {p.gender?.toUpperCase()}</span>
              <span>•</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <MapPin size={12} /> {p.city}, {p.state}
              </span>
            </div>
          </div>

          {/* Clinical Risk Summary */}
          <div style={{ padding: '14px 0', borderBottom: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Framingham 10-Yr CVD Base:</span>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#F3F4F6' }}>{baseRisk}%</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>South Asian Recalibration:</span>
              <span className="badge badge-info" style={{ fontSize: '0.65rem' }}>1.45x Risk Enhancer</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Vascular Age:</span>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#F59E0B' }}>
                {p.cardiovascular_risk?.vascular_age || p.age} Years
              </span>
            </div>
          </div>

          {/* Conditions & Labs */}
          <div style={{ padding: '14px 0', borderBottom: '1px solid var(--border-color)' }}>
            <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', marginBottom: '8px', textTransform: 'uppercase' }}>
              Documented Diagnoses
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
              {p.clinical_history?.conditions?.map((c, i) => (
                <span key={i} style={{ 
                  background: 'rgba(56, 75, 112, 0.25)', padding: '3px 8px', borderRadius: '6px', 
                  fontSize: '0.72rem', color: '#E2E8F0' 
                }}>
                  {c}
                </span>
              ))}
            </div>

            <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', marginBottom: '8px', textTransform: 'uppercase' }}>
              Laboratory Biomarkers
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.78rem' }}>
              <div style={{ background: 'rgba(17, 24, 39, 0.6)', padding: '6px 8px', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.68rem' }}>Total Chol</span>
                <strong style={{ color: '#F3F4F6' }}>{p.labs?.total_cholesterol} mg/dL</strong>
              </div>
              <div style={{ background: 'rgba(17, 24, 39, 0.6)', padding: '6px 8px', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.68rem' }}>HbA1c</span>
                <strong style={{ color: p.labs?.hba1c >= 6.5 ? '#F87171' : '#34D399' }}>{p.labs?.hba1c}%</strong>
              </div>
              <div style={{ background: 'rgba(17, 24, 39, 0.6)', padding: '6px 8px', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.68rem' }}>Systolic BP</span>
                <strong style={{ color: '#F3F4F6' }}>{p.vitals?.systolic_bp} mmHg</strong>
              </div>
              <div style={{ background: 'rgba(17, 24, 39, 0.6)', padding: '6px 8px', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '0.68rem' }}>hs-CRP</span>
                <strong style={{ color: '#F3F4F6' }}>{p.labs?.hs_crp} mg/L</strong>
              </div>
            </div>
          </div>

          {/* Active Medications */}
          <div style={{ paddingTop: '12px' }}>
            <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', marginBottom: '8px', textTransform: 'uppercase' }}>
              Active Medications
            </p>
            {p.clinical_history?.medications?.length > 0 ? (
              p.clinical_history.medications.map((m, idx) => (
                <div key={idx} style={{ 
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                  fontSize: '0.75rem', marginBottom: '4px', color: 'var(--text-muted)' 
                }}>
                  <span>• {m.name}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>{m.dosage}</span>
                </div>
              ))
            ) : (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>No active cardiac prescriptions</span>
            )}
          </div>
        </div>

        {/* ── CENTER PANEL: LIVE PPG TELEMETRY & MULTIMODAL FUSION ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Top 4 Real-Time Metrics Tiles */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px' }}>
            
            {/* Tile 1: Heart Rate */}
            <div className="glass-panel" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>HEART RATE</span>
                <Activity size={18} color="#EF4444" />
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '1.9rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#FFFFFF' }}>
                  {v.bpm || 72}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>BPM</span>
              </div>
              <span style={{ fontSize: '0.7rem', color: v.bpm > 100 ? '#F87171' : (v.bpm < 55 ? '#FBBF24' : '#34D399') }}>
                {v.bpm > 100 ? '● Tachycardic Rate' : (v.bpm < 55 ? '● Bradycardic Rate' : '● Normal Range')}
              </span>
            </div>

            {/* Tile 2: Blood Oxygenation */}
            <div className="glass-panel" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>SPO2 LEVEL</span>
                <Zap size={18} color="#06B6D4" />
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '1.9rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#FFFFFF' }}>
                  {v.spo2 || 98}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>%</span>
              </div>
              <span style={{ fontSize: '0.7rem', color: v.spo2 < 92 ? '#F87171' : '#34D399' }}>
                {v.spo2 < 92 ? '● Hypoxic Warning' : '● Optimal Saturation'}
              </span>
            </div>

            {/* Tile 3: RMSSD (Autonomic Tone) */}
            <div className="glass-panel" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>RMSSD (HRV)</span>
                <TrendingUp size={18} color="#8B5CF6" />
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '1.9rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#FFFFFF' }}>
                  {v.rmssd || 38}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>ms</span>
              </div>
              <span style={{ fontSize: '0.7rem', color: v.rmssd < 20 ? '#F87171' : '#34D399' }}>
                {v.rmssd < 20 ? '● Sympathetic Strain' : '● Vagal Tone Balanced'}
              </span>
            </div>

            {/* Tile 4: ML Arrhythmia Screening */}
            <div className="glass-panel" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>AI RHYTHM SCREENING (v3 - 8 CLASS)</span>
                <ShieldCheck size={18} color="#10B981" />
              </div>
              <div style={{ fontSize: '1.02rem', fontWeight: 700, color: getArrhythmiaColor(v.arrhythmia_predicted), marginTop: '6px', marginBottom: '4px' }}>
                {formatArrhythmiaLabel(v.arrhythmia_predicted)}
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>
                Investigational prototype • Requires 12-lead ECG
              </span>
            </div>
          </div>

          {/* Real-Time Live Waveform Oscilloscope */}
          <div className="glass-panel" style={{ padding: '18px', flex: 1, minHeight: '220px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#06B6D4', boxShadow: '0 0 8px #06B6D4' }} />
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#FFFFFF' }}>
                  Live Photoplethysmogram (PPG) Telemetry Stream
                </span>
              </div>
              <div style={{ display: 'flex', gap: '12px', fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                <span>Sampling: <strong style={{ color: '#F3F4F6' }}>100 Hz</strong></span>
                <span>Signal Quality: <strong style={{ color: (v.signal_quality || 0.94) >= 0.40 ? '#34D399' : '#FBBF24' }}>
                  {((v.signal_quality !== undefined ? v.signal_quality : 0.94) * 100).toFixed(0)}% {(v.signal_quality !== undefined ? v.signal_quality : 0.94) >= 0.40 ? '(Optimal)' : '(Motion Gated)'}
                </strong></span>
              </div>
            </div>

            <div style={{ 
              flex: 1, background: 'rgba(10, 15, 29, 0.95)', borderRadius: '10px', 
              border: '1px solid rgba(56, 75, 112, 0.3)', padding: '10px', overflow: 'hidden', minHeight: '120px'
            }}>
              {renderWaveformSVG()}
            </div>
          </div>

          {/* Dynamic Instability Trajectory Trend */}
          <div className="glass-panel" style={{ padding: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#FFFFFF' }}>
                Dynamic Physiological Instability Trajectory (Telemetry Fusion)
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Updated continuously</span>
            </div>
            <div style={{ height: '90px', background: 'rgba(10, 15, 29, 0.7)', borderRadius: '8px', padding: '6px' }}>
              {renderTrajectorySVG()}
            </div>
          </div>
        </div>

        {/* ── RIGHT PANEL: "WHAT-IF" TREATMENT OUTCOME SIMULATOR ── */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <Sliders size={20} color="var(--accent-amber)" />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#FFFFFF' }}>
              "What-If" Treatment Simulator
            </h3>
          </div>
          <div style={{ background: 'rgba(56, 75, 112, 0.2)', padding: '6px 10px', borderRadius: '6px', marginBottom: '14px', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            ⏱ <strong>Time Horizon:</strong> 5–10 year sustained therapeutic adherence. Educational decision support — not clinical prescribing.
          </div>

          {/* Intervention 1: Systolic BP Adjustment */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Target Systolic BP</span>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#FFFFFF', fontFamily: 'var(--font-mono)' }}>
                {simSBP} mmHg
              </span>
            </div>
            <input
              type="range"
              min="105"
              max="175"
              value={simSBP}
              onChange={(e) => setSimSBP(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent-cyan)' }}
            />
          </div>

          {/* Intervention 2: Medication Additions */}
          <div style={{ marginBottom: '16px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '8px' }}>
              Add Virtual Medication Therapies:
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: '#E2E8F0', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={simMeds.metoprolol}
                  onChange={(e) => setSimMeds({ ...simMeds, metoprolol: e.target.checked })}
                  style={{ accentColor: 'var(--accent-cyan)' }}
                />
                + Metoprolol 50mg (Beta-Blocker: -12 BPM)
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: '#E2E8F0', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={simMeds.atorvastatin}
                  onChange={(e) => setSimMeds({ ...simMeds, atorvastatin: e.target.checked })}
                  style={{ accentColor: 'var(--accent-cyan)' }}
                />
                + Atorvastatin 40mg (Statin: -25% LDL)
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: '#E2E8F0', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={simMeds.ramipril}
                  onChange={(e) => setSimMeds({ ...simMeds, ramipril: e.target.checked })}
                  style={{ accentColor: 'var(--accent-cyan)' }}
                />
                + Ramipril 5mg (ACE-i: -12 mmHg SBP)
              </label>
            </div>
          </div>

          {/* Intervention 3: Smoking Cessation */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: '#E2E8F0', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={!simSmoker}
                onChange={(e) => setSimSmoker(!e.target.checked)}
                style={{ accentColor: 'var(--accent-cyan)' }}
              />
              Enforce Complete Smoking Cessation
            </label>
          </div>

          {/* Run Button */}
          <button
            onClick={runSimulation}
            disabled={isSimulating}
            style={{
              background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
              color: '#FFFFFF',
              padding: '11px',
              borderRadius: '8px',
              fontWeight: 700,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              boxShadow: '0 4px 14px rgba(59, 130, 246, 0.4)',
              marginBottom: '16px'
            }}
          >
            <Play size={16} fill="#FFFFFF" />
            {isSimulating ? 'SIMULATING TWIN...' : 'RUN VIRTUAL SIMULATION'}
          </button>

          {/* Simulation Output Card */}
          {simResult && (
            <div style={{ 
              background: 'rgba(16, 185, 129, 0.08)', borderRadius: '10px', 
              border: '1px solid rgba(16, 185, 129, 0.35)', padding: '14px', flex: 1 
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                <CheckCircle2 size={16} color="#10B981" />
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#34D399' }}>
                  Projected Outcome
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Base Risk:</span>
                <span style={{ fontSize: '0.85rem', color: '#EF4444', textDecoration: 'line-through' }}>
                  {simResult.original_base_risk}%
                </span>
                <span style={{ fontSize: '1rem', fontWeight: 800, color: '#10B981' }}>
                  → {simResult.projected_base_risk}%
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.75rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Absolute Risk Reduction:</span>
                <strong style={{ color: '#34D399' }}>-{simResult.absolute_risk_reduction}%</strong>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px', fontSize: '0.75rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Projected Vascular Age:</span>
                <strong style={{ color: '#FBBF24' }}>{simResult.projected_vascular_age} Years</strong>
              </div>

              <p style={{ fontSize: '0.72rem', color: '#E2E8F0', lineHeight: 1.4 }}>
                {simResult.clinical_summary}
              </p>
            </div>
          )}

          {/* Recent Alerts Feed */}
          <div style={{ marginTop: 'auto', paddingTop: '12px' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-dim)', display: 'block', marginBottom: '6px', textTransform: 'uppercase' }}>
              Real-Time Alert Feed
            </span>
            {twinStatus?.recent_alerts?.length > 0 ? (
              twinStatus.recent_alerts.map((al, i) => (
                <div key={i} style={{ 
                  background: 'rgba(239, 68, 68, 0.1)', padding: '6px 8px', borderRadius: '6px', 
                  fontSize: '0.7rem', color: '#FCA5A5', marginBottom: '4px', display: 'flex', gap: '6px' 
                }}>
                  <Clock size={12} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>[{al.time}] {al.message}</span>
                </div>
              ))
            ) : (
              <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>No active critical alerts</span>
            )}
          </div>
        </div>

      </div>

      {/* ── FOOTER: CLINICAL GOVERNANCE & REGULATORY NOTICE ── */}
      <footer style={{ 
        marginTop: '16px', padding: '12px 18px', borderRadius: '10px',
        background: 'rgba(15, 23, 42, 0.65)', border: '1px solid rgba(56, 75, 112, 0.3)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px',
        fontSize: '0.72rem', color: 'var(--text-muted)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Info size={16} color="var(--accent-cyan)" />
          <span>
            <strong>Clinical Decision Support Notice:</strong> CardioTwin provides non-diagnostic risk surveillance. Photoplethysmogram (PPG) optical screening is an observational modality; all detected dysrhythmias require urgent 12-lead diagnostic ECG confirmation and physician review.
          </span>
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <span>Dataset: Multi-Modal (MIMIC-III 2,000 pts + CinC 2015 + BUT PPG + BIDMC | 2,271 pts / 4,683 windows)</span>
          <span>Model: v3 (8-Class XGBoost)</span>
          <span>Version: 3.0.0</span>
        </div>
      </footer>

    </div>
  );
}
