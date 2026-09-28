/**
 * DARPAN rail-gateway — provider response normalisation.
 *
 * The ONLY place that knows RailKit's wire format. Everything downstream of this
 * module speaks canonical DTOs (see dto.md). Provider quirks handled here:
 *
 *   - delay is a human string, and the format differs per endpoint:
 *       trackTrain    -> "19 Min"
 *       liveAtStation -> "47 Mins."
 *   - timestamps are "HH:MM DD-Mon" with NO year and NO timezone (times are IST)
 *   - distanceKm / platform arrive as strings, sometimes ""
 *   - timeline mixes real halts (type "stoppage") with passing points ("intermediate")
 *   - absent data is "", "--", null or missing entirely — all mean "unknown"
 *
 * Rule: unknown NEVER becomes a default. It becomes null, and the field is listed
 * in `unavailableFields` so the UI can say "—" instead of inventing a number.
 */

const IST_OFFSET_MIN = 330; // UTC+05:30, Indian Railways runs entirely on IST

const MONTHS = {
  jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
  jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
};

/** "" | "--" | null | undefined | "N/A" -> true */
function isBlank(v) {
  if (v === null || v === undefined) return true;
  const s = String(v).trim();
  return s === '' || s === '--' || s === '-' || s.toUpperCase() === 'N/A';
}

/**
 * "19 Min" | "47 Mins." | "1 Hr 5 Min" | "RIGHT TIME" | "" -> minutes | null
 * Returns 0 for explicit on-time, null for genuinely unknown.
 */
export function parseDelayMinutes(raw) {
  if (isBlank(raw)) return null;
  if (typeof raw === 'number') return Number.isFinite(raw) ? Math.round(raw) : null;
  const s = String(raw).trim();
  if (/right\s*time|on\s*time|no\s*delay/i.test(s)) return 0;

  let total = 0;
  let matched = false;
  const hr = s.match(/(-?\d+)\s*(?:hr|hour|h)\b/i);
  if (hr) { total += parseInt(hr[1], 10) * 60; matched = true; }
  const mn = s.match(/(-?\d+)\s*(?:min|mins|m)\b/i);
  if (mn) { total += parseInt(mn[1], 10); matched = true; }
  if (!matched) {
    const bare = s.match(/^(-?\d+)$/);
    if (!bare) return null;
    total = parseInt(bare[1], 10);
  }
  return total;
}

/**
 * Parse a provider timestamp into an ISO-8601 instant.
 *
 * Accepts "20:23 01-Sep" (trackTrain), "20:05" (liveAtStation, no date),
 * "01-Sep-2026" (date only). The provider omits the year, so it is inferred from
 * `refDate` with wrap handling: a Dec timestamp seen from a Jan reference belongs
 * to the previous year, and vice versa. Without this, every new-year journey
 * would be off by 12 months.
 *
 * @param raw     provider string
 * @param refDate JS Date giving year context (defaults to now)
 * @param fallbackDay "DD-Mon" to use when raw carries only a clock time
 * @returns ISO string with +05:30 offset, or null
 */
