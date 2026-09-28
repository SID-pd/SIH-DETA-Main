/**
 * RailPulse: Real-Time Dynamic Railway ETA & Operational Intelligence
 * Pure System Logic & Working Methodology Controller
 */

// ==========================================================================
// 1. Pipeline Stages Detail Model (Screenshot 1 Method)
// ==========================================================================
const pipelineDetails = {
  data_source: {
    title: 'Stage 1: Live Railway Telemetry Streams',
    badge: 'TELEMETRY INGESTION TIER',
    input: 'Locomotive RTIS GPS (1Hz pings), electronic interlocking block aspect feeds, station arrival/departure punch logs, and halt-level ultrasonic sensors.',
    method: 'Asynchronous streaming ingestion via Kafka and WebSocket event loops with timestamp verification and duplicate rejection.',
    output: 'Raw telemetry event stream tagged with locomotive ID, speed, heading, and GPS precision index.',
    failure: 'Prevents single-point-of-failure reliance on delayed station manual register logs.'
  },
  processing: {
    title: 'Stage 2: Ingestion & Map-Matching Pipeline',
    badge: 'SPATIAL PROCESSING',
    input: 'Raw noisy GPS coordinates and live speed vectors from locomotives.',
    method: 'Kalman filtering removes GPS drift; PostGIS spatial ST_DWithin and ST_ClosestPoint map-match coordinates to exact railway track vectors.',
    output: 'Normalized track location (Track Line ID, Section ID, KM Post, Direction of Travel).',
    failure: 'Eliminates false off-track deviations and bridges topological ambiguities at complex parallel track junctions.'
  },
  storage: {
    title: 'Stage 3: RailPulse Relational Database (PostgreSQL + PostGIS)',
    badge: 'MASTER SOURCE OF TRUTH',
    input: 'Track geometries, master timetable schedules, rake turnarounds, crew rosters, and historical journey records.',
    method: 'Acid-compliant relational storage with spatial indexing (GIST on track geometries) strictly isolated from public queries.',
    output: 'Permanent railway network graph, schedule baseline, and training warehouse for machine learning models.',
    failure: 'Prevents database deadlocks and crashes by completely shielding master operational records from public passenger traffic.'
  },
  layer1: {
    title: 'Stage 4A: Layer 1 Train & Halt Behaviour Model',
    badge: 'EMPIRICAL STATISTICAL DNA',
    input: 'Historical logs across 12+ months of journeys, train category (Rajdhani, Mail, Express, Freight), and station categories.',
    method: 'Computes dynamic behavioural weight vectors: W_dwell = f(train, station, day_of_week, peak_hour) and recovery capacity W_recov.',
    output: 'Station-specific dwell weight (e.g. W_dwell = 1.35x) and sectional recovery capability.',
    failure: 'Prevents applying generic dwell assumptions to high-density terminal hubs with massive passenger boarding surges.'
  },
  layer3: {
    title: 'Stage 4B: Layer 3 Dynamic ML Real-Time ETA Model',
    badge: 'DYNAMIC TIME-SERIES INFERENCE',
    input: 'Live RTIS coordinates, instantaneous velocity, Layer 1 weights, and hyper-local halt weather matrices (fog index, rainfall).',
    method: 'Continuous regression with Gradient Boosted Trees (LightGBM) & sequence models (PyTorch) to infer arrival probability distributions.',
    output: 'Probabilistic forecast with confidence interval: PRYJ 23:48 ± 2.1 min (Confidence: 92%).',
    failure: 'Replaces static timetable extrapolation with real-time awareness of en-route deceleration and micro-climatic bottlenecks.'
  },
  layer2: {
    title: 'Stage 4C: Layer 2 Operational Constraint & Physics Verifier',
    badge: 'PHYSICAL RAILWAY SAFETY VERIFIER',
    input: 'Layer 3 predicted ETAs, current block section occupancies, trailing rakes, and platform track availability.',
    method: 'Rulebook verification: enforces headway safety minimums (Δt ≥ 3 min), braking deceleration limits, and platform conflict checks.',
    output: 'Verified Feasible ETA or alternative precedence recommendation (e.g. hold freight train on loop line).',
    failure: 'Prevents safety-critical prediction failures that violate signalling block separation or platform track conflicts.'
  },
  redis_tier: {
    title: 'Stage 5: Redis High-Speed In-Memory Serving Tier',
    badge: 'SUB-1.5MS MEMORY CACHE',
    input: 'Verified ETAs and active train state hashes emitted by Layer 2.',
    method: 'In-memory key-value caching (train:{id}:eta) and Sorted Sets for station arrival boards (station:{id}:arrivals).',
    output: 'Ultra-low latency data serving capable of handling 100,000+ queries per second with < 1.5ms response time.',
    failure: 'Prevents public frontend crashes during peak travel periods and holiday booking surges.'
  },
  api_interface: {
    title: 'Stage 6A: FastAPI High-Throughput REST Gateway',
    badge: 'ASYNC PUBLIC APIS',
    input: 'HTTP GET requests from IRCTC mobile apps, NTES, and third-party travel aggregator applications.',
    method: 'Asynchronous non-blocking Python ASGI gateway querying Redis directly without touching disk storage.',
    output: 'Serialized JSON response with next station ETA, delay in minutes, and prediction confidence.',
    failure: 'Ensures zero database connection pool exhaustion under nationwide concurrency.'
  },
  ws_interface: {
    title: 'Stage 6B: WebSocket Live Streaming Server',
    badge: 'FULL-DUPLEX REAL-TIME PUSH',
    input: 'Persistent socket connections from Station Platform Display Systems (PIDS) and Section Controller consoles.',
    method: 'Redis Pub/Sub channel multiplexing broadcasting train coordinate shifts and revised ETAs in under 50ms.',
    output: 'Live platform display countdown and real-time controller track occupancy visualizer.',
    failure: 'Eliminates client-side polling loops that waste network bandwidth across thousands of railway stations.'
  },
  output_results: {
    title: 'Stage 7: Verified Feasible ETA & Operational Guidance',
    badge: 'ACTIONABLE OPERATIONAL VALUE',
    input: 'Final verified arrival times, platform track allocations, and downstream recovery margins.',
    method: 'Multi-channel dispatch: passenger notifications, station display updates, and crew roster management feeds.',
    output: 'Accurate passenger information, conflict-free platform allocations, and timely pit-line maintenance turnaround scheduling.',
    failure: 'Prevents platform overcrowding, rake cleaning backlogs, crew duty-hour violations, and multimodal commuter delays.'
  }
};

