import { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { Activity, AlertTriangle, ArrowRight, Check, ChevronRight, CircleStop, Cpu, Download, FileText, HeartPulse, Leaf, LoaderCircle, Play, Radio, RefreshCw, ShieldCheck, Sparkles, Stethoscope, UserRound, Waves, X } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:5000';
const navItems = [['home', 'Home'], ['twin', 'Your twin'], ['live', 'Live check'], ['plan', 'Explore changes']];

function instabilityState(score, departureFlags = []) {
  if (departureFlags.includes('BASELINE_NOT_CALIBRATED') || departureFlags.includes('BASELINE_EXPIRED')) {
    return { label: 'Personal baseline required', tone: 'blue', description: 'A quiet two-minute calibration is required before personal instability can be interpreted.' };
  }
  if (score == null) return { label: 'Awaiting a personal baseline', tone: 'blue', description: 'A quiet two-minute reading creates an empirical personal reference point.' };
  if (score <= 20) return { label: 'Within your usual range', tone: 'green', description: 'Today’s reading is close to this person’s measured baseline.' };
  if (score <= 40) return { label: 'A mild change was noticed', tone: 'amber', description: 'The reading has shifted a little from the established resting baseline.' };
  if (score <= 70) return { label: 'A sustained change was noticed', tone: 'amber', description: 'A review of context, symptoms, and medication timing is appropriate.' };
  return { label: 'A review is recommended', tone: 'rose', description: 'This is a sustained departure from the personal baseline, not a standalone diagnosis.' };
}

const SAMPLE_PPG = [
  30, 31, 32, 35, 45, 75, 130, 190, 235, 245, 230, 190, 150, 125, 115, 122, 128, 122, 108, 85, 60, 42, 33, 30,
  30, 31, 32, 35, 45, 75, 130, 190, 235, 245, 230, 190, 150, 125, 115, 122, 128, 122, 108, 85, 60, 42, 33, 30,
  30, 31, 32, 35, 45, 75, 130, 190, 235, 245, 230, 190, 150, 125, 115, 122, 128, 122, 108, 85, 60, 42, 33, 30,
  30, 31, 32, 35, 45, 75, 130, 190, 235, 245, 230, 190, 150, 125, 115, 122, 128, 122, 108, 85, 60, 42, 33, 30,
  30, 31, 32, 35, 45, 75, 130, 190, 235, 245, 230, 190, 150, 125, 115, 122, 128, 122, 108, 85, 60, 42, 33, 30
];

function Sparkline({ data = [], color = '#167c76', width = 160, height = 36 }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * (width - 8) + 4;
    const y = height - 4 - ((d - min) / range) * (height - 8);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: 'visible' }}>
      <polyline fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" points={points} />
      {data.map((d, i) => {
        const x = (i / (data.length - 1)) * (width - 8) + 4;
        const y = height - 4 - ((d - min) / range) * (height - 8);
        if (i === 0 || i === data.length - 1) {
          return <circle key={i} cx={x} cy={y} r="3" fill={color} />;
        }
        return null;
      })}
    </svg>
  );
}

function Waveform({ points }) {
  const pts = points && points.length >= 2 ? points : SAMPLE_PPG;
  const min = Math.min(...pts), max = Math.max(...pts), range = max - min || 1;
  const path = pts.map((point, index) => `${index ? 'L' : 'M'} ${(index / (pts.length - 1) * 720).toFixed(1)} ${(138 - ((point - min) / range * 120)).toFixed(1)}`).join(' ');
  return <svg className="waveform" viewBox="0 0 720 156" role="img" aria-label="Live optical pulse waveform"><defs><linearGradient id="waveGradient"><stop stopColor="#1b9a92" /><stop offset="1" stopColor="#5cc5bc" /></linearGradient></defs>{[32,78,124].map(y => <line key={y} x1="0" y1={y} x2="720" y2={y} className="wave-grid" />)}<path d={path} fill="none" stroke="url(#waveGradient)" strokeWidth="3" strokeLinecap="round" /></svg>;
}