export function parseIstTimestamp(raw, refDate = new Date(), fallbackDay = null) {
  if (isBlank(raw)) return null;
  const s = String(raw).trim();

  let hh = null, mi = null, day = null, mon = null, year = null;

  // Four observed shapes:
  //   "20:23 01-Sep"        timeFirst  (trackTrain timeline)
  //   "01-Sep-2026 20:23"   dateFirst  (trackTrain lastUpdate)
  //   "01-Sep-2026"         dateOnly   (trackTrain date, liveAtStation runDate)
  //   "20:05"               timeOnly   (liveAtStation arrival/departure)
  const timeFirst = s.match(/^(\d{1,2}):(\d{2})\s+(\d{1,2})-([A-Za-z]{3})(?:-(\d{4}))?/);
  const dateFirst = s.match(/^(\d{1,2})-([A-Za-z]{3})-(\d{4})\s+(\d{1,2}):(\d{2})/);
  const dateOnly = s.match(/^(\d{1,2})-([A-Za-z]{3})-(\d{4})$/);
  const timeOnly = s.match(/^(\d{1,2}):(\d{2})$/);

  if (timeFirst) {
    hh = +timeFirst[1]; mi = +timeFirst[2]; day = +timeFirst[3];
    mon = MONTHS[timeFirst[4].toLowerCase()] ?? null;
    year = timeFirst[5] ? +timeFirst[5] : null;
  } else if (dateFirst) {
    day = +dateFirst[1]; mon = MONTHS[dateFirst[2].toLowerCase()] ?? null;
    year = +dateFirst[3]; hh = +dateFirst[4]; mi = +dateFirst[5];
  } else if (dateOnly) {
    day = +dateOnly[1]; mon = MONTHS[dateOnly[2].toLowerCase()] ?? null;
    year = +dateOnly[3]; hh = 0; mi = 0;
  } else if (timeOnly) {
    hh = +timeOnly[1]; mi = +timeOnly[2];
    if (fallbackDay) {
      const fb = String(fallbackDay).match(/(\d{1,2})-([A-Za-z]{3})/);
      if (fb) { day = +fb[1]; mon = MONTHS[fb[2].toLowerCase()] ?? null; }
    }
    if (day === null) {
      // Clock-only with no date context: anchor to the reference day in IST.
      const ist = new Date(refDate.getTime() + IST_OFFSET_MIN * 60000);
      day = ist.getUTCDate(); mon = ist.getUTCMonth() + 1; year = ist.getUTCFullYear();
    }
  } else {
    return null;
  }

  if (mon === null || hh === null) return null;

  if (year === null) {
    const ist = new Date(refDate.getTime() + IST_OFFSET_MIN * 60000);
    year = ist.getUTCFullYear();
    const refMon = ist.getUTCMonth() + 1;
    // Year-boundary wrap: Dec seen from Jan -> last year; Jan seen from Dec -> next year.
    if (refMon === 1 && mon === 12) year -= 1;
    else if (refMon === 12 && mon === 1) year += 1;
  }

  if (hh > 23 || mi > 59 || day < 1 || day > 31) return null;
  const pad = (n, w = 2) => String(n).padStart(w, '0');
  return `${pad(year, 4)}-${pad(mon)}-${pad(day)}T${pad(hh)}:${pad(mi)}:00+05:30`;
}

/** "200" | 200 | "" -> number | null */
export function parseNum(raw) {
  if (isBlank(raw)) return null;
  const n = Number(String(raw).trim());
  return Number.isFinite(n) ? n : null;
}

/** Platform: keep as a string label ("1", "4A"), null when unknown. */
export function parsePlatform(raw) {
  if (isBlank(raw)) return null;
  const s = String(raw).trim();
  return s === '0' ? null : s;
}

