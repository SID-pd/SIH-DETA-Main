/**
 * DARPAN rail-gateway
 * ===================
 * The ONLY process that holds a provider API key or knows a provider's wire format.
 *
 * Responsibilities (plan §2.1, ADR-001/002):
 *   1. own the RailKit SDK + key            -> key never reaches a browser (fixes D1)
 *   2. normalise to canonical DTOs          -> domain code is provider-agnostic (R2)
 *   3. quota accounting + concurrency cap   -> a demo cannot burn the daily budget (R1)
 *   4. typed errors, never fabricated data  -> failure stays visible (ADR-004)
 *
 * Deliberately zero-dependency (node:http, not Fastify): 14 routes need no framework,
 * and no install step means no supply-chain surface on a service that holds a secret.
 *
 * Bind: 127.0.0.1 only. This service must never be internet-reachable.
 */

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as normalise from './normalise.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../../..');
const SDK_PATH = path.join(
  REPO_ROOT, 'Indian-railway-Railkit-main-api', 'RailKit-main', 'index.obfuscated.js',
);

const PORT = Number(process.env.GATEWAY_PORT || 8081);
const HOST = '127.0.0.1';
const DAILY_QUOTA = Number(process.env.RAILKIT_DAILY_QUOTA || 5000);
const MAX_CONCURRENCY = Number(process.env.GATEWAY_MAX_CONCURRENCY || 4);
const UPSTREAM_TIMEOUT_MS = Number(process.env.GATEWAY_TIMEOUT_MS || 15000);

// --- key loading: env first, then repo .env. Never logged beyond a fingerprint. ---
function loadApiKey() {
  if (process.env.RAILKIT_API_KEY) return process.env.RAILKIT_API_KEY.trim();
  const envPath = path.join(REPO_ROOT, '.env');
  if (fs.existsSync(envPath)) {
    const m = fs.readFileSync(envPath, 'utf8').match(/RAILKIT_API_KEY\s*=\s*(.+)/);
    if (m) return m[1].trim();
  }
  return null;
}

const API_KEY = loadApiKey();
if (!API_KEY) {
  console.error('[gateway] FATAL: RAILKIT_API_KEY not found in env or repo .env');
  process.exit(1);
}
const KEY_FINGERPRINT = `${API_KEY.slice(0, 12)}…${API_KEY.slice(-4)}`;

const rk = await import(`file://${SDK_PATH.split(path.sep).join('/')}`);
rk.configure(API_KEY);

// ---------------------------------------------------------------------------
// Quota + concurrency
// ---------------------------------------------------------------------------

const quota = {
  day: new Date().toISOString().slice(0, 10),
  used: 0,
  byEndpoint: Object.create(null),
  errors: 0,
  rolled() {
    const today = new Date().toISOString().slice(0, 10);
    if (today !== this.day) { this.day = today; this.used = 0; this.errors = 0; this.byEndpoint = Object.create(null); }
  },
  remaining() { this.rolled(); return Math.max(0, DAILY_QUOTA - this.used); },
  charge(ep) {
    this.rolled();
    this.used += 1;
    this.byEndpoint[ep] = (this.byEndpoint[ep] || 0) + 1;
  },
};

let inFlight = 0;
const waiters = [];
async function withSlot(fn) {
  if (inFlight >= MAX_CONCURRENCY) {
    await new Promise((res) => waiters.push(res));
  }
  inFlight += 1;
  try {
    return await fn();
  } finally {
    inFlight -= 1;
    const next = waiters.shift();
    if (next) next();
  }
}

