'use strict';

/**
 * tests/test_schedule.js — canonical test for the tournament-promoted
 * lib/schedule.js (T-049 winner: candidate B, field-cascade carry).
 *
 * Coverage:
 *   (1) GOLDEN: the candidate-agnostic vectors (candidates/vectors.js / T-046)
 *       run against the PROMOTED lib/schedule.js — all 11 must pass. Requiring
 *       candidates/vectors.js at TEST TIME is permitted by the T-049 contract
 *       (only the shipped runtime module must be candidate-free; verified: it
 *       has zero candidates/ require).
 *   (2) Independent assertions with hand-computed expected values (NOT derived
 *       from vectors.js): a DOM/DOW OR-coupling case, an EXCLUSIVITY case, a
 *       leap Feb-29 case, and the WINNER's decisive impossible-schedule
 *       behavior (throws, does not silently return a partial array).
 */

const { test } = require('node:test');
const assert = require('node:assert');

const { parse } = require('../lib/parser');
const { nextOccurrences } = require('../lib/schedule');
const { runAgainst } = require('../candidates/vectors');

const iso = (dates) => dates.map((d) => d.toISOString());

test('golden vectors: promoted lib/schedule.js passes all T-046 vectors', () => {
  const { passed, total, failures } = runAgainst(nextOccurrences);
  assert.strictEqual(
    passed,
    total,
    `expected ${total}/${total} golden vectors, got ${passed}; failures: ` +
      JSON.stringify(failures)
  );
  assert.strictEqual(total, 11, 'expected the pinned 11-vector golden set');
});

test('DOM/DOW OR-coupling: "0 0 13 * 5" fires on the 13th OR any Friday (union)', () => {
  // Both dayOfMonth={13} and dayOfWeek={5=Fri} restricted -> a day matches if
  // it is the 13th OR a Friday. In July 2026: Fridays are 3,10,17,24,31 and
  // the 13th is a Monday (dom-only match, must still be included). Expected
  // values hand-computed from the Gregorian calendar, NOT read from vectors.js.
  const parsed = parse('0 0 13 * 5');
  const got = iso(nextOccurrences(parsed, new Date('2026-07-01T00:00:00Z'), 6));
  assert.deepStrictEqual(got, [
    '2026-07-03T00:00:00.000Z', // Friday
    '2026-07-10T00:00:00.000Z', // Friday
    '2026-07-13T00:00:00.000Z', // 13th (a Monday) — dom-only match in the union
    '2026-07-17T00:00:00.000Z', // Friday
    '2026-07-24T00:00:00.000Z', // Friday
    '2026-07-31T00:00:00.000Z', // Friday
  ]);
});

test('EXCLUSIVITY: fromDate landing exactly on a match returns the NEXT minute', () => {
  // "*/15 * * * *" -> minutes {0,15,30,45}. fromDate is EXACTLY 00:15:00, a
  // matching minute; the exclusive-boundary rule requires it be skipped, so
  // the first result is 00:30, not 00:15.
  const parsed = parse('*/15 * * * *');
  const got = iso(nextOccurrences(parsed, new Date('2026-07-04T00:15:00Z'), 1));
  assert.deepStrictEqual(got, ['2026-07-04T00:30:00.000Z']);

  // Second exclusivity flavor: a daily 00:00 job started exactly at midnight
  // must skip that midnight and land on the following day's midnight.
  const daily = parse('0 0 * * *');
  const gotDaily = iso(nextOccurrences(daily, new Date('2026-07-04T00:00:00Z'), 1));
  assert.deepStrictEqual(gotDaily, ['2026-07-05T00:00:00.000Z']);
});

test('LEAP: "0 0 29 2 *" only fires in leap years (2024 then 2028, skipping 2025-2027)', () => {
  const parsed = parse('0 0 29 2 *');
  const got = iso(nextOccurrences(parsed, new Date('2023-01-01T00:00:00Z'), 2));
  assert.deepStrictEqual(got, [
    '2024-02-29T00:00:00.000Z',
    '2028-02-29T00:00:00.000Z',
  ]);
});

test('WINNER DECISIVE BEHAVIOR: an impossible schedule THROWS (no silent partial)', () => {
  // "0 0 30 2 *" — February never has a 30th day, so this schedule can never
  // be satisfied. The promoted engine (candidate B) throws a documented Error
  // rather than silently returning fewer than `count` dates (candidate A's
  // losing behavior). This pins the tournament's decisive axis.
  const parsed = parse('0 0 30 2 *');
  assert.throws(
    () => nextOccurrences(parsed, new Date('2026-01-01T00:00:00Z'), 1),
    /no valid day found within \d+ day-carries/,
    'impossible schedule must throw, not return a partial/empty array'
  );
});

test('LONG-HORIZON SPARSE: yearly schedule returns the full requested count', () => {
  // "0 0 1 1 *" fires once a year (Jan 1). Requesting 20 occurrences must
  // return exactly 20 — the promoted engine's day-carry cap bounds the gap
  // BETWEEN occurrences, not the total horizon, so a long legitimate sequence
  // is never silently truncated (candidate A truncated this to 11).
  const parsed = parse('0 0 1 1 *');
  const got = nextOccurrences(parsed, new Date('2026-01-01T00:00:00Z'), 20);
  assert.strictEqual(got.length, 20);
  assert.strictEqual(got[0].toISOString(), '2027-01-01T00:00:00.000Z');
  assert.strictEqual(got[19].toISOString(), '2046-01-01T00:00:00.000Z');
});