function normStationName(raw) {
  if (isBlank(raw)) return null;
  // Provider yells: "ASANSOL JN." / "HOWRAH JN". Title-case for display,
  // preserving the Jn/Cantt style abbreviations.
  return String(raw).trim().replace(/\s+/g, ' ').replace(
    /\w[\w']*/g,
    (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(),
  );
}

// ---------------------------------------------------------------------------
// Canonical DTO builders
// ---------------------------------------------------------------------------

/**
 * trackTrain -> canonical live status.
 *
 * The provider's `timeline` interleaves 9 real halts with ~247 passing points for
 * a long-distance train. We keep them separate:
 *   stops         - scheduled halts, the timeline the UI renders
 *   passingPoints - non-halt points, used only to pin down current position
 */
export function normaliseLiveStatus(payload, { trainNumber, journeyDate } = {}) {
  const d = payload?.data ?? {};
  const timeline = Array.isArray(d.timeline) ? d.timeline : [];
  const unavailable = [];

  const ref = parseIstTimestamp(d.lastUpdate) ?? null;
  const refDate = ref ? new Date(ref) : new Date();

  const mapEntry = (e) => {
    const arr = e.arrival ?? {};
    const dep = e.departure ?? {};
    return {
      stationCode: e.stationCode ?? null,
      stationName: normStationName(e.stationName),
      status: ['passed', 'current', 'upcoming'].includes(e.status) ? e.status : null,
      distanceKm: parseNum(e.distanceKm),
      platform: parsePlatform(e.platform),
      arrival: {
        scheduled: parseIstTimestamp(arr.scheduled, refDate),
        actual: parseIstTimestamp(arr.actual, refDate),
        delayMinutes: parseDelayMinutes(arr.delay),
      },
      departure: {
        scheduled: parseIstTimestamp(dep.scheduled, refDate),
        actual: parseIstTimestamp(dep.departure ?? dep.actual, refDate),
        delayMinutes: parseDelayMinutes(dep.delay),
      },
    };
  };

  const stops = timeline.filter((e) => e.type === 'stoppage').map(mapEntry);
  const passingPoints = timeline
    .filter((e) => e.type !== 'stoppage')
    .map((e) => ({
      stationCode: e.stationCode ?? null,
      stationName: normStationName(e.stationName),
      status: e.status ?? null,
    }));

  // Current delay: the most recent observed delay on a passed/current halt.
  let currentDelayMinutes = null;
  for (const s of stops) {
    const observed = s.departure.delayMinutes ?? s.arrival.delayMinutes;
    if ((s.status === 'passed' || s.status === 'current') && observed !== null) {
      currentDelayMinutes = observed;
    }
  }
  if (currentDelayMinutes === null) unavailable.push('position.delayMinutes');

  const currentCode = d.currentStationCode ?? null;
  const lastPassed = [...stops].reverse().find((s) => s.status === 'passed') ?? null;
  const nextStop = stops.find((s) => s.status === 'upcoming' || s.status === 'current') ?? null;

  // The provider reports NO live speed. Deriving one from two timestamps would be
  // an inference, not telemetry, so it is exposed as null and flagged. The UI
  // renders "—". This is the H4 `speed: 128` lie, removed at the source.
  unavailable.push('position.speedKmph');

  const coaches = Array.isArray(d.coachPosition)
    ? d.coachPosition.map((c) => ({
        type: isBlank(c.type) ? null : String(c.type).trim(),
        label: isBlank(c.number) ? null : String(c.number).trim(),
        position: parseNum(c.position),
      }))
    : [];
  if (!coaches.length) unavailable.push('composition');

  const totalDistanceKm = stops.reduce(
    (max, s) => (s.distanceKm !== null && s.distanceKm > max ? s.distanceKm : max), 0,
  ) || null;
  const coveredKm = lastPassed?.distanceKm ?? null;

  return {
    train: {
      number: d.trainNo ?? trainNumber ?? null,
      name: normStationName(d.trainName),
      journeyDate: parseIstTimestamp(d.date)?.slice(0, 10) ?? journeyDate ?? null,
    },
    position: {
      currentStationCode: currentCode,
      lastStationCode: lastPassed?.stationCode ?? null,
      nextStationCode: nextStop?.stationCode ?? null,
      delayMinutes: currentDelayMinutes,
      speedKmph: null,
      distanceCoveredKm: coveredKm,
      totalDistanceKm,
      statusNote: isBlank(d.statusNote) ? null : String(d.statusNote).trim(),
      lastUpdateAt: ref,
    },
    stops,
    passingPoints,
    composition: coaches,
    unavailableFields: unavailable,
  };
}

/** getTrainInfo -> canonical train + route (route carries real coordinates). */
export function normaliseTrainInfo(payload) {
  const d = payload?.data ?? {};
  const info = d.trainInfo ?? {};
  const route = Array.isArray(d.route) ? d.route : [];

  return {
    train: {
      number: info.train_no ?? null,
      name: normStationName(info.train_name),
      type: isBlank(info.type) ? null : String(info.type).trim(),
      from: { code: info.from_stn_code ?? null, name: normStationName(info.from_stn_name) },
      to: { code: info.to_stn_code ?? null, name: normStationName(info.to_stn_name) },
      departureTime: isBlank(info.from_time) ? null : info.from_time,
      arrivalTime: isBlank(info.to_time) ? null : info.to_time,
      travelTime: isBlank(info.travel_time) ? null : info.travel_time,
      // "1111111" -> [Mon..Sun] booleans; IR convention starts at Monday.
      runningDays: /^[01]{7}$/.test(String(info.running_days ?? ''))
        ? String(info.running_days).split('').map((c) => c === '1')
        : null,
    },
    route: route.map((r, i) => ({
      seq: i + 1,
      stationCode: r.stnCode ?? null,
      stationName: normStationName(r.stnName),
      arrival: isBlank(r.arrival) ? null : r.arrival,
      departure: isBlank(r.departure) ? null : r.departure,
      haltMinutes: parseNum(r.haltMinutes),
      distanceKm: parseNum(r.distance),
      day: parseNum(r.day),
      platform: parsePlatform(r.platform),
      lat: parseNum(r.coordinates?.latitude),
      lon: parseNum(r.coordinates?.longitude),
    })),
  };
}

/** liveAtStation -> canonical station board. */
export function normaliseStationBoard(payload, { stationCode } = {}) {
  const d = payload?.data ?? {};
  const trains = Array.isArray(d.trains) ? d.trains : [];
  return {
    stationCode: stationCode ?? null,
    totalTrains: parseNum(d.totalTrains) ?? trains.length,
    trains: trains.map((t) => ({
      trainNumber: t.trainNo ?? null,
      trainName: normStationName(t.trainName),
      trainType: isBlank(t.trainType) ? null : String(t.trainType).trim(),
      from: { code: t.source ?? null, name: normStationName(t.sourceName) },
      to: { code: t.dest ?? null, name: normStationName(t.destName) },
      classes: isBlank(t.classes) ? null : String(t.classes).trim(),
      platform: parsePlatform(t.platform),
      cancelled: t.cancelled === null || t.cancelled === undefined ? false : Boolean(t.cancelled),
      runDate: parseIstTimestamp(t.runDate)?.slice(0, 10) ?? null,
      arrival: {
        scheduled: parseIstTimestamp(t.arrival?.scheduled, new Date(), t.runDate),
        actual: parseIstTimestamp(t.arrival?.actual, new Date(), t.runDate),
        delayMinutes: parseDelayMinutes(t.arrival?.delay),
      },
      departure: {
        scheduled: parseIstTimestamp(t.departure?.scheduled, new Date(), t.runDate),
        actual: parseIstTimestamp(t.departure?.actual, new Date(), t.runDate),
        delayMinutes: parseDelayMinutes(t.departure?.delay),
      },
    })),
  };
}

/**
 * checkPNRStatus -> canonical PNR.
 * NOTE: passenger names are deliberately NOT propagated. The UI never displayed
 * them, and dropping them at the boundary means they cannot reach a log, a cache,
 * or a metric label. (Plan §4.1 / D7.)
 */
export function normalisePnr(payload, { pnr } = {}) {
  const d = payload?.data ?? {};
  const rawPassengers = d.passengers ?? d.passengerList ?? [];

  return {
    pnr,
    train: {
      number: d.trainNo ?? d.trainNumber ?? d.train_number ?? null,
      name: normStationName(d.trainName ?? d.train_name),
    },
    journeyDate: d.doj ?? d.dateOfJourney ?? d.date_of_journey ?? null,
    from: { code: d.from ?? d.fromStation ?? null, name: normStationName(d.fromStationName) },
    to: { code: d.to ?? d.toStation ?? null, name: normStationName(d.toStationName) },
    boardingPoint: d.boardingPoint ?? null,
    reservationClass: d.journeyClass ?? d.class ?? null,
    quota: d.quota ?? null,
    chartPrepared: typeof d.chartPrepared === 'boolean'
      ? d.chartPrepared
      : (typeof d.chart_prepared === 'boolean' ? d.chart_prepared : null),
    passengers: (Array.isArray(rawPassengers) ? rawPassengers : []).map((p, i) => ({
      serial: parseNum(p.passengerSerialNumber ?? p.passenger_serial_number) ?? i + 1,
      bookingStatus: p.bookingStatus ?? p.booking_status ?? null,
      currentStatus: p.currentStatus ?? p.current_status ?? null,
      coach: p.coach ?? p.coachPosition ?? null,
      berth: parseNum(p.berth ?? p.seatNumber),
      berthType: p.berthType ?? p.berth_type ?? null,
    })),
  };
}

export const __testables = { isBlank, normStationName };