function selectPipelineStage(stageKey) {
  const data = pipelineDetails[stageKey];
  if (!data) return;

  document.getElementById('stage-detail-title').textContent = data.title;
  document.getElementById('stage-detail-badge').textContent = data.badge;
  document.getElementById('stage-detail-input').textContent = data.input;
  document.getElementById('stage-detail-method').textContent = data.method;
  document.getElementById('stage-detail-output').textContent = data.output;
  document.getElementById('stage-detail-failure').textContent = data.failure;

  const card = document.getElementById('pipeline-explainer');
  if (card) {
    card.style.borderColor = '#0f172a';
    card.style.boxShadow = '0 0 16px rgba(15, 23, 42, 0.12)';
    setTimeout(() => {
      card.style.boxShadow = 'none';
    }, 400);
  }
}

// ==========================================================================
// 2. Architecture Component Detail Model (Screenshot 2 Method)
// ==========================================================================
const archDetails = {
  pwa: {
    title: 'Client Tier: Passenger Mobile Apps (IRCTC / NTES)',
    badge: 'HIGH-CONCURRENCY CONSUMERS',
    role: 'Provides real-time train status and platform arrival forecasts to millions of daily passengers.',
    latency: 'Sub-2ms responses served directly from Redis in-memory cache.',
    keys: 'Queries `GET /api/v1/trains/{train_id}/eta` backed by `train:{id}:eta` in RAM.',
    inval: 'Cache automatically pushes updates over WebSockets when delay changes by ≥ 1 minute.'
  },
  pids: {
    title: 'Display Tier: Station Platform Information Displays (PIDS)',
    badge: 'STATION DISPLAY SYSTEMS',
    role: 'Powers station hall and platform LED/LCD displays showing expected arrival times, platform track assignments, and dwell times.',
    latency: 'Sub-second real-time sync with section interlocking.',
    keys: 'Reads from Redis Sorted Set `station:{station_code}:arrivals`.',
    inval: 'Immediate update broadcast via Redis Pub/Sub when Layer 2 verifies platform routing.'
  },
  dashboard: {
    title: 'Dispatch Tier: Section Controller Cockpit (Web)',
    badge: 'OPERATIONAL CONTROL CONSOLE',
    role: 'Empowers divisional dispatchers to monitor section occupancies, receive automated precedence advice, and simulate What-If incident injections.',
    latency: 'Sub-50ms WebSocket telemetry stream with PostGIS track map.',
    keys: 'Full access to section graph state, temporary speed restrictions, and conflict resolution logs.',
    inval: 'Bidirectional control: dispatchers can manually override model advice or inject maintenance blocks.'
  },
  comms: {
    title: 'Streaming Tier: Real-Time WebSockets & Kafka Pub/Sub',
    badge: 'DISTRIBUTED MESSAGE BUS',
    role: 'Transport layer moving high-frequency GPS coordinate pings and signal aspect state transitions across microservices.',
    latency: 'End-to-end event propagation in under 50 milliseconds.',
    keys: 'Kafka topics partitioned by Railway Zone (NR, NCR, ECR, ER).',
    inval: 'Persistent connection pooling with automatic backpressure management.'
  },
  ingestion: {
    title: 'Ingestion Engine: Telemetry & Spatial Validator',
    badge: 'STREAM PRE-PROCESSING',
    role: 'Ingests raw locomotive RTIS data, performs Kalman noise filtering, and verifies spatial coordinate bounding boxes.',
    latency: 'Processes 15,000 telemetry events per second per cluster node.',
    keys: 'Emits sanitized location events to PostGIS and the Layer 3 inference pipeline.',
    inval: 'Rejects invalid GPS anomalies (e.g. teleportation glitches, reverse track errors).'
  },
  decision: {
    title: 'Decision Node: Anomaly / Delay Variance Detection',
    badge: 'DYNAMIC GRAPH MODE BRANCH',
    role: 'Evaluates whether running time deviates from expected baseline: Δ = |T_live - T_predicted|.',
    latency: 'Instantaneous in-memory comparison (sub-100 microseconds).',
    keys: 'If Δ < threshold (3 min) ➔ Maintain Mode 1 Aggregate Section Flow. If Δ ≥ threshold ➔ Trigger Mode 2 Detailed Halt Traversal.',
    inval: 'Dynamic threshold adjusting automatically for train category and weather season.'
  },
  redis: {
    title: 'Storage Tier: Redis High-Speed In-Memory Cache',
    badge: 'SUB-1.5MS MEMORY LAYER',
    role: 'Shields PostgreSQL by serving 100% of public mobile queries and station board requests directly from RAM.',
    latency: '1.1ms average read latency across 100,000 concurrent connections.',
    keys: 'Hashes for train ETA, Sorted Sets for station arrival boards, Geohashes for live coordinates.',
    inval: 'Keys expire automatically via TTL (120s - 300s) with active refresh from Layer 2.'
  },
  api: {
    title: 'API Gateway: FastAPI / Python Asynchronous Backend',
    badge: 'CORE API SERVICES',
    role: 'Manages request authentication, query routing, rate limiting, and cache serialization.',
    latency: 'Sub-2ms HTTP round-trip when serving from Redis cache.',
    keys: 'Exposes RESTful `/api/v1/trains/{id}/eta` and WebSocket `/ws/live-stream`.',
    inval: 'Stateless containerized services scaling horizontally with Kubernetes.'
  },
  ml_engine: {
    title: 'Intelligence Tier: Layer 3 Dynamic ML ETA Engine',
    badge: 'GRADIENT BOOSTED TIME-SERIES',
    role: 'Computes probabilistic arrival times based on live speed curves, halt-level micro-weather, and Layer 1 weights.',
    latency: 'Sub-15ms model inference per train section.',
    keys: 'Trained LightGBM regressor and PyTorch sequence model checkpoints.',
    inval: 'Periodically retrained offline using historical trip logs from the Analytics Lake.'
  },
  postgres: {
    title: 'Storage Tier: Master Database (PostgreSQL + PostGIS)',
    badge: 'AUTHORITATIVE SOURCE OF TRUTH',
    role: 'Persistent storage for track graph geometries, master schedules, turnaround rules, and audit logs.',
    latency: 'Private access only: batch queries and operational mutations.',
    keys: 'Tables: `network_nodes`, `network_edges`, `train_schedules`, `historical_runs`.',
    inval: 'Master record updated only on timetable revisions, track engineering changes, or journey completion.'
  },
  lake: {
    title: 'Analytics Tier: Historical Run Logs & Data Lake',
    badge: 'OFFLINE ML TRAINING WAREHOUSE',
    role: 'Stores years of historical locomotive runs, sensor telemetry, and incident records for deep analytics and model retraining.',
    latency: 'Columnar storage (Parquet / Snowflake) optimized for large batch aggregations.',
    keys: 'Historical dwell archives, weather sensor time-series, and dispatcher override logs.',
    inval: 'Continuous daily ETL pipeline appending completed journey records.'
  },
  dwell_proc: {
    title: 'Analytics Engine: Layer 1 Behaviour & Dwell Extraction',
    badge: 'STATISTICAL ARCHIVE PIPELINE',
    role: 'Extracts empirical dwell distributions and sectional recovery capabilities for every train category across day-of-week patterns.',
    latency: 'Batch computation updating Layer 1 weight lookup tables nightly.',
    keys: 'Generates weight lookup tables consumed by Layer 3 during real-time inference.',
    inval: 'Weights adapt continuously to reflect seasonal passenger rush and track maintenance seasons.'
  }
};

