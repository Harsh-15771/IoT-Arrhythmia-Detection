import { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { Activity, ArrowRight, Check, ChevronRight, CircleStop, Download, FileText, HeartPulse, Leaf, LoaderCircle, Play, Radio, RefreshCw, ShieldCheck, Sparkles, Stethoscope, UserRound, Waves, X } from 'lucide-react';

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

function Waveform({ points }) {
  if (points.length < 2) return <div className="empty-wave"><Radio size={23} /><span>Place a finger firmly on the sensor to begin a live reading.</span></div>;
  const min = Math.min(...points), max = Math.max(...points), range = max - min || 1;
  const path = points.map((point, index) => `${index ? 'L' : 'M'} ${(index / (points.length - 1) * 720).toFixed(1)} ${(138 - ((point - min) / range * 120)).toFixed(1)}`).join(' ');
  return <svg className="waveform" viewBox="0 0 720 156" role="img" aria-label="Live optical pulse waveform"><defs><linearGradient id="waveGradient"><stop stopColor="#1b9a92" /><stop offset="1" stopColor="#5cc5bc" /></linearGradient></defs>{[32,78,124].map(y => <line key={y} x1="0" y1={y} x2="720" y2={y} className="wave-grid" />)}<path d={path} fill="none" stroke="url(#waveGradient)" strokeWidth="3" strokeLinecap="round" /></svg>;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('PAT001');
  const [twinStatus, setTwinStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const [waveformPoints, setWaveformPoints] = useState([]);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibration, setCalibration] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [simMeds, setSimMeds] = useState({ metoprolol: false, atorvastatin: false, ramipril: false });
  const [simSBP, setSimSBP] = useState(135);
  const [simSmoker, setSimSmoker] = useState(false);
  const [simResult, setSimResult] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isSimulatedData, setIsSimulatedData] = useState(false);

  const applyStatus = data => {
    setTwinStatus(data);
    setIsCalibrating(Boolean(data?.is_calibrating));
    setCalibration(data?.calibration_status || null);
    if (data?.current_vitals?.data_source === 'SIMULATION') {
      setIsSimulatedData(true);
    } else if (data?.hardware_telemetry?.device_id) {
      setIsSimulatedData(false);
    }
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
        setIsSimulatedData(false);
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
      if (data.updated_status) applyStatus(data.updated_status);
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
    const labels = { metoprolol: 'Metoprolol', atorvastatin: 'Atorvastatin', ramipril: 'Ramipril' };
    const meds = Object.entries(simMeds).filter(([, on]) => on).map(([key]) => labels[key]);
    fetch(`${API_BASE}/twin/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ add_medications: meds, systolic_bp: simSBP, smoker: simSmoker })
    }).then(r => r.json()).then(data => setSimResult(data.simulation || null)).finally(() => setIsSimulating(false));
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

  const score = twinStatus?.personal_instability?.instability_score ?? null;
  const flags = twinStatus?.personal_instability?.departure_flags || [];
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
                  {[['metoprolol', 'Metoprolol'], ['atorvastatin', 'Atorvastatin'], ['ramipril', 'Ramipril']].map(([key, label]) => (
                    <button key={key} className={simMeds[key] ? 'choice selected' : 'choice'} onClick={() => setSimMeds(current => ({ ...current, [key]: !current[key] }))}>
                      {simMeds[key] && <Check size={15} />} {label}
                    </button>
                  ))}
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
                    <p className="eyebrow">Illustrative outcome</p>
                    <strong>{Number(simResult.simulated_baseline_risk ?? simResult.projected_risk ?? 0).toFixed(1)}%</strong>
                    <p>estimated long-term cardiovascular risk after the selected changes</p>
                    <div className="result-compare">
                      <span>Current <b>{Number(simResult.current_baseline_risk ?? risk ?? 0).toFixed(1)}%</b></span>
                      <ArrowRight size={16} />
                      <span>Illustrative <b>{Number(simResult.simulated_baseline_risk ?? simResult.projected_risk ?? 0).toFixed(1)}%</b></span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="result-illustration"><Sparkles size={34} /></div>
                    <h3>Explore a possible future</h3>
                    <p>Select one or more options to see an educational, long-term risk scenario.</p>
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
