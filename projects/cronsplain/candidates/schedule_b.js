'use strict';

/**
 * candidates/schedule_b.js — cronsplain schedule tournament, CANDIDATE B
 * (T-048): FIELD-CASCADE CARRY INCREMENT.
 *
 * Implements nextOccurrences(parsed, fromDate, count) -> Date[] exactly per
 * the INTERFACE_DOC in candidates/vectors.js (T-046, authoritative). See
 * that file for the full contract; the short version:
 *
 *   - `parsed` is the ParsedCron shape from require('../lib/parser').parse():
 *       { fields: { minute, hour, dayOfMonth, month, dayOfWeek } (all
 *         Set<int>), domRestricted: boolean, dowRestricted: boolean }.
 *   - Returns `count` UTC Date objects (seconds=0, ms=0), STRICTLY AFTER
 *     fromDate (exclusive), ascending, satisfying `parsed` including the
 *     DOM/DOW OR-coupling rule (both restricted -> union; one restricted ->
 *     that field alone; neither -> every day matches).
 *
 * METHOD (candidate B's identity — deliberately different from candidate A's
 * brute-force minute tick): FIELD-CASCADE CARRY INCREMENT.
 *
 *   1. Start from a lower-bound minute one past fromDate (single arithmetic
 *      step via addOneMinute — calendar-correct, not a search loop).
 *   2. If the lower-bound's OWN calendar day already satisfies the
 *      month + DOM/DOW-OR rule, look for the next valid {hour, minute}
 *      *within that same day* via direct Set lookups (findTimeInDay):
 *        - if the lower-bound hour itself is valid and a minute >= the
 *          lower-bound minute exists in the minute Set, use it;
 *        - else find the smallest hour in the hour Set that is strictly
 *          greater than the lower-bound hour, and take that hour's
 *          smallest valid minute;
 *        - else the day is exhausted (fall through to step 3).
 *   3. If the day doesn't qualify at all, or step 2 found nothing left in
 *      it, CARRY to the next valid day: walk day-by-day (addOneDay, which
 *      is calendar-correct per-month-length and leap-year aware since it
 *      derives days-in-month from Date.UTC's own normalization) re-testing
 *      the month + DOM/DOW-OR predicate, until a matching day is found —
 *      then reset {hour, minute} to the smallest values in their Sets.
 *      This is the "carry across month/year boundaries" behavior: crossing
 *      a month or year boundary is just another day-carry step, and
 *      Date.UTC-derived day-counts (see daysInMonth) automatically handle
 *      28/29/30/31-day months and leap Feb 29 with no special-cased
 *      calendar math.
 *   4. Repeat step 2-3 (bounded by SAFETY_CAP_DAYS below) until `count`
 *      occurrences are collected; the lower bound for the next occurrence
 *      is simply the previous result + 1 minute (step 1 again).
 *
 * This never ticks minute-by-minute across empty stretches: within a day,
 * matching {hour, minute} pairs are found by direct Set membership/search
 * (O(|hours| + |minutes|), both <= 60); only crossing INVALID days costs an
 * iteration, and even that is a single calendar day per step, never a
 * per-minute scan.
 *
 * SAFETY CAP: day-carrying (step 3) is bounded by SAFETY_CAP_DAYS = 3660
 * (~10 Gregorian years). This comfortably covers the worst realistic
 * legitimate gap this parser's grammar can produce — the widest possible
 * spacing between two Feb-29 leap days is 8 years (e.g. 1896 -> 1904, the
 * classic centurial-exception gap: 1900 is NOT a leap year), i.e. ~2922
 * days — while still guaranteeing termination (via a thrown Error, not an
 * infinite loop) for genuinely impossible schedules such as
 * '0 0 30 2 *' (February never has a 30th day, at any year, ever).
 *
 * Zero runtime dependencies; CommonJS only (package.json / T-044 contract).
 * require('./vectors') is used ONLY inside the require.main self-check
 * guard at the bottom of this file — never for the exported implementation.
 */

const SAFETY_CAP_DAYS = 3660;

// ---------------------------------------------------------------------------
// Calendar-correct carry helpers. daysInMonth/addOneDay/addOneMinute lean on
// Date.UTC's own month/day normalization (passing day 0 of the FOLLOWING
// month yields the last day of the target month) so leap years and
// variable month lengths never need manual special-casing.
// ---------------------------------------------------------------------------

/** Number of days in UTC month `month` (1-12) of `year`. */
function daysInMonth(year, month) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** Advance a {year, month, day} triple by exactly one calendar day. */
function addOneDay(year, month, day) {
  let y = year;
  let mo = month;
  let d = day + 1;
  const dim = daysInMonth(y, mo);
  if (d > dim) {
    d = 1;
    mo += 1;
    if (mo > 12) {
      mo = 1;
      y += 1;
    }
  }
  return { year: y, month: mo, day: d };
}

/** Advance a full {year, month, day, hour, minute} by exactly one minute. */
function addOneMinute(year, month, day, hour, minute) {
  let h = hour;
  let mi = minute + 1;
  if (mi > 59) {
    mi = 0;
    h += 1;
  }
  if (h > 23) {
    h = 0;
    const carried = addOneDay(year, month, day);
    return { year: carried.year, month: carried.month, day: carried.day, hour: h, minute: mi };
  }
  return { year, month, day, hour: h, minute: mi };
}

/** Ascending-sorted array of a Set<int>. */
function sortedOf(set) {
  return Array.from(set).sort((a, b) => a - b);
}

