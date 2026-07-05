'use strict';

/**
 * candidates/schedule_a.js — cronsplain schedule tournament candidate A
 * (T-047): BRUTE-FORCE MINUTE TICK.
 *
 * Implements nextOccurrences(parsed, fromDate, count) -> Date[] exactly per
 * the interface pinned in candidates/vectors.js (INTERFACE_DOC / T-046) and
 * the ParsedCron shape pinned in lib/parser.js (T-045):
 *
 *   parsed = {
 *     fields: {
 *       minute: Set<int>, hour: Set<int>, dayOfMonth: Set<int>,
 *       month: Set<int>, dayOfWeek: Set<int>,
 *     },
 *     domRestricted: boolean, dowRestricted: boolean, source: string,
 *   }
 *
 * METHOD (candidate A's identity): start at a UTC instant one minute after
 * `fromDate` (seconds/ms zeroed), then advance strictly ONE MINUTE AT A TIME,
 * testing every visited minute against the parsed Sets via plain UTC getters
 * (getUTCMinutes/getUTCHours/getUTCDate/getUTCMonth+1/getUTCDay), applying
 * the DOM/DOW OR-coupling rule at the day level. Every minute that satisfies
 * all constraints is collected, in the ascending order they are visited
 * (which is already ascending because we only ever step forward), until
 * `count` matches have been collected.
 *
 * This is deliberately the "obviously correct, obviously slow" reference
 * method: no field-cascade carry/increment logic, no jumping ahead by
 * computing the next valid hour/day directly — just tick-and-test. It is
 * the tournament's brute-force baseline candidate, verified against the
 * golden vectors below.
 *
 * SAFETY ITERATION CAP: cron schedules can specify combinations that never
 * occur (e.g. '0 0 30 2 *' — February never has a 30th day), which would
 * otherwise tick forever. We bound the total number of minutes stepped to
 * MAX_MINUTES_TO_SCAN = 6,000,000 (~11.4 calendar years' worth of minutes:
 * 6,000,000 / (365.25 * 24 * 60) ~= 11.41). If the cap is reached before
 * `count` matches are found, we stop early and return whatever matches were
 * collected (fewer than `count` entries) rather than looping forever. The
 * widest gap exercised by the golden vectors (candidates/vectors.js) is the
 * Feb-29 leap-year case, which spans ~5.16 years (2023-01-01 -> 2028-02-29,
 * 2,714,400 minutes) — comfortably inside this cap with more than 2x margin
 * to spare, while a genuinely impossible schedule like '0 0 30 2 *' still
 * terminates deterministically instead of looping forever.
 *
 * Zero runtime dependencies; CommonJS only (package.json / T-044 contract).
 */

const MAX_MINUTES_TO_SCAN = 6000000; // ~11.4 years of minutes; see comment above.

/**
 * Does UTC day D (given its day-of-month and day-of-week) satisfy the
 * parsed DOM/DOW coupling rule?
 *
 * @param {number} dom - D's UTC day-of-month (1-31)
 * @param {number} dow - D's UTC day-of-week (0-6, Sun=0)
 * @param {object} parsed - the ParsedCron object
 * @returns {boolean}
 */
function dayMatches(dom, dow, parsed) {
  const { domRestricted, dowRestricted } = parsed;
  const { dayOfMonth, dayOfWeek } = parsed.fields;

  if (domRestricted && dowRestricted) {
    // Vixie OR-coupling: union, not intersection.
    return dayOfMonth.has(dom) || dayOfWeek.has(dow);
  }
  if (domRestricted) {
    return dayOfMonth.has(dom);
  }
  if (dowRestricted) {
    return dayOfWeek.has(dow);
  }
  // Neither field restricted: every day matches.
  return true;
}

/**
 * Does UTC instant `d` (already minute-aligned) fully satisfy `parsed`?
 *
 * @param {Date} d
 * @param {object} parsed
 * @returns {boolean}
 */
function minuteMatches(d, parsed) {
  const { minute, hour, month } = parsed.fields;

  if (!minute.has(d.getUTCMinutes())) return false;
  if (!hour.has(d.getUTCHours())) return false;
  if (!month.has(d.getUTCMonth() + 1)) return false; // Set is 1-12
  if (!dayMatches(d.getUTCDate(), d.getUTCDay(), parsed)) return false;

  return true;
}

/**
 * nextOccurrences(parsed, fromDate, count) -> Date[]
 *
 * Returns the next `count` UTC minutes strictly after `fromDate` that
 * satisfy `parsed`, in ascending order, via brute-force minute ticking.
 * See module doc comment above for the full method + safety-cap notes.
 *
 * @param {object} parsed - ParsedCron shape from require('../lib/parser').parse
 * @param {Date} fromDate - exclusive lower bound
 * @param {number} count - number of occurrences to return
 * @returns {Date[]}
 */
function nextOccurrences(parsed, fromDate, count) {
  const results = [];

  // Start one minute after fromDate, minute-aligned (seconds=0, ms=0). Using
  // Date.UTC with the minute already advanced by one guarantees exclusivity
  // of fromDate itself even when fromDate lands exactly on a matching
  // minute — we never test fromDate's own minute at all.
  let cursor = new Date(
    Date.UTC(
      fromDate.getUTCFullYear(),
      fromDate.getUTCMonth(),
      fromDate.getUTCDate(),
      fromDate.getUTCHours(),
      fromDate.getUTCMinutes() + 1,
      0,
      0
    )
  );

  let stepsTaken = 0;
  while (results.length < count && stepsTaken < MAX_MINUTES_TO_SCAN) {
    if (minuteMatches(cursor, parsed)) {
      results.push(cursor);
    }
    // Advance exactly one minute. Date.UTC/setUTCMinutes handles all
    // carries (minute->hour->day->month->year) correctly, including
    // month-length and leap-year rollovers, since Date normalizes
    // out-of-range field values automatically.
    cursor = new Date(cursor.getTime() + 60000);
    stepsTaken += 1;
  }

  return results;
}

module.exports = { nextOccurrences };