function selectArchComponent(compKey) {
  const data = archDetails[compKey];
  if (!data) return;

  document.getElementById('arch-detail-title').textContent = data.title;
  document.getElementById('arch-detail-badge').textContent = data.badge;
  document.getElementById('arch-detail-role').textContent = data.role;
  document.getElementById('arch-detail-latency').textContent = data.latency;
  document.getElementById('arch-detail-keys').textContent = data.keys;
  document.getElementById('arch-detail-inval').textContent = data.inval;

  const card = document.getElementById('arch-explainer');
  if (card) {
    card.style.borderColor = '#0f172a';
    card.style.boxShadow = '0 0 16px rgba(15, 23, 42, 0.12)';
    setTimeout(() => {
      card.style.boxShadow = 'none';
    }, 400);
  }
}

// ==========================================================================
// 3. Corridor Dual-Mode Traversal Logic & Route Visualizer
// ==========================================================================
const haltData = {
  ROOMA: {
    name: 'Halt 1: Rooma (ROMA)',
    status: 'Nominal Clear Flow',
    speed: '110 km/h (Normal Running)',
    weather: 'Clear Visibility (> 2500m) • Track Adhesion: 0.38',
    logic: 'No speed restrictions. Train runs at maximum permissible sectional speed (MPS). Layer 1 calculates zero dwell penalty.'
  },
  BINDKI: {
    name: 'Halt 2: Bindki Road (BKO)',
    status: 'ANOMALY DETECTED: DENSE FOG',
    speed: '30 km/h Imposed (TSR Active)',
    weather: 'Atmospheric Visibility: 70m • Micro-Valley Fog Alert',
    logic: 'Micro-valley geography traps dense fog across KM 1020-1032. Detailed Traversal isolates this exact 12 km stretch rather than penalizing the entire 194 km section, saving downstream dispatchers from false timetable panic.'
  },
  FATEHPUR: {
    name: 'Halt 3: Fatehpur (FTP)',
    status: 'Sectional Speed Recovery',
    speed: '90 km/h (Accelerating to 110)',
    weather: 'Mist Dissipating • Visibility: 900m',
    logic: 'Exiting fog belt. Layer 1 sectional recovery buffer calculates 3.0 minutes of recovery before Sirathu, allowing Prayagraj arrival to be revised from +17m down to +14m.'
  }
};

