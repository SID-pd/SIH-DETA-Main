/**
 * Normalisation tests — run offline against recorded provider fixtures.
 * `node --test services/rail-gateway/test/`
 *
 * Fixtures are real captured RailKit responses (plan §6 W4.6: "integration tests
 * with recorded provider fixtures"), so these tests cost zero quota and stay
 * meaningful when the provider is down.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  parseDelayMinutes, parseIstTimestamp, parseNum, parsePlatform,
  normaliseLiveStatus, normaliseTrainInfo, normaliseStationBoard, normalisePnr,
} from '../src/normalise.mjs';

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures');
const load = (n) => JSON.parse(fs.readFileSync(path.join(FIX, n), 'utf8'));

// --- scalar parsers -------------------------------------------------------

test('parseDelayMinutes handles every observed provider format', () => {
  assert.equal(parseDelayMinutes('19 Min'), 19);        // trackTrain
  assert.equal(parseDelayMinutes('47 Mins.'), 47);      // liveAtStation
  assert.equal(parseDelayMinutes('1 Hr 5 Min'), 65);
  assert.equal(parseDelayMinutes('RIGHT TIME'), 0);
  assert.equal(parseDelayMinutes('0 Min'), 0);
  assert.equal(parseDelayMinutes(12), 12);
  assert.equal(parseDelayMinutes('-3 Min'), -3);        // running early
});

test('parseDelayMinutes returns null for unknown, never 0', () => {
  // The critical distinction: "we do not know the delay" must not render as
  // "on time". This is ADR-004 at the scalar level.
  for (const v of ['', '--', null, undefined, 'N/A', 'garbage']) {
    assert.equal(parseDelayMinutes(v), null, `expected null for ${JSON.stringify(v)}`);
  }
});

test('parseIstTimestamp parses "HH:MM DD-Mon" as IST', () => {
  const ref = new Date('2026-09-01T12:00:00Z');
  assert.equal(parseIstTimestamp('20:23 01-Sep', ref), '2026-09-01T20:23:00+05:30');
  assert.equal(parseIstTimestamp('18:47 01-Sep', ref), '2026-09-01T18:47:00+05:30');
});

test('parseIstTimestamp infers year across the Dec/Jan boundary', () => {
  // A Dec timestamp observed from a Jan reference belongs to the PREVIOUS year.
  const jan = new Date('2027-01-02T06:00:00Z');
  assert.equal(parseIstTimestamp('23:50 31-Dec', jan), '2026-12-31T23:50:00+05:30');
  // A Jan timestamp observed from a Dec reference belongs to the NEXT year.
  const dec = new Date('2026-12-31T20:00:00Z');
  assert.equal(parseIstTimestamp('00:20 01-Jan', dec), '2027-01-01T00:20:00+05:30');
});

test('parseIstTimestamp handles date-only and clock-only forms', () => {
  assert.equal(parseIstTimestamp('01-Sep-2026'), '2026-09-01T00:00:00+05:30');
  // clock-only + explicit day context (liveAtStation gives runDate separately)
  assert.equal(
    parseIstTimestamp('20:05', new Date('2026-09-01T12:00:00Z'), '01-Sep-2026'),
    '2026-09-01T20:05:00+05:30',
  );
  assert.equal(parseIstTimestamp('--'), null);
  assert.equal(parseIstTimestamp('25:99 01-Sep'), null); // impossible clock
});

test('parseNum / parsePlatform treat blanks as unknown', () => {
  assert.equal(parseNum('200'), 200);
  assert.equal(parseNum(''), null);      // origin station distanceKm is ""
  assert.equal(parsePlatform('4'), '4');
  assert.equal(parsePlatform('4A'), '4A');
  assert.equal(parsePlatform('0'), null); // provider uses 0 for "unassigned"
  assert.equal(parsePlatform(''), null);
});

// --- live status ----------------------------------------------------------

test('normaliseLiveStatus splits halts from passing points', () => {
  const dto = normaliseLiveStatus(load('trackTrain_12301.json'), { trainNumber: '12301' });
  // Fixture: 256 timeline entries = 9 stoppages + 247 intermediates.
  assert.equal(dto.stops.length, 9);
  assert.equal(dto.passingPoints.length, 247);
  assert.equal(dto.train.number, '12301');
  assert.ok(dto.stops.every((s) => s.stationCode));
});

test('normaliseLiveStatus converts delay strings and timestamps', () => {
  const dto = normaliseLiveStatus(load('trackTrain_12301.json'), { trainNumber: '12301' });
  const asn = dto.stops.find((s) => s.stationCode === 'ASN');
  assert.equal(asn.arrival.delayMinutes, 19);           // was "19 Min"
  assert.equal(asn.departure.delayMinutes, 20);         // was "20 Min"
  assert.equal(asn.distanceKm, 200);                    // was "200"
  assert.equal(asn.platform, '4');
  assert.match(asn.arrival.scheduled, /^\d{4}-\d{2}-\d{2}T18:47:00\+05:30$/);
});

test('normaliseLiveStatus reports live speed as unavailable, not invented', () => {
  // H4 in the plan hardcoded `speed: 128`. The provider has no speed field at all,
  // so the DTO must say so rather than guess.
  const dto = normaliseLiveStatus(load('trackTrain_12301.json'), { trainNumber: '12301' });
  assert.equal(dto.position.speedKmph, null);
  assert.ok(dto.unavailableFields.includes('position.speedKmph'));
});

test('normaliseLiveStatus derives position from the timeline', () => {
  const dto = normaliseLiveStatus(load('trackTrain_12301.json'), { trainNumber: '12301' });
  assert.equal(dto.position.currentStationCode, 'MRQ');
  assert.equal(typeof dto.position.delayMinutes, 'number');
  assert.ok(dto.position.totalDistanceKm > 0);
  assert.ok(dto.position.lastUpdateAt.endsWith('+05:30'));
});

test('normaliseLiveStatus exposes real coach composition', () => {
  // H10 in the plan was a fabricated rake. The provider actually supplies one.
  const dto = normaliseLiveStatus(load('trackTrain_12301.json'), { trainNumber: '12301' });
  assert.equal(dto.composition.length, 24);
  assert.equal(dto.composition[0].type, 'ENG');
  assert.equal(dto.composition[2].label, 'B1');
  assert.equal(dto.composition[2].position, 2);
  assert.ok(!dto.unavailableFields.includes('composition'));
});

// --- train info ----------------------------------------------------------

test('normaliseTrainInfo yields a route with usable coordinates', () => {
  const dto = normaliseTrainInfo(load('getTrainInfo_12301.json'));
  assert.equal(dto.train.number, '12301');
  assert.ok(dto.route.length >= 2);
  const withCoords = dto.route.filter((r) => r.lat !== null && r.lon !== null);
  assert.ok(withCoords.length > 0, 'expected at least one stop with coordinates');
  for (const r of withCoords) {
    assert.ok(r.lat > 6 && r.lat < 38, `lat ${r.lat} outside India`);
    assert.ok(r.lon > 68 && r.lon < 98, `lon ${r.lon} outside India`);
  }
  assert.equal(dto.route[0].seq, 1);
});

test('normaliseTrainInfo decodes running days', () => {
  const dto = normaliseTrainInfo(load('getTrainInfo_12301.json'));
  assert.ok(dto.train.runningDays === null || dto.train.runningDays.length === 7);
});

// --- station board -------------------------------------------------------

test('normaliseStationBoard normalises a real NDLS board', () => {
  const dto = normaliseStationBoard(load('liveAtStation_NDLS.json'), { stationCode: 'NDLS' });
  assert.equal(dto.stationCode, 'NDLS');
  assert.ok(dto.trains.length > 0);
  const t = dto.trains[0];
  assert.ok(t.trainNumber);
  assert.equal(typeof t.cancelled, 'boolean'); // provider sends null for "not cancelled"
  // "47 Mins." must have become a number
  const delayed = dto.trains.find((x) => x.arrival.delayMinutes !== null);
  assert.equal(typeof delayed.arrival.delayMinutes, 'number');
});

// --- PNR -----------------------------------------------------------------

test('normalisePnr drops passenger names at the boundary', () => {
  // Privacy is enforced structurally: a name cannot leak into a cache or log
  // because it never enters the DTO. (Plan D7.)
  const dto = normalisePnr({
    data: {
      trainNo: '12301', trainName: 'RAJDHANI EXPRES', from: 'HWH', to: 'NDLS',
      passengers: [{ passenger_serial_number: 1, name: 'REAL PERSON NAME', booking_status: 'CNF', current_status: 'CNF', coach: 'B4', berth: 42 }],
    },
  }, { pnr: '1234567890' });

  assert.equal(dto.passengers.length, 1);
  assert.equal(dto.passengers[0].coach, 'B4');
  assert.equal(dto.passengers[0].berth, 42);
  assert.ok(!('name' in dto.passengers[0]));
  assert.ok(!JSON.stringify(dto).includes('REAL PERSON NAME'));
});

test('normalisePnr does not invent a train when fields are missing', () => {
  // H2 in the plan defaulted missing fields to "12301 / Howrah Rajdhani / HWH->NDLS".
  const dto = normalisePnr({ data: {} }, { pnr: '1234567890' });
  assert.equal(dto.train.number, null);
  assert.equal(dto.train.name, null);
  assert.equal(dto.from.code, null);
  assert.equal(dto.chartPrepared, null); // tri-state: not "false"
  assert.deepEqual(dto.passengers, []);
});

test('parseIstTimestamp parses the date-first lastUpdate form', () => {
  // Regression: "01-Sep-2026 20:23" (trackTrain.lastUpdate) is a distinct shape
  // from "20:23 01-Sep" (timeline entries). Missing it silently nulled lastUpdateAt,
  // which would have made every live response look like it had no freshness stamp.
  assert.equal(parseIstTimestamp('01-Sep-2026 20:23'), '2026-09-01T20:23:00+05:30');
});