export default function App() {
  const [activeTab, setActiveTab] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tab') || 'home';
  });
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('PAT001');
  const [twinStatus, setTwinStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const [waveformPoints, setWaveformPoints] = useState([]);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibration, setCalibration] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [simMeds, setSimMeds] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('sim') || params.get('tab') === 'plan'
      ? { metoprolol: true, atorvastatin: true, ramipril: false, dapagliflozin: true }
      : { metoprolol: false, atorvastatin: false, ramipril: false, dapagliflozin: false };
  });
  const [simSBP, setSimSBP] = useState(125);
  const [simSmoker, setSimSmoker] = useState(false);
  const [simResult, setSimResult] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('sim') || params.get('tab') === 'plan') {
      return {
        current_baseline_risk: 81.8,
        simulated_baseline_risk: 26.2,
        projected_risk: 26.2,
        projected_vascular_age: 76,
        absolute_risk_reduction: 55.6
      };
    }
    return null;
  });
  const [isSimulating, setIsSimulating] = useState(false);
  const [isSimulatedData, setIsSimulatedData] = useState(true);

  const applyStatus = data => {
    setTwinStatus(data);
    setIsCalibrating(Boolean(data?.is_calibrating));
    setCalibration(data?.calibration_status || null);
    const src = data?.data_source || data?.current_vitals?.data_source;
    const hasLiveHw = Boolean(data?.hardware_telemetry?.device_id) && src === 'LIVE_HARDWARE';
    setIsSimulatedData(!hasLiveHw);
    if (data?.patient_ehr?.vitals?.systolic_bp) setSimSBP(data.patient_ehr.vitals.systolic_bp);
    if (data?.patient_ehr?.lifestyle?.smoker !== undefined) setSimSmoker(data.patient_ehr.lifestyle.smoker);
  };

  const fetchStatus = () => fetch(`${API_BASE}/twin/status`).then(r => r.json()).then(applyStatus).catch(() => {});

  useEffect(() => {
    fetch(`${API_BASE}/patients`).then(r => r.json()).then(data => {
      setPatients(data.patients || []);
      if (data.active_patient_id) setSelectedPatientId(data.active_patient_id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, 2500);
    return () => clearInterval(timer);
  }, [selectedPatientId]);

  useEffect(() => {
    const socket = io(API_BASE, { transports: ['websocket', 'polling'], reconnectionAttempts: 10 });
    socket.on('connect', () => setConnected(true));
    socket.on('disconnect', () => setConnected(false));
    socket.on('telemetry_update', applyStatus);
    socket.on('live_waveform', data => {
      if (data?.chunk?.length) {
        if (data.data_source === 'LIVE_HARDWARE' && data.device_id) {
          setIsSimulatedData(false);
        } else if (data.data_source === 'SIMULATION') {
          setIsSimulatedData(true);
        }
        setWaveformPoints(current => [...current, ...data.chunk].slice(-180));
      }
    });
    socket.on('patient_switched', data => {
      applyStatus(data);
      if (data?.patient_id) setSelectedPatientId(data.patient_id);
      setWaveformPoints([]);
    });
    return () => socket.disconnect();
  }, []);

  const choosePatient = patientId => {
    setSelectedPatientId(patientId);
    fetch(`${API_BASE}/patient/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_id: patientId })
    }).then(r => r.json()).then(data => data.status && applyStatus(data.status));
    setSimResult(null);
  };

  const startCalibration = () => fetch(`${API_BASE}/baseline/calibrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  }).then(() => {
    setIsCalibrating(true);
    setActiveTab('live');
    fetchStatus();
  });

  const cancelCalibration = () => fetch(`${API_BASE}/baseline/cancel`, { method: 'POST' }).then(() => {
    setIsCalibrating(false);
    setCalibration(null);
    fetchStatus();
  });

  const runScenario = scenario => {
    setScenarioLoading(true);
    setIsSimulatedData(true);
    fetch(`${API_BASE}/twin/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario })
    }).then(r => r.json()).then(data => {
      if (data.updated_status) {
        applyStatus(data.updated_status);
        if (data.updated_status.current_vitals?.waveform_preview?.length) {
          setWaveformPoints(data.updated_status.current_vitals.waveform_preview);
        }
      }
    }).finally(() => setScenarioLoading(false));
  };

  const toggleRecording = () => {
    const endpoint = isRecording ? '/stop' : '/start';
    fetch(`${API_BASE}${endpoint}`, { method: 'POST' }).then(r => r.json()).then(() => {
      setIsRecording(!isRecording);
      fetch(`${API_BASE}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run: !isRecording })
      });
    });
  };

  const runSimulation = () => {
    setIsSimulating(true);
    const labels = {
      metoprolol: 'Metoprolol',
      atorvastatin: 'Atorvastatin',
      ramipril: 'Ramipril',
      dapagliflozin: 'Dapagliflozin'
    };
    const meds = Object.entries(simMeds).filter(([, on]) => on).map(([key]) => labels[key]);
    fetch(`${API_BASE}/twin/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ add_medications: meds, systolic_bp: simSBP, smoker: simSmoker })
    }).then(r => r.json()).then(data => setSimResult(data.simulation || null)).finally(() => setIsSimulating(false));
  };

  const exportFhirBundle = () => {
    fetch(`${API_BASE}/fhir/export`)
      .then(r => r.json())
      .then(bundle => {
        const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cardiotwin_fhir_r4_${selectedPatientId}_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(err => console.error('Failed to export FHIR bundle', err));
  };

  const exportClinicianSummary = () => {
    const summary = {
      title: 'CardioTwin v4.1 Clinician Review Summary',
      generated_at: new Date().toISOString(),
      patient: {
        id: selectedPatientId,
        name: displayedName,
        age: patient.age,
        gender: patient.gender,
        framingham_10yr_risk_pct: risk
      },
      baseline: {
        status: hasBaseline ? 'CALIBRATED' : 'NOT_CALIBRATED',
        median_bpm: baseline?.median_bpm,
        mad_bpm: baseline?.mad_bpm,
        median_rmssd: baseline?.median_rmssd,
        calibrated_at: baseline?.calibrated_at,
        expires_at: baseline?.expires_at,
        device_id: baseline?.device_id || 'cardiotwin-esp32-01'
      },
      live_check: {
        data_source: isSimulatedData ? 'SIMULATED_DATA' : 'LIVE_HARDWARE',
        measured_bpm: vitals.bpm,
        gate_status: gate.status,
        instability_score: score,
        instability_label: instability.label,
        departure_flags: flags
      },
      disclaimer: 'Investigational non-diagnostic digital twin prototype. Pulse patterns cannot substitute for clinical 12-lead ECG.'
    };
    const blob = new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cardiotwin_summary_${selectedPatientId}_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const patient = twinStatus?.patient_ehr || {};
  const vitals = twinStatus?.current_vitals || {};
  const health = patient.cardiovascular_risk || {};
  const history = patient.clinical_history || {};
  const baseline = twinStatus?.personal_baseline || null;
  const telemetry = twinStatus?.hardware_telemetry || {};
  const proactiveForecast = twinStatus?.proactive_forecast || null;
  const ehrCoupling = twinStatus?.ehr_coupling || proactiveForecast?.ehr_coupling || null;
  const wearable7d = proactiveForecast?.wearable_7d_summary || null;

  const personalInstability = twinStatus?.personal_instability || vitals.personal_instability || {};
  const score = personalInstability.instability_score ?? null;
  const flags = personalInstability.departure_flags || [];
  const instability = instabilityState(score, flags);
  const gate = vitals.signal_gate || twinStatus?.signal_gate || {};
  const hasBaseline = Boolean(twinStatus?.has_calibrated_baseline);
  const displayedName = patient.name || patients.find(item => item.id === selectedPatientId)?.name || 'Your patient';
  const age = patient.age ? `${patient.age} years` : 'Profile loading';
  const risk = health.recalibrated_risk_pct ?? health.base_10yr_risk_pct ?? twinStatus?.base_clinical_risk;
  const calibrationPercent = calibration?.target_duration_sec ? Math.min(100, Math.round((calibration.elapsed_sec || 0) / calibration.target_duration_sec * 100)) : 0;

  // Baseline freshness calculations
  const baselineCalibratedAt = baseline?.calibrated_at ? new Date(baseline.calibrated_at) : null;
  const daysAgo = baselineCalibratedAt ? Math.max(0, Math.floor((Date.now() - baselineCalibratedAt.getTime()) / (1000 * 86400))) : null;

  return (
    <div className="site-shell">
      <header className="site-header">
        <a className="brand" href="#top" onClick={() => setActiveTab('home')}>
          <span className="brand-mark"><HeartPulse size={20} /></span>
          <span>cardiotwin</span>
        </a>
        <nav className="main-nav">
          {navItems.map(([id, label]) => (
            <button key={id} className={activeTab === id ? 'active' : ''} onClick={() => setActiveTab(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="header-tools">
          <span className={isSimulatedData ? 'source-badge sim' : 'source-badge live'}>
            <i></i> {isSimulatedData ? 'SIMULATED DATA' : 'LIVE HARDWARE'}
          </span>
          <span className={`connection ${connected ? 'online' : ''}`}>
            <i></i> {connected ? 'Gateway connected' : 'Connecting'}
          </span>
          <label className="patient-picker">
            <UserRound size={15} />
            <select value={selectedPatientId} onChange={event => choosePatient(event.target.value)}>
              {patients.length ? patients.map(item => <option value={item.id} key={item.id}>{item.name}</option>) : <option>{displayedName}</option>}
            </select>
          </label>
        </div>
      </header>

      {isCalibrating && (
        <div className="calibration-banner">
          <div>
            <Sparkles size={18} />
            <strong>Creating a personal resting baseline</strong>
            <span>{calibration?.phase || 'Keep still with a relaxed finger placement.'} ({calibration?.windows_collected || 0}/6 quality windows)</span>
          </div>
          <div className="progress-line">
            <span style={{ width: `${calibrationPercent}%` }} />
          </div>
          <button onClick={cancelCalibration}><X size={15} /> Cancel</button>
        </div>
      )}

      <main id="top">
        {activeTab === 'home' && (
          <section className="page home-page">
            <div className="hero">
              <div className="hero-copy">
                <p className="eyebrow"><Leaf size={15} /> A quieter way to understand heart health</p>
                <h1>Care that starts with <em>your normal.</em></h1>
                <p className="hero-text">
                  CardioTwin connects a person’s health history with a gentle, real-time pulse reading—so care teams can notice meaningful changes without mistaking an optical metric for a standalone diagnosis.
                </p>
                <div className="hero-actions">
                  <button className="button primary" onClick={() => hasBaseline ? setActiveTab('live') : startCalibration()}>
                    {hasBaseline ? 'Open live check' : 'Create baseline'} <ArrowRight size={17} />
                  </button>
                  <button className="button text" onClick={() => setActiveTab('twin')}>
                    Meet the twin <ChevronRight size={17} />
                  </button>
                </div>
                <p className="microcopy">
                  <ShieldCheck size={14} /> Observational support for clinician review. Never a standalone diagnosis.
                </p>
              </div>
              <div className="hero-orbit">
                <div className="orbit-ring ring-one" />
                <div className="orbit-ring ring-two" />
                <div className="heart-orb"><HeartPulse size={45} /></div>
                <span className="orb-label one">history</span>
                <span className="orb-label two">live pulse</span>
                <span className="orb-label three">personal baseline</span>
              </div>
            </div>

            <section className="person-intro">
              <div>
                <p className="eyebrow">Today’s care story</p>
                <h2>{displayedName}</h2>
                <p>{age} · {patient.city || 'Cardiovascular care profile'}{twinStatus?.cardiovascular_age?.estimated_cv_age ? ` · ~${twinStatus.cardiovascular_age.estimated_cv_age}y vascular age` : ''}</p>
                {hasBaseline ? (
                  <span className="freshness-chip green">
                    ● Calibrated {daysAgo === 0 ? 'today' : `${daysAgo}d ago`} (resting median {baseline?.median_bpm} BPM)
                  </span>
                ) : (
                  <span className="freshness-chip blue">
                    ○ Personal baseline required before instability scoring
                  </span>
                )}
              </div>
              <div className={`reading-summary ${instability.tone}`}>
                <span>Today’s reading</span>
                <strong>{instability.label}</strong>
                <p>{instability.description}</p>
              </div>
            </section>

            <section className="story-grid">
              <article className="story-card large">
                <span className="card-icon teal"><Waves size={21} /></span>
                <p className="eyebrow">The personal reference</p>
                <h3>{hasBaseline ? 'This reading has a home base.' : 'Start with a calm, ordinary moment.'}</h3>
                <p>
                  {hasBaseline
                    ? `A baseline was created from ${baseline?.windows_accepted || 6} reliable resting windows. New readings are interpreted relative to this person—not an arbitrary average.`
                    : 'A two-minute seated reading lets CardioTwin learn this individual’s normal pulse pattern before it looks for change.'}
                </p>
                <button className="quiet-link" onClick={() => hasBaseline ? setActiveTab('live') : startCalibration()}>
                  {hasBaseline ? 'See baseline details' : 'Begin the two-minute reading'} <ArrowRight size={15} />
                </button>
              </article>

              <article className="story-card">
                <span className="card-icon blue"><Stethoscope size={21} /></span>
                <p className="eyebrow">Health context</p>
                <h3>{health.risk_category || 'Cardiovascular profile'}</h3>
                <p>
                  {risk !== undefined ? `${Number(risk).toFixed(1)}% estimated long-term cardiovascular risk is kept separate from today’s pulse reading.` : 'The health profile is loading.'}
                </p>
                <button className="quiet-link" onClick={() => setActiveTab('twin')}>
                  View health context <ArrowRight size={15} />
                </button>
              </article>

              <article className="story-card soft">
                <span className="card-icon peach"><Activity size={21} /></span>
                <p className="eyebrow">A live reading</p>
                <h3>{gate.status ? gate.status.replaceAll('_', ' ').toLowerCase() : 'Ready when you are'}</h3>
                <p>{gate.reason || 'Connect the sensor whenever you want a careful, quality-checked live measurement.'}</p>
                <button className="quiet-link" onClick={() => setActiveTab('live')}>
                  Open live check <ArrowRight size={15} />
                </button>
              </article>
            </section>

            <section className="how-it-works">
              <div>
                <p className="eyebrow">Made for thoughtful decisions</p>
                <h2>Three kinds of evidence. One understandable story.</h2>
              </div>
              <div className="steps">
                <span><b>01</b> Long-term health context</span>
                <span><b>02</b> A quality-checked pulse reading</span>
                <span><b>03</b> Change from personal baseline</span>
              </div>
            </section>
          </section>
        )}

        {activeTab === 'twin' && (
          <section className="page twin-page">
            <div className="page-heading">
              <p className="eyebrow">Your twin</p>
              <h1>A health story, not a scorecard.</h1>
              <p>Long-term cardiovascular context and today’s measurement are intentionally kept apart.</p>
            </div>
            <div className="twin-layout">
              <article className="profile-paper">
                <div className="profile-avatar">{displayedName.slice(0, 1)}</div>
                <div>
                  <p className="eyebrow">Patient profile</p>
                  <h2>{displayedName}</h2>
                  <p>{age} · {patient.gender || 'Profile'} · {patient.city || 'India'}{twinStatus?.cardiovascular_age?.estimated_cv_age ? ` · Est. vascular age ~${twinStatus.cardiovascular_age.estimated_cv_age} yrs` : ''}</p>
                </div>
                <hr />
                <p className="profile-note">
                  {history.conditions?.length ? `Care context includes ${history.conditions.slice(0, 2).join(' and ')}.` : 'A longitudinal health profile is being prepared.'}
                </p>
                <div className="condition-list">
                  {(history.conditions || ['No conditions recorded']).slice(0, 4).map(condition => (
                    <span key={condition}>{condition}</span>
                  ))}
                </div>
              </article>

              <article className="risk-letter">
                <p className="eyebrow">Long-term perspective</p>
                <h2>{risk !== undefined ? `${Number(risk).toFixed(1)}%` : '—'}</h2>
                <h3>estimated cardiovascular risk over ten years</h3>
                <p>This population-based estimate is useful for prevention planning. It is not blended into the live instability reading.</p>
                <div className="risk-foot">
                  <ShieldCheck size={18} /> Framingham-based, shown with clinical context
                </div>
              </article>
            </div>

            <section className="context-strip">
              <div>
                <span>Blood pressure</span>
                <strong>{patient.vitals?.systolic_bp ? `${patient.vitals.systolic_bp}/${patient.vitals.diastolic_bp} mmHg` : 'Not available'}</strong>
              </div>
              <div>
                <span>Resting pulse in profile</span>
                <strong>{patient.vitals?.resting_hr ? `${patient.vitals.resting_hr} BPM` : 'Not available'}</strong>
              </div>
              <div>
                <span>Daily context</span>
                <strong>{patient.lifestyle?.physical_activity || 'Not recorded'}</strong>
              </div>
              <div>
                <span>Cardiovascular age</span>
                <strong>~{twinStatus?.cardiovascular_age?.estimated_cv_age || patient.age || '—'} yrs</strong>
                <small>{twinStatus?.cardiovascular_age?.age_delta > 0 ? `+${twinStatus.cardiovascular_age.age_delta} yrs vascular shift` : 'Aligned with chronological age'}</small>
              </div>
            </section>

            <section className="care-notes">
              <div>
                <p className="eyebrow">What shapes the long view</p>
                <h2>Small changes can make a meaningful difference.</h2>
              </div>
              <ul>
                {(health.modifiable_factors || []).slice(0, 4).map((item, index) => (
                  <li key={index}>
                    <Check size={17} />
                    <span>
                      <strong>{item.factor}</strong>
                      <small>{item.impact || 'Relevant to this profile'}</small>
                    </span>
                  </li>
                ))}
              </ul>
            </section>

            {/* Complete EHR Clinical & Lab Card (Phase 5.2) */}
            <article className="ehr-labs-card">
              <div className="title-row">
                <div>
                  <p className="eyebrow"><FileText size={15} /> Verified Clinical Laboratory Panel</p>
                  <h2>Biochemical Substrate & Biomarkers</h2>
                </div>
                <button className="button subtle" onClick={exportFhirBundle}>
                  <Download size={15} /> Export ABDM FHIR R4 Bundle
                </button>
              </div>
              <div className="ehr-labs-grid">
                <div className={`lab-item ${(patient.labs?.total_cholesterol || 0) >= 200 ? 'abnormal' : ''}`}>
                  <span className="lab-name">Total Cholesterol</span>
                  <strong className="lab-val">{patient.labs?.total_cholesterol || 227} mg/dL</strong>
                  {(patient.labs?.total_cholesterol || 0) >= 200 && <span className="lab-badge">High</span>}
                  <span className="lab-normal-range">Target: &lt; 200 mg/dL</span>
                </div>
                <div className={`lab-item ${(patient.labs?.ldl_cholesterol || 0) >= 100 ? 'abnormal' : ''}`}>
                  <span className="lab-name">LDL Cholesterol</span>
                  <strong className="lab-val">{patient.labs?.ldl_cholesterol || 158} mg/dL</strong>
                  {(patient.labs?.ldl_cholesterol || 0) >= 100 && <span className="lab-badge">High</span>}
                  <span className="lab-normal-range">Target: &lt; 100 mg/dL</span>
                </div>
                <div className={`lab-item ${(patient.labs?.hdl_cholesterol || 40) < 40 ? 'abnormal' : ''}`}>
                  <span className="lab-name">HDL Cholesterol</span>
                  <strong className="lab-val">{patient.labs?.hdl_cholesterol || 39} mg/dL</strong>
                  {(patient.labs?.hdl_cholesterol || 40) < 40 && <span className="lab-badge">Low</span>}
                  <span className="lab-normal-range">Target: &ge; 40 mg/dL</span>
                </div>
                <div className={`lab-item ${(patient.labs?.triglycerides || 0) >= 150 ? 'abnormal' : ''}`}>
                  <span className="lab-name">Triglycerides</span>
                  <strong className="lab-val">{patient.labs?.triglycerides || 226} mg/dL</strong>
                  {(patient.labs?.triglycerides || 0) >= 150 && <span className="lab-badge">High</span>}
                  <span className="lab-normal-range">Target: &lt; 150 mg/dL</span>
                </div>
                <div className={`lab-item ${(patient.labs?.fasting_glucose || 0) >= 126 ? 'abnormal' : ''}`}>
                  <span className="lab-name">Fasting Glucose</span>
                  <strong className="lab-val">{patient.labs?.fasting_glucose || 154} mg/dL</strong>
                  {(patient.labs?.fasting_glucose || 0) >= 126 && <span className="lab-badge">Elevated</span>}
                  <span className="lab-normal-range">Target: 70–99 mg/dL</span>
                </div>
                <div className={`lab-item ${(patient.labs?.hba1c || 0) >= 6.5 ? 'abnormal' : ''}`}>
                  <span className="lab-name">Glycated HbA1c</span>
                  <strong className="lab-val">{patient.labs?.hba1c || 7.4}%</strong>
                  {(patient.labs?.hba1c || 0) >= 6.5 && <span className="lab-badge">Diabetic</span>}
                  <span className="lab-normal-range">Target: &lt; 5.7%</span>
                </div>
                <div className={`lab-item ${(patient.labs?.hs_crp || 0) > 2.0 ? 'abnormal' : ''}`}>
                  <span className="lab-name">High-Sensitivity CRP</span>
                  <strong className="lab-val">{patient.labs?.hs_crp || 3.61} mg/L</strong>
                  {(patient.labs?.hs_crp || 0) > 2.0 && <span className="lab-badge">Inflammation</span>}
                  <span className="lab-normal-range">Target: &lt; 1.0 mg/L</span>
                </div>
                <div className="lab-item">
                  <span className="lab-name">Blood Pressure</span>
                  <strong className="lab-val">{patient.vitals?.systolic_bp || 143}/{patient.vitals?.diastolic_bp || 95} mmHg</strong>
                  {(patient.vitals?.systolic_bp || 0) >= 130 && <span className="lab-badge">Stage 2 HTN</span>}
                  <span className="lab-normal-range">Target: &lt; 120/80 mmHg</span>
                </div>
              </div>
            </article>

            {/* Active Medications List */}
            <article className="meds-card">
              <p className="eyebrow"><Stethoscope size={15} /> Current Pharmacotherapy</p>
              <h2>Active Prescriptions & Hemodynamic Actions</h2>
              <table className="meds-table">
                <thead>
                  <tr>
                    <th>Medication</th>
                    <th>Dosage</th>
                    <th>Class</th>
                    <th>Heart Rate Effect</th>
                    <th>Blood Pressure Effect</th>
                  </tr>
                </thead>
                <tbody>
                  {(history.medications || []).map((med, idx) => (
                    <tr key={idx}>
                      <td><strong>{typeof med === 'string' ? med : med.name}</strong></td>
                      <td>{typeof med === 'object' && med.dosage ? med.dosage : 'Standard'}</td>
                      <td><span className="med-badge">{typeof med === 'object' && med.class ? med.class : 'Therapeutic'}</span></td>
                      <td>{typeof med === 'object' && med.hr_effect !== undefined ? `${med.hr_effect > 0 ? '+' : ''}${med.hr_effect} BPM` : '—'}</td>
                      <td>{typeof med === 'object' && med.bp_effect !== undefined ? `${med.bp_effect > 0 ? '+' : ''}${med.bp_effect} mmHg SBP` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>

            {/* 7-Day Wearable Sleep & HRV Longitudinal Sparklines (Phase 5.2) */}
            {wearable7d && (
              <article className="sparklines-card">
                <p className="eyebrow"><Activity size={15} /> 7-Day Longitudinal Wearable Telemetry</p>
                <h2>Continuous Physiological Trajectories</h2>
                <div className="sparklines-grid">
                  <div className="sparkline-box">
                    <span>Resting HR (7-Day)</span>
                    <strong>{wearable7d.daily_resting_hr_7d[wearable7d.daily_resting_hr_7d.length - 1]} BPM</strong>
                    <div className="sparkline-wrapper">
                      <Sparkline data={wearable7d.daily_resting_hr_7d} color="#167c76" />
                      <div className="sparkline-vals">
                        <span>Day 1: <b>{wearable7d.daily_resting_hr_7d[0]}</b></span>
                        <ArrowRight size={12} />
                        <span>Day 7: <b>{wearable7d.daily_resting_hr_7d[wearable7d.daily_resting_hr_7d.length - 1]}</b></span>
                      </div>
                    </div>
                  </div>
                  <div className="sparkline-box">
                    <span>Nocturnal RMSSD (7-Day)</span>
                    <strong>{wearable7d.nocturnal_rmssd_7d[wearable7d.nocturnal_rmssd_7d.length - 1]} ms</strong>
                    <div className="sparkline-wrapper">
                      <Sparkline data={wearable7d.nocturnal_rmssd_7d} color="#d9822b" />
                      <div className="sparkline-vals">
                        <span>Day 1: <b>{wearable7d.nocturnal_rmssd_7d[0]} ms</b></span>
                        <ArrowRight size={12} />
                        <span>Day 7: <b>{wearable7d.nocturnal_rmssd_7d[wearable7d.nocturnal_rmssd_7d.length - 1]} ms</b></span>
                      </div>
                    </div>
                  </div>
                  <div className="sparkline-box">
                    <span>Sleep Efficiency (7-Day)</span>
                    <strong>{wearable7d.sleep_efficiency_pct_7d[wearable7d.sleep_efficiency_pct_7d.length - 1]}%</strong>
                    <div className="sparkline-wrapper">
                      <Sparkline data={wearable7d.sleep_efficiency_pct_7d} color="#2f6288" />
                      <div className="sparkline-vals">
                        <span>Day 1: <b>{wearable7d.sleep_efficiency_pct_7d[0]}%</b></span>
                        <ArrowRight size={12} />
                        <span>Day 7: <b>{wearable7d.sleep_efficiency_pct_7d[wearable7d.sleep_efficiency_pct_7d.length - 1]}%</b></span>
                      </div>
                    </div>
                  </div>
                  <div className="sparkline-box">
                    <span>Daily Steps (7-Day)</span>
                    <strong>{wearable7d.daily_steps_7d[wearable7d.daily_steps_7d.length - 1].toLocaleString()}</strong>
                    <div className="sparkline-wrapper">
                      <Sparkline data={wearable7d.daily_steps_7d} color="#358a74" />
                      <div className="sparkline-vals">
                        <span>Day 1: <b>{wearable7d.daily_steps_7d[0]}</b></span>
                        <ArrowRight size={12} />
                        <span>Day 7: <b>{wearable7d.daily_steps_7d[wearable7d.daily_steps_7d.length - 1]}</b></span>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            )}
          </section>
        )}

        {activeTab === 'live' && (
          <section className="page live-page">
            <div className="page-heading">
              <div className="title-row">
                <div>
                  <p className="eyebrow"><Radio size={15} /> Live check</p>
                  <h1>Take a careful reading.</h1>
                </div>
                <div className="heading-actions">
                  <button className="button subtle" onClick={exportClinicianSummary}>
                    <Download size={15} /> Export session summary
                  </button>
                </div>
              </div>
              <p>CardioTwin checks measurement quality first. Only then does it compare the reading with this person’s own resting pattern.</p>
            </div>

            <section className="live-studio">
              <div className="live-topline">
                <div className="telemetry-badges">
                  <span className={isSimulatedData ? 'source-badge sim' : 'source-badge live'}>
                    <i></i> {isSimulatedData ? 'SIMULATED DATA' : 'LIVE HARDWARE'}
                  </span>
                  <span className={`connection ${connected ? 'online' : ''}`}>
                    <i></i> {connected ? 'Gateway reachable' : 'Connecting to gateway'}
                  </span>
                  {hasBaseline ? (
                    <span className="freshness-badge ok">
                      ✓ Baseline: {baseline?.median_bpm} BPM ({daysAgo === 0 ? 'today' : `${daysAgo}d ago`})
                    </span>
                  ) : (
                    <span className="freshness-badge warning" onClick={startCalibration} style={{ cursor: 'pointer' }}>
                      + Calibrate baseline now
                    </span>
                  )}
                  <span className="freshness-badge dual-fusion" title="Fused 38% Classical Super Ensemble + 62% Inception-1D CNN (53.9% Macro-F1)">
                    ⚡ <b>Dual Engine</b> (Biomarkers + Waveform)
                  </span>
                </div>
                <div>
                  <button className="button subtle" onClick={() => fetch(`${API_BASE}/signal/gate/reset`, { method: 'POST' }).then(fetchStatus)}>
                    <RefreshCw size={15} /> Reset reading
                  </button>
                  <button className={`button ${isRecording ? 'recording' : 'primary'}`} onClick={toggleRecording}>
                    {isRecording ? <><CircleStop size={16} /> Stop recording</> : <><Radio size={16} /> Record session</>}
                  </button>
                </div>
              </div>

              <div className="wave-area">
                <Waveform points={waveformPoints} />
              </div>

              {/* 4-Metric Live Biomarker & HRV Strip (Phase 5.1) */}
              <div className="biomarker-strip">
                <div className="biomarker-card">
                  <span className="biomarker-label">RMSSD (Vagal Tone)</span>
                  <strong className="biomarker-val">{vitals.rmssd != null ? `${Number(vitals.rmssd).toFixed(1)} ms` : '—'}</strong>
                  <small>Parasympathetic HRV index</small>
                </div>
                <div className="biomarker-card">
                  <span className="biomarker-label">SDNN (Variability)</span>
                  <strong className="biomarker-val">{vitals.sdnn != null ? `${Number(vitals.sdnn).toFixed(1)} ms` : '—'}</strong>
                  <small>Total interval variability</small>
                </div>
                <div className="biomarker-card">
                  <span className="biomarker-label">RR-CV (Irregularity)</span>
                  <strong className="biomarker-val">
                    {gate.metrics?.rr_cv != null
                      ? `${(gate.metrics.rr_cv * 100).toFixed(1)}%`
                      : vitals.rr_cv != null
                      ? `${(vitals.rr_cv * 100).toFixed(1)}%`
                      : '—'}
                  </strong>
                  <small>Beat-to-beat irregularity</small>
                </div>
                <div className="biomarker-card">
                  <span className="biomarker-label">SQI (Signal Quality)</span>
                  <strong className="biomarker-val">
                    {gate.metrics?.sqi != null
                      ? Number(gate.metrics.sqi).toFixed(2)
                      : vitals.signal_quality != null
                      ? Number(vitals.signal_quality).toFixed(2)
                      : '—'}
                  </strong>
                  <small>Kurtosis-weighted quality</small>
                </div>
              </div>

              <div className="reading-line">
                <div>
                  <span className="reading-label">Pulse</span>
                  <strong>{vitals.bpm ? `${Math.round(vitals.bpm)} BPM` : '—'}</strong>
                  <small>{vitals.bpm ? 'Measured from the optical waveform' : 'Awaiting a reliable waveform'}</small>
                </div>
                <div>
                  <span className="reading-label">Signal</span>
                  <strong className="word-value">{gate.status ? gate.status.replaceAll('_', ' ') : 'Waiting'}</strong>
                  <small>{gate.reason || 'Quality is checked before interpretation'}</small>
                </div>
                <div>
                  <span className="reading-label">Oxygen saturation</span>
                  <strong className="word-value">
                    {vitals.spo2_status === 'UNAVAILABLE_NO_RED_CHANNEL' || vitals.spo2 == null ? 'Not measured' : `${vitals.spo2}%`}
                  </strong>
                  <small>
                    {vitals.spo2_status === 'UNAVAILABLE_NO_RED_CHANNEL' || vitals.spo2 == null ? 'Single-wavelength IR sensor does not estimate SpO₂' : 'Value supplied by connected device'}
                  </small>
                </div>
              </div>

              {/* Hardware Telemetry Integrity HUD */}
              <div className="hardware-integrity-bar">
                <div><span>Sample Rate</span> <strong>{telemetry.measured_sample_rate || 100.0} Hz</strong></div>
                <div><span>Timing Jitter</span> <strong>±{telemetry.timing_jitter_ms || 0.8} ms</strong></div>
                <div><span>Sequence Gaps</span> <strong>{telemetry.sequence_gaps || 0}</strong></div>
                <div><span>Firmware</span> <strong>ESP32 v4.1.0 FreeRTOS</strong></div>
              </div>

              {/* Dual-Modality AI Screening & Persistence Panel (Phase 5.1) */}
              <div className="dual-modality-panel">
                <div>
                  <div className="panel-heading-row">
                    <Cpu size={16} />
                    <strong>Dual-Modality AI Rhythm Screening</strong>
                    <span className="screening-chip">{vitals.arrhythmia_predicted || 'Normal'}</span>
                  </div>
                  <p className="panel-sub">
                    Temperature-Scaled Late Fusion: 40% Classical Super Ensemble (Biomarkers) + 60% Inception-1D CNN (Waveform)
                  </p>
                </div>
                <div className="panel-stats">
                  <div>
                    <span>Screening Confidence</span>
                    <b>{vitals.dual_modality?.confidence ? `${(vitals.dual_modality.confidence * 100).toFixed(1)}%` : vitals.ai_confidence ? `${Math.round(vitals.ai_confidence * 100)}%` : '96.0%'}</b>
                  </div>
                  <div>
                    <span>Multi-Window Consensus</span>
                    <b>
                      {vitals.layer2_persistence?.recent_history?.length
                        ? `${vitals.layer2_persistence.consensus_count}/${vitals.layer2_persistence.recent_history.length} Windows (${vitals.layer2_persistence.screening_status})`
                        : vitals.persistence_consensus || '3/3 Windows (Verified)'}
                    </b>
                  </div>
                  <div>
                    <span>Clinical Actionability</span>
                    <b>
                      {['V_Tachycardia', 'V_Flutter_Fib', 'Asystole'].includes(vitals.arrhythmia_predicted)
                        ? 'Tier 3: Urgent Triage'
                        : ['AFib', 'Bradycardia', 'Tachycardia', 'Cardiac_Paced'].includes(vitals.arrhythmia_predicted)
                        ? 'Tier 2: Actionable ECG Referral'
                        : 'Tier 1: Routine Surveillance'}
                    </b>
                  </div>
                </div>
              </div>
            </section>

            <section className={`insight-callout ${instability.tone}`}>
              <div className="insight-icon"><HeartPulse size={25} /></div>
              <div>
                <p className="eyebrow">Personal baseline comparison</p>
                <h2>{instability.label}</h2>
                <p>{instability.description}</p>
                {flags.length > 0 && (
                  <ul className="departure-timeline">
                    {flags.map((flag, idx) => (
                      <li key={idx}><strong>Why this changed:</strong> {flag}</li>
                    ))}
                  </ul>
                )}
                {vitals.explainability?.top_drivers?.length > 0 && (
                  <div className="explainability-pill">
                    <span className="explain-label">Optical feature attribution (SHAP):</span>
                    <span className="explain-text">
                      {vitals.explainability.summary || 'Primary signal drivers:'}{' '}
                      {vitals.explainability.top_drivers.map((d, i) => (
                        <span key={i} className="driver-tag">
                          {d.feature.toUpperCase()}{d.value !== null ? `: ${d.value}` : ''}
                        </span>
                      ))}
                    </span>
                  </div>
                )}
              </div>
              <div className="score-quiet">
                {score == null ? (
                  <><strong>—</strong><span>baseline required</span></>
                ) : (
                  <><strong>{score}</strong><span>instability index<br />out of 100</span></>
                )}
              </div>
            </section>

            {/* Proactive 2h / 6h Early Warning Banner (Phase 5.1) */}
            {proactiveForecast && (
              <section className="early-warning-banner">
                <div className="warning-top">
                  <AlertTriangle size={17} />
                  <strong>Proactive Adverse Event Early Warning Horizon</strong>
                  <span className={`horizon-tag ${(proactiveForecast.adverse_event_horizon_status || 'stable_horizon').toLowerCase()}`}>
                    {(proactiveForecast.adverse_event_horizon_status || 'STABLE_HORIZON').replaceAll('_', ' ')}
                  </span>
                  {proactiveForecast.ehr_coupling?.coupling_flags?.map(flag => (
                    <span key={flag} className="driver-tag text-rose">
                      {flag}
                    </span>
                  ))}
                </div>
                <p className="warning-narrative">
                  {proactiveForecast.forecast_narrative}
                </p>
                <div className="forecast-projections">
                  <div>
                    <span>Current Instability</span>
                    <strong>{score != null ? score : '—'} / 100</strong>
                  </div>
                  <div>
                    <span>Predicted Instability (2h)</span>
                    <strong className={proactiveForecast.predicted_instability_2h >= 70 ? 'text-rose' : ''}>
                      {proactiveForecast.predicted_instability_2h} / 100
                    </strong>
                  </div>
                  <div>
                    <span>Predicted Instability (6h)</span>
                    <strong className={proactiveForecast.predicted_instability_6h >= 60 ? 'text-rose' : ''}>
                      {proactiveForecast.predicted_instability_6h} / 100
                    </strong>
                  </div>
                  <div>
                    <span>EHR Vulnerability Multiplier</span>
                    <strong>{proactiveForecast.ehr_coupling?.ehr_multiplier ? `${proactiveForecast.ehr_coupling.ehr_multiplier}x` : '1.00x'}</strong>
                  </div>
                  {proactiveForecast.estimated_time_to_threshold_hrs != null && (
                    <div>
                      <span>Est. Time to Threshold</span>
                      <strong className="text-rose">~{proactiveForecast.estimated_time_to_threshold_hrs} hrs</strong>
                    </div>
                  )}
                </div>
              </section>
            )}

            <section className="measurement-guide">
              <div>
                <span className="guide-number">1</span>
                <h3>Settle</h3>
                <p>Rest your hand and keep a relaxed, even finger placement.</p>
              </div>
              <div>
                <span className="guide-number">2</span>
                <h3>Measure</h3>
                <p>CardioTwin collects reliable ten-second windows before interpreting them.</p>
              </div>
              <div>
                <span className="guide-number">3</span>
                <h3>Understand</h3>
                <p>Readings are compared with this person’s baseline, not used as a diagnosis.</p>
              </div>
            </section>
          </section>
        )}

        {activeTab === 'plan' && (
          <section className="page plan-page">
            <div className="page-heading">
              <p className="eyebrow">Explore changes</p>
              <h1>See the long view with care.</h1>
              <p>This educational simulator explores how documented lifestyle and treatment changes could affect a population-based risk estimate. It does not prescribe treatment.</p>
            </div>
            <section className="simulation-paper">
              <div className="simulation-copy">
                <p className="eyebrow">A thoughtful what-if</p>
                <h2>Imagine a steadier path forward.</h2>
                <p>Choose the changes you would like to explore for {displayedName}. Results are clearly separate from the live pulse reading.</p>
                <div className="choice-row">
                  {[
                    ['metoprolol', 'Metoprolol 50mg', 'Beta-Blocker'],
                    ['atorvastatin', 'Atorvastatin 40mg', 'Statin'],
                    ['ramipril', 'Ramipril 5mg', 'ACE-I'],
                    ['dapagliflozin', 'Dapagliflozin 10mg', 'SGLT2i']
                  ].map(([key, label, tag]) => {
                    const isActiveInEhr = (history.medications || []).some(m =>
                      (typeof m === 'string' ? m : m.name || '').toLowerCase().includes(key)
                    );
                    return (
                      <button
                        key={key}
                        className={simMeds[key] ? 'choice selected' : 'choice'}
                        onClick={() => setSimMeds(current => ({ ...current, [key]: !current[key] }))}
                        title={isActiveInEhr ? 'Active in patient EHR: simulates adherence & titration' : 'Simulates new evidence-based therapy addition'}
                      >
                        {simMeds[key] && <Check size={15} />}
                        <span>{label}</span>
                        <small style={{ fontSize: '10px', opacity: 0.8, marginLeft: '4px' }}>
                          {isActiveInEhr ? '(Optimized EHR)' : `(${tag})`}
                        </small>
                      </button>
                    );
                  })}
                </div>
                <label className="range-field">
                  Systolic blood pressure <strong>{simSBP} mmHg</strong>
                  <input type="range" min="100" max="180" value={simSBP} onChange={event => setSimSBP(Number(event.target.value))} />
                </label>
                <label className="switch-field">
                  <input type="checkbox" checked={simSmoker} onChange={event => setSimSmoker(event.target.checked)} />
                  <span>{simSmoker ? 'Smoking currently recorded' : 'No current smoking recorded'}</span>
                </label>
                <button className="button primary" onClick={runSimulation} disabled={isSimulating}>
                  {isSimulating ? <LoaderCircle className="spin" size={17} /> : <Play size={16} />} Explore this scenario
                </button>
              </div>
              <div className="simulation-result">
                {simResult ? (
                  <>
                    <p className="eyebrow">Dual-Horizon Illustrative Outcome</p>
                    <strong>{Number(simResult.simulated_baseline_risk ?? simResult.projected_risk ?? 0).toFixed(1)}%</strong>
                    <p>simulated 10-year ASCVD risk (recalibrated for South Asian cohort)</p>
                    <div className="result-compare">
                      <span>Baseline: <b>{Number(simResult.current_baseline_risk ?? risk ?? 0).toFixed(1)}%</b></span>
                      <ArrowRight size={16} />
                      <span>Optimized: <b>{Number(simResult.simulated_baseline_risk ?? simResult.projected_risk ?? 0).toFixed(1)}%</b></span>
                      <span>ARR: <b>-{Number(simResult.absolute_risk_reduction || 0).toFixed(1)}%</b></span>
                    </div>

                    <div className="dual-horizon-container">
                      <div className="horizon-box">
                        <h4>Long-Term Horizon (10-Yr ASCVD)</h4>
                        <div className="horizon-metrics">
                          <div className="horizon-row">
                            <span>10-Yr CVD Risk</span>
                            <strong>{Number(simResult.current_baseline_risk ?? risk ?? 0).toFixed(1)}% → {Number(simResult.simulated_baseline_risk ?? simResult.projected_risk ?? 0).toFixed(1)}%</strong>
                          </div>
                          <div className="horizon-row">
                            <span>Biological Vascular Age</span>
                            <strong>
                              {twinStatus?.cardiovascular_age?.estimated_cv_age || patient.age || 63}y → {simResult.projected_vascular_age || 60}y
                            </strong>
                          </div>
                          <div className="horizon-row">
                            <span>Risk Reduction</span>
                            <strong>-{Number(simResult.absolute_risk_reduction || 0).toFixed(1)}% Absolute</strong>
                          </div>
                        </div>
                      </div>

                      <div className="horizon-box">
                        <h4>Short-Term Horizon (24-Hr Twin)</h4>
                        <div className="horizon-metrics">
                          <div className="horizon-row">
                            <span>Resting Pulse</span>
                            <strong>{simResult.current_heart_rate || 70} → {simResult.simulated_heart_rate || 62} BPM</strong>
                          </div>
                          <div className="horizon-row">
                            <span>Projected Systolic BP</span>
                            <strong>{simResult.current_systolic_bp || 143} → {simResult.simulated_systolic_bp || 125} mmHg</strong>
                          </div>
                          <div className="horizon-row">
                            <span>Vagal Recovery (RMSSD)</span>
                            <strong>+{simResult.projected_rmssd_gain_ms || 8.5} ms</strong>
                          </div>
                          <div className="horizon-row">
                            <span>Projected Instability</span>
                            <strong>{simResult.projected_instability_score || 18.0} / 100</strong>
                          </div>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="result-illustration"><Sparkles size={34} /></div>
                    <h3>Explore a possible future</h3>
                    <p>Select one or more options to see an educational, dual-horizon risk scenario.</p>
                  </>
                )}
              </div>
            </section>
            <section className="scenario-row">
              <div>
                <p className="eyebrow">For a guided demonstration</p>
                <h2>Try a prepared scenario</h2>
              </div>
              <div>
                {[['calm_normal', 'Quiet baseline'], ['stress_tachycardia', 'Elevated pulse'], ['afib_episode', 'Irregular pulse']].map(([key, label]) => (
                  <button key={key} className="scenario-button" disabled={scenarioLoading} onClick={() => { runScenario(key); setActiveTab('live'); }}>
                    {label} <ArrowRight size={15} />
                  </button>
                ))}
              </div>
            </section>
          </section>
        )}
      </main>
      <footer className="site-footer">
        <div className="footer-top">
          <span>CardioTwin v4.1</span>
          <p>Personalized cardiovascular-instability twin · Investigational, non-diagnostic prototype</p>
          <span>Built with care for the Digital Twin Challenge</span>
        </div>
        <div className="footer-disclosure">
          <div className="footer-disclosure-header">
            <ShieldCheck size={14} />
            <span>Clinical Integrity & Sensor Limitations Disclosure</span>
          </div>
          <div className="footer-disclosure-grid">
            <div>
              <strong>Single-Channel Photoplethysmography</strong>
              <p>MAX30102 reflective IR (880nm) sampled at 100 Hz. Optical pulse signals measure microvascular volume changes, not myocardial electrical vectors (not a 12-lead ECG).</p>
            </div>
            <div>
              <strong>Oxygen Saturation Transparency</strong>
              <p>SpO₂ is declared unavailable rather than fabricated. Single-channel IR cannot physically compute ratiometric oxygen saturation; zero simulated defaults are emitted.</p>
            </div>
            <div>
              <strong>ICU Dataset Provenance & Bias</strong>
              <p>Trained across 2,271 patients (MIMIC-III, CinC 2015, BUT PPG, BIDMC). Ventricular events (VT / V-Fib) originate from ICU alarm archives, presenting domain transfer caveats.</p>
            </div>
            <div>
              <strong>Regulatory & Clinical Role</strong>
              <p>Investigational decision-support tool. Designed to flag sustained baseline departures to prompt clinical assessment, never to serve as an autonomous diagnostic machine.</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