function switchCorridorMode(mode) {
  const btnNormal = document.getElementById('btn-mode-normal');
  const btnDetailed = document.getElementById('btn-mode-detailed');
  const haltsLayer = document.getElementById('halts-layer');
  const statusBar = document.getElementById('corridor-status-bar');

  if (mode === 'NORMAL') {
    btnNormal.classList.add('active');
    btnDetailed.classList.remove('active');
    haltsLayer.style.opacity = '0.2';
    haltsLayer.style.pointerEvents = 'none';
    statusBar.innerHTML = '<span>Mode 1 Active: <strong>Normal Section Mode</strong>. Section CNB ➔ PRYJ calculated as aggregate 194 km transit. Zero halt overhead.</span>';
  } else {
    btnDetailed.classList.add('active');
    btnNormal.classList.remove('active');
    haltsLayer.style.opacity = '1';
    haltsLayer.style.pointerEvents = 'auto';
    statusBar.innerHTML = '<span>Mode 2 Active: <strong>Detailed Halt Traversal</strong>. Anomaly at Bindki Road isolated to KM 1020-1032. Exploded halt scan active.</span>';
  }
}

function inspectHaltLogic(haltKey) {
  const data = haltData[haltKey];
  if (!data) return;

  const statusBar = document.getElementById('corridor-status-bar');
  statusBar.innerHTML = `<span><strong>${data.name}</strong> [${data.status}]: Speed: ${data.speed} • Weather: ${data.weather}. <em>${data.logic}</em></span>`;
}