/** Smallest element of sortedArr that is >= x, or null if none. */
function smallestAtLeast(sortedArr, x) {
  for (const v of sortedArr) {
    if (v >= x) return v;
  }
  return null;
}

/** Smallest element of sortedArr that is > x, or null if none. */
function smallestGreaterThan(sortedArr, x) {
  for (const v of sortedArr) {
    if (v > x) return v;
  }
  return null;
}

/**
 * nextOccurrences(parsed, fromDate, count) -> Date[]
 * See file header + candidates/vectors.js INTERFACE_DOC for the full
 * contract.
 */
function nextOccurrences(parsed, fromDate, count) {
  const { fields, domRestricted, dowRestricted } = parsed;
  const minuteSet = fields.minute;
  const hourSet = fields.hour;
  const monthSet = fields.month;
  const domSet = fields.dayOfMonth;
  const dowSet = fields.dayOfWeek;

  const minutesSorted = sortedOf(minuteSet);
  const hoursSorted = sortedOf(hourSet);

  /**
   * DOM/DOW OR-coupling predicate for a single calendar day (does NOT
   * check the month field — callers combine it with monthSet.has(month)).
   */
  function dayOfMonthDowMatches(year, month, day) {
    if (domRestricted && dowRestricted) {
      const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
      return domSet.has(day) || dowSet.has(dow);
    }
    if (domRestricted) {
      return domSet.has(day);
    }
    if (dowRestricted) {
      const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
      return dowSet.has(dow);
    }
    return true;
  }

  function isValidDay(year, month, day) {
    return monthSet.has(month) && dayOfMonthDowMatches(year, month, day);
  }

  /**
   * Within a day already known to be valid, find the next {hour, minute}
   * such that: if hourLB is itself in hourSet and minuteLB !== null, a
   * minute >= minuteLB in minuteSet is preferred; otherwise the smallest
   * hour strictly greater than hourLB (with its smallest valid minute) is
   * used. Pass hourLB = -1, minuteLB = null to mean "any time of day"
   * (returns the day's overall smallest {hour, minute}).
   * Returns null if no qualifying time remains in the day.
   */
  function findTimeInDay(hourLB, minuteLB) {
    if (minuteLB !== null && hourSet.has(hourLB)) {
      const m = smallestAtLeast(minutesSorted, minuteLB);
      if (m !== null) {
        return { hour: hourLB, minute: m };
      }
    }
    const nextHour = smallestGreaterThan(hoursSorted, hourLB);
    if (nextHour !== null) {
      return { hour: nextHour, minute: minutesSorted[0] };
    }
    return null;
  }

  /**
   * Carry day-by-day (bounded by SAFETY_CAP_DAYS) to the next valid day
   * STRICTLY AFTER (year, month, day). Throws if the cap is exhausted.
   */
  function nextValidDayAfter(year, month, day) {
    let { year: cy, month: cm, day: cd } = addOneDay(year, month, day);
    for (let i = 0; i < SAFETY_CAP_DAYS; i += 1) {
      if (isValidDay(cy, cm, cd)) {
        return { year: cy, month: cm, day: cd };
      }
      ({ year: cy, month: cm, day: cd } = addOneDay(cy, cm, cd));
    }
    throw new Error(
      `cronsplain schedule_b: no valid day found within ${SAFETY_CAP_DAYS} ` +
        `day-carries starting after ${year}-${month}-${day} (schedule is ` +
        'likely impossible, e.g. a day-of-month that never exists in the ' +
        "given month, such as '0 0 30 2 *')"
    );
  }

  const results = [];

  // Lower bound: the first minute-aligned instant strictly after fromDate.
  let y = fromDate.getUTCFullYear();
  let mo = fromDate.getUTCMonth() + 1;
  let d = fromDate.getUTCDate();
  let h = fromDate.getUTCHours();
  let mi = fromDate.getUTCMinutes();
  ({ year: y, month: mo, day: d, hour: h, minute: mi } = addOneMinute(y, mo, d, h, mi));

  for (let i = 0; i < count; i += 1) {
    let found = null;
    if (isValidDay(y, mo, d)) {
      found = findTimeInDay(h, mi);
    }
    if (!found) {
      const nextDay = nextValidDayAfter(y, mo, d);
      y = nextDay.year;
      mo = nextDay.month;
      d = nextDay.day;
      found = findTimeInDay(-1, null);
      if (!found) {
        // Cannot happen: nextValidDayAfter only returns days where
        // monthSet/domSet/dowSet already permit SOME hour/minute, since
        // hourSet/minuteSet are always non-empty for a parsed field.
        throw new Error('cronsplain schedule_b: internal invariant violated (valid day with no valid time)');
      }
    }
    h = found.hour;
    mi = found.minute;
    results.push(new Date(Date.UTC(y, mo - 1, d, h, mi, 0, 0)));

    ({ year: y, month: mo, day: d, hour: h, minute: mi } = addOneMinute(y, mo, d, h, mi));
  }

  return results;
}

module.exports = { nextOccurrences };

// ---------------------------------------------------------------------------
// Self-check: run standalone with `node candidates/schedule_b.js`. Scores
// this candidate's nextOccurrences against the golden VECTORS (T-046).
// require('./vectors') happens ONLY inside this guard.
// ---------------------------------------------------------------------------
if (require.main === module) {
  const { runAgainst } = require('./vectors');
  const result = runAgainst(nextOccurrences);
  console.log(`schedule_b self-check: passed=${result.passed} total=${result.total}`);
  if (result.failures.length > 0) {
    console.log(JSON.stringify(result.failures, null, 2));
  }
  process.exit(result.passed === result.total ? 0 : 1);
}