function withTimeout(promise, ms, label) {
  let timer;
  const timeout = new Promise((_, rej) => {
    timer = setTimeout(() => rej(new GatewayError('PROVIDER_TIMEOUT', `${label} exceeded ${ms}ms`, 504, true)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

class GatewayError extends Error {
  constructor(code, message, status = 502, retryable = false) {
    super(message);
    this.code = code; this.status = status; this.retryable = retryable;
  }
}

/**
 * Map a provider failure string onto a typed error.
 * The provider signals "not found" with success:false + a prose message, so this
 * is where prose becomes a status code. Note we do NOT fall back to data.
 */
function classifyProviderError(msg) {
  const s = String(msg || '').toLowerCase();
  if (/no pnr data|invalid pnr/.test(s)) return new GatewayError('PNR_NOT_FOUND', msg, 404, false);
  // "Train data not available for date: 01-Sep-2026" — either an unknown train, or a
  // real train with no run on that date. Both deterministic: retrying spends quota.
  if (/not found|no data|not available|invalid train|invalid station/.test(s)) return new GatewayError('NOT_FOUND', msg, 404, false);
  if (/quota|limit|exhaust/.test(s)) return new GatewayError('PROVIDER_QUOTA', msg, 429, true);
  if (/unauthor|forbidden|api key|invalid key/.test(s)) return new GatewayError('PROVIDER_AUTH', msg, 502, false);
  if (/timeout|timed out|econn|network|socket/.test(s)) return new GatewayError('PROVIDER_TIMEOUT', msg, 504, true);
  // Deterministic rejections: the same request will fail identically, so retrying
  // just spends quota to learn nothing.
  if (/invalid|malformed|must be|required|bad request/.test(s)) return new GatewayError('PROVIDER_REJECTED', msg, 400, false);
  return new GatewayError('PROVIDER_ERROR', msg || 'provider call failed', 502, true);
}

/**
 * Single provider call: quota gate -> concurrency slot -> timeout -> normalise.
 * One jittered retry, but only for retryable classes and never for 4xx —
 * retrying a "train not found" just spends quota to get the same answer.
 */
async function callProvider(endpoint, fn, normaliser, ctx = {}) {
  if (quota.remaining() <= 0) {
    throw new GatewayError('QUOTA_EXHAUSTED',
      `local daily budget of ${DAILY_QUOTA} reached; refusing to call provider`, 429, true);
  }

  const attempt = async () => {
    quota.charge(endpoint);
    const t0 = Date.now();
    const raw = await withTimeout(fn(), UPSTREAM_TIMEOUT_MS, endpoint);
    const latency = Date.now() - t0;
    if (!raw || raw.success !== true) {
      throw classifyProviderError(raw?.error ?? raw?.message);
    }
    return { dto: normaliser ? normaliser(raw, ctx) : raw.data, latency };
  };

  try {
    return await attempt();
  } catch (err) {
    const e = err instanceof GatewayError ? err : classifyProviderError(err.message);
    if (!e.retryable || quota.remaining() <= 0) { quota.errors += 1; throw e; }
    await new Promise((r) => setTimeout(r, 250 + Math.random() * 400)); // jittered
    try {
      return await attempt();
    } catch (err2) {
      quota.errors += 1;
      throw err2 instanceof GatewayError ? err2 : classifyProviderError(err2.message);
    }
  }
}

// ---------------------------------------------------------------------------
// Routes  (canonical DTO out; the API service never sees a RailKit field name)
// ---------------------------------------------------------------------------

const RX_TRAIN = /^\d{5}$/;
const RX_STATION = /^[A-Za-z0-9]{1,5}$/;
const RX_PNR = /^\d{10}$/;
const RX_DATE = /^\d{2}-\d{2}-\d{4}$/; // DD-MM-YYYY, the provider's format

function bad(msg) { return new GatewayError('BAD_REQUEST', msg, 400, false); }

/** Today in IST as DD-MM-YYYY (the provider's date format). */
function istDateDDMMYYYY(now = new Date()) {
  const ist = new Date(now.getTime() + 330 * 60000); // UTC+05:30
  const p = (n) => String(n).padStart(2, '0');
  return `${p(ist.getUTCDate())}-${p(ist.getUTCMonth() + 1)}-${ist.getUTCFullYear()}`;
}

const routes = {
  'live': async (q) => {
    const no = String(q.train || '');
    if (!RX_TRAIN.test(no)) throw bad('train must be 5 digits');
    // Always pass an explicit date. Two reasons:
    //  1. trackTrain(no, undefined) is rejected by the provider ("Invalid date format.")
    //  2. relying on the SDK's implicit default would use the SERVER's calendar day;
    //     Indian Railways runs on IST, so we compute the IST day ourselves. Between
    //     18:30 and 24:00 UTC these differ, which is exactly the evening window when
    //     long-distance trains are mid-journey.
    const date = q.date && RX_DATE.test(q.date) ? q.date : istDateDDMMYYYY();
    return callProvider('trackTrain',
      () => rk.trackTrain(no, date),
      normalise.normaliseLiveStatus,
      { trainNumber: no, journeyDate: date });
  },

  'train': async (q) => {
    const no = String(q.train || '');
    if (!RX_TRAIN.test(no)) throw bad('train must be 5 digits');
    return callProvider('getTrainInfo', () => rk.getTrainInfo(no), normalise.normaliseTrainInfo);
  },

  'board': async (q) => {
    const code = String(q.station || '').toUpperCase();
    if (!RX_STATION.test(code)) throw bad('station must be 1-5 alphanumerics');
    const hours = [2, 4, 8].includes(Number(q.hours)) ? Number(q.hours) : 2;
    return callProvider('liveAtStation',
      () => rk.liveAtStation(code, hours),
      normalise.normaliseStationBoard, { stationCode: code });
  },

  'pnr': async (q) => {
    const pnr = String(q.pnr || '');
    if (!RX_PNR.test(pnr)) throw bad('pnr must be 10 digits');
    return callProvider('checkPNRStatus',
      () => rk.checkPNRStatus(pnr), normalise.normalisePnr, { pnr });
  },

  'station': async (q) => {
    const code = String(q.code || '').toUpperCase();
    if (!RX_STATION.test(code)) throw bad('code must be 1-5 alphanumerics');
    return callProvider('stationByCode', () => rk.stationByCode(code), null);
  },

  'history': async (q) => {
    const no = String(q.train || '');
    if (!RX_TRAIN.test(no)) throw bad('train must be 5 digits');
    if (!RX_DATE.test(String(q.date || ''))) throw bad('date must be DD-MM-YYYY');
    return callProvider('getTrainHistory', () => rk.getTrainHistory(no, q.date), null);
  },

  'cancelled': async () => callProvider('cancelList', () => rk.cancelList(), null),
};

// ---------------------------------------------------------------------------
// HTTP surface
// ---------------------------------------------------------------------------

function send(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(payload),
    'cache-control': 'no-store',
  });
  res.end(payload);
}

const server = http.createServer(async (req, res) => {
  const started = Date.now();
  let url;
  try { url = new URL(req.url, `http://${HOST}:${PORT}`); }
  catch { return send(res, 400, { ok: false, error: { code: 'BAD_REQUEST', message: 'malformed url' } }); }

  const seg = url.pathname.replace(/^\/+|\/+$/g, '').split('/');
  const q = Object.fromEntries(url.searchParams);

  if (seg[0] === 'health') {
    return send(res, 200, {
      ok: true,
      service: 'rail-gateway',
      provider: 'railkit',
      keyFingerprint: KEY_FINGERPRINT,
      quota: { day: quota.day, used: quota.used, remaining: quota.remaining(), limit: DAILY_QUOTA, byEndpoint: quota.byEndpoint, errors: quota.errors },
      concurrency: { inFlight, max: MAX_CONCURRENCY, queued: waiters.length },
      uptimeSec: Math.round(process.uptime()),
    });
  }

  if (seg[0] !== 'internal' || !routes[seg[1]]) {
    return send(res, 404, { ok: false, error: { code: 'NO_ROUTE', message: `unknown route ${url.pathname}` } });
  }

  try {
    const { dto, latency } = await withSlot(() => routes[seg[1]](q));
    // Access log carries NO query values: a PNR must never reach a log line (D7).
    console.log(`[gateway] ${seg[1]} 200 upstream=${latency}ms total=${Date.now() - started}ms quota=${quota.used}/${DAILY_QUOTA}`);
    return send(res, 200, { ok: true, data: dto, meta: { provider: 'railkit', endpoint: seg[1], upstreamLatencyMs: latency, fetchedAt: new Date().toISOString() } });
  } catch (err) {
    const e = err instanceof GatewayError ? err : classifyProviderError(err.message);
    console.warn(`[gateway] ${seg[1]} ${e.status} ${e.code} total=${Date.now() - started}ms`);
    return send(res, e.status, { ok: false, error: { code: e.code, message: e.message, retryable: e.retryable } });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`[gateway] listening http://${HOST}:${PORT}  key=${KEY_FINGERPRINT}  quota=${DAILY_QUOTA}/day  maxConcurrency=${MAX_CONCURRENCY}`);
});

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => { console.log(`[gateway] ${sig} received, closing`); server.close(() => process.exit(0)); });
}