// ==========================================================================
// 4. What-If Incident Simulation Methodology Controller
// ==========================================================================
const incidentScenarios = {
  FOG: {
    tag: 'SCENARIO: DENSE FOG (LEVEL 2)',
    speed: '30 km/h',
    trainX: 590,
    etaPRYJ: 'ETA 23:48 (+14m)',
    etaDDU: 'ETA 01:52 (+11m)',
    logs: [
      '[INGESTION] RTIS GPS received: Lat 26.0461, Lng 80.6128. Speed 88 km/h.',
      '[MONITOR] Halt 2 (Bindki Road) weather sensor alert: Visibility = 70m (Threshold < 150m).',
      '[GRAPH_ENGINE] Delta threshold breached. Section CNB-PRYJ exploded into Mode 2 (Detailed Halt Traversal).',
      '[LAYER_3_ML] Ingested localized halt matrix: Imposing 30 km/h TSR across KM 1020-1032.',
      '[LAYER_2_VERIFY] Track headway checked against Goods 3012. Minimum separation: 4.8 min (SAFE).',
      '[VERIFIED_ETA] PRYJ revised to 23:48 (+14m). Layer 1 calculates 3m recovery between Fatehpur & Sirathu.',
      '[REDIS_SYNC] Published updated hash `train:12301:eta` to Redis cluster in 1.14ms.'
    ],
    verdict: 'Operational Verdict: Feasible ETA computed. Goods rake 3012 held at Bindki Loop Line to prevent blocking Rajdhani express.'
  },
  MAINTENANCE: {
    tag: 'SCENARIO: UNSCHEDULED TRACK BLOCK LINE 1 (LEVEL 3)',
    speed: '15 km/h',
    trainX: 575,
    etaPRYJ: 'ETA 00:08 (+34m)',
    etaDDU: 'ETA 02:10 (+29m)',
    logs: [
      '[ADMIN_INJECTION] Emergency track maintenance block declared on Line 1 at KM 1040.',
      '[GRAPH_ENGINE] Line 1 edge disabled in PostGIS topology graph. Searching alternate paths.',
      '[LAYER_2_VERIFY] Precedence evaluation: Diverting Train 12301 via Bindki Road Loop Line 2.',
      '[LAYER_2_VERIFY] Turnout speed restriction imposed: 15 km/h over crossover point.',
      '[LAYER_3_ML] Inferred additional traversal delay: +20 minutes loop dwelling.',
      '[VERIFIED_ETA] PRYJ revised to 00:08 (+34m). Station master notified for platform reassignment.',
      '[REDIS_SYNC] Updated station arrival board `station:PRYJ:arrivals` in 1.22ms.'
    ],
    verdict: 'Operational Verdict: Rerouted via Loop Line 2. Avoided dead-stop cancellation. Platform 1 at PRYJ reallocated to Sangam Express.'
  },
  SIGNAL: {
    tag: 'SCENARIO: SIGNAL 408 INTERMITTENT CAUTION (LEVEL 1)',
    speed: '65 km/h',
    trainX: 520,
    etaPRYJ: 'ETA 23:38 (+4m)',
    etaDDU: 'ETA 01:41 (On Time)',
    logs: [
      '[TELEMETRY] Automatic Block Signal 408 aspect changed from Green to Double Yellow (Caution).',
      '[INGESTION] Preceding freight train slowing down in forward block section.',
      '[LAYER_3_ML] Predicted traversal slowdown: +4.0 minutes sectional loss.',
      '[LAYER_1_BUFFER] Layer 1 evaluates downstream recovery capacity: 5.5 minutes buffer available before PRYJ.',
      '[LAYER_2_VERIFY] Verified buffer absorption: Downstream arrival at DDU remains on-time.',
      '[REDIS_SYNC] Refreshed ETA in Redis key `train:12301:eta` in 0.98ms.'
    ],
    verdict: 'Operational Verdict: Minor caution slowdown absorbed by Layer 1 recovery buffer. Zero disruption to downstream train schedules.'
  },
  DISASTER: {
    tag: 'SCENARIO: LINE RUPTURE / EMERGENCY HALT (LEVEL 4)',
    speed: '0 km/h (HALTED)',
    trainX: 610,
    etaPRYJ: 'ETA INDETERMINATE (EMERGENCY)',
    etaDDU: 'ETA INDETERMINATE (EMERGENCY)',
    logs: [
      '[ALARM] Emergency brake application (EBA) tripped at KM 1028. Locomotive speed: 0 km/h.',
      '[CONTROL_ROOM] Section controller confirms rail fracture report. Track closed indefinitely.',
      '[LAYER_2_FAILSAFE] Safety Rule Enforced: Indeterminate ETA rule triggered.',
      '[SAFETY_POLICY] Suppressing speculative machine learning arrival calculations.',
      '[REDIS_SYNC] Updated status hash: `train:12301:eta` -> { status: "EMERGENCY_HALT", eta: "INDETERMINATE" } in 0.85ms.',
      '[PUBLIC_ALERT] Passenger mobile apps and station displays updated with verified hold advisory.'
    ],
    verdict: 'Operational Verdict: Failsafe triggered. Speculative ETAs suppressed to prevent passenger confusion. Emergency relief rake dispatched.'
  },
  NORMAL: {
    tag: 'SCENARIO: NOMINAL TIMETABLE FLOW',
    speed: '110 km/h',
    trainX: 430,
    etaPRYJ: 'ETA 23:34 (On Time)',
    etaDDU: 'ETA 01:41 (On Time)',
    logs: [
      '[RESET] Restoring nominal timetable baseline across New Delhi - Prayagraj corridor.',
      '[GRAPH_ENGINE] Re-engaging Mode 1 (Normal Section Mode). Aggregate section computation active.',
      '[LAYER_1_DNA] Train 12301 running strictly within Rajdhani scheduled dwell tolerance.',
      '[LAYER_2_VERIFY] Headway separation nominal. Clear green aspects across all automatic block sections.',
      '[REDIS_SYNC] Refreshed all keys with on-time schedule in 1.05ms.'
    ],
    verdict: 'Operational Verdict: Nominal flow restored. Full line-speed running with zero operational delay.'
  }
};

function triggerIncidentLogic(scenarioKey) {
  const scenario = incidentScenarios[scenarioKey];
  if (!scenario) return;

  // Update button active states
  const buttons = document.querySelectorAll('.incident-btn');
  buttons.forEach(btn => btn.classList.remove('active'));
  event.currentTarget.classList.add('active');

  // Update scenario tag
  document.getElementById('terminal-scenario-tag').textContent = scenario.tag;

  // Update terminal logs
  const terminal = document.getElementById('logic-terminal');
  terminal.innerHTML = '';
  scenario.logs.forEach(log => {
    const div = document.createElement('div');
    if (log.includes('[INGESTION]') || log.includes('[TELEMETRY]')) div.innerHTML = `<span class="t-info">${log}</span>`;
    else if (log.includes('[MONITOR]') || log.includes('[ALARM]') || log.includes('[ADMIN_INJECTION]')) div.innerHTML = `<span class="t-warn">${log}</span>`;
    else if (log.includes('[GRAPH_ENGINE]') || log.includes('[LAYER_3_ML]') || log.includes('[LAYER_2_VERIFY]') || log.includes('[LAYER_1_BUFFER]')) div.innerHTML = `<span class="t-accent">${log}</span>`;
    else if (log.includes('[VERIFIED_ETA]') || log.includes('[REDIS_SYNC]') || log.includes('[RESET]')) div.innerHTML = `<span class="t-success">${log}</span>`;
    else if (log.includes('[LAYER_2_FAILSAFE]') || log.includes('[SAFETY_POLICY]')) div.innerHTML = `<span class="t-danger">${log}</span>`;
    else div.textContent = log;
    terminal.appendChild(div);
  });

  // Update decision outcome verdict
  document.getElementById('decision-outcome-box').innerHTML = `<strong>Operational Verdict:</strong> ${scenario.verdict}`;

  // Update corridor track visualizer
  const trainMarker = document.getElementById('train-marker');
  const speedLabel = document.getElementById('train-live-speed');
  const etaPryj = document.getElementById('eta-pryj-text');
  const etaDdu = document.getElementById('eta-ddu-text');
  const activeTrack = document.getElementById('active-track-progress');

  if (trainMarker) trainMarker.setAttribute('transform', `translate(${scenario.trainX}, 110)`);
  if (speedLabel) speedLabel.textContent = scenario.speed;
  if (etaPryj) etaPryj.textContent = scenario.etaPRYJ;
  if (etaDdu) etaDdu.textContent = scenario.etaDDU;
  if (activeTrack) activeTrack.setAttribute('d', `M 60 110 L ${scenario.trainX} 110`);
}

// ==========================================================================
// 5. Page Load Initialization
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  selectPipelineStage('layer3');
  selectArchComponent('redis');
  switchCorridorMode('DETAILED');
});
