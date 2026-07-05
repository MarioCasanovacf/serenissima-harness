'use strict';

const { parse } = require('../lib/parser');

/**
 * candidates/vectors.js — cronsplain schedule tournament: candidate-agnostic
 * golden vectors (T-046).
 *
 * This module is authored BEFORE any candidate exists (T-047/T-048) and
 * imports NO candidate implementation — only the VERIFIED `../lib/parser`
 * (T-045), to turn each vector's cron expression into the pinned ParsedCron
 * shape:
 *
 *   {
 *     fields: {
 *       minute: Set<int>, hour: Set<int>, dayOfMonth: Set<int>,
 *       month: Set<int>, dayOfWeek: Set<int>,
 *     },
 *     domRestricted: boolean,  // raw dayOfMonth text !== '*'
 *     dowRestricted: boolean,  // raw dayOfWeek text !== '*'
 *     source: string,
 *   }
 *
 * ---------------------------------------------------------------------------
 * INTERFACE (every schedule candidate — T-047 brute-force minute-tick,
 * T-048 field-cascade carry-increment, and the promoted lib/schedule.js —
 * MUST implement exactly this):
 *
 *   nextOccurrences(parsed, fromDate, count) -> Date[]
 *
 *   - `parsed` is a ParsedCron object as returned by require('../lib/parser')
 *     .parse(expr) (see shape above). Candidates read parsed.fields.* Sets
 *     and the two *Restricted booleans; they never re-parse a string.
 *   - `fromDate` is a JS Date. All matching is performed against fromDate's
 *     UTC calendar fields (getUTCFullYear/getUTCMonth/getUTCDate/
 *     getUTCHours/getUTCMinutes) — this module never uses local-time
 *     getters, and neither should a conforming candidate.
 *   - `count` is a positive integer: the number of occurrences to return.
 *   - Returns an array of exactly `count` `Date` objects, each:
 *       * UTC — constructed via Date.UTC(...) (or equivalent) so
 *         toISOString() always ends in '.000Z'.
 *       * minute-aligned — seconds === 0 and milliseconds === 0.
 *       * STRICTLY AFTER fromDate — EXCLUSIVE. If fromDate itself lands
 *         exactly on a minute that satisfies `parsed`, that minute is NOT
 *         returned; the first result is the next later matching minute.
 *       * in ascending order (result[i] < result[i+1] for all i).
 *   - DOM/DOW OR-coupling (the classic Vixie quirk, pinned by lib/parser.js
 *     and re-stated here because it is THE thing that trips up naive
 *     implementations): a candidate day D (given D's day-of-month and D's
 *     day-of-week) is a MATCHING DAY iff:
 *       * parsed.domRestricted && parsed.dowRestricted:
 *           D matches iff dayOfMonth(D) is in parsed.fields.dayOfMonth
 *           OR dayOfWeek(D) is in parsed.fields.dayOfWeek (UNION — a day
 *           that matches only one of the two fields still counts).
 *       * exactly one of domRestricted/dowRestricted is true:
 *           D matches iff that single field's Set contains D's value; the
 *           OTHER field's Set (which is the field's full wildcard range,
 *           since it is unrestricted) is NOT consulted at all.
 *       * neither is restricted (both fields are '*'):
 *           every day matches (day is not a constraint).
 *     Minute/hour/month always constrain independently (plain Set
 *     membership on parsed.fields.minute / .hour / .month) regardless of
 *     domRestricted/dowRestricted.
 * ---------------------------------------------------------------------------
 *
 * GROUND TRUTH: every VECTORS[i].expected array below was hand-computed
 * against real cron/Gregorian-calendar semantics (weekday-of-date, leap
 * years, month lengths) and is annotated inline with the rule it exercises.
 * Day-of-week arithmetic used throughout this file's comments: 2026-01-01
 * is a Thursday (verified: 2024-01-01 is a Monday [known anchor]; 2024 is a
 * leap year so 2024-01-01 -> 2025-01-01 is +366 days, 366 mod 7 = 2, so
 * 2025-01-01 = Monday+2 = Wednesday; 2025 is not a leap year so
 * 2025-01-01 -> 2026-01-01 is +365 days, 365 mod 7 = 1, so
 * 2026-01-01 = Wednesday+1 = Thursday). From that anchor, for any date in
 * 2026, dow = (3 + dayOfYear) mod 7 with Sunday=0..Saturday=6 (dayOfYear
 * counted from 1 for Jan 1st) — this closed form is used to independently
 * derive every Friday/Monday/Saturday cited below, and is ALSO
 * cross-checked mechanically against a throwaway (unshipped) reference
 * implementation before this file was finalized (see the handoff note for
 * T-046 for the disclosure of that self-check — it is NOT part of this
 * module and is NOT required to ship).
 *
 * DAYS-OF-WEEK USED BELOW (each independently derivable from the closed
 * form above; listed here once for cross-reference):
 *   2026-07-01 Wed   2026-07-03 Fri   2026-07-04 Sat   2026-07-06 Mon
 *   2026-07-10 Fri   2026-07-13 Mon   2026-07-17 Fri   2026-07-20 Mon
 *   2026-07-24 Fri   2026-07-27 Mon   2026-07-31 Fri   2026-08-01 Sat
 *
 * MODULE EXPORTS: { VECTORS, runAgainst, INTERFACE_DOC }.
 *
 * Zero runtime dependencies; CommonJS only (package.json / T-044 contract).
 */

const INTERFACE_DOC =
  'nextOccurrences(parsed, fromDate, count) -> Date[]: returns the next ' +
  '`count` UTC Date objects (seconds=0, ms=0) whose minute satisfies ' +
  '`parsed` (the ParsedCron shape from require(\'../lib/parser\').parse), ' +
  'each STRICTLY AFTER fromDate (exclusive — a fromDate landing exactly on ' +
  'a matching minute is skipped), in ascending order. DOM/DOW coupling: ' +
  'when parsed.domRestricted && parsed.dowRestricted, a day matches if ' +
  'dayOfMonth OR dayOfWeek matches (union); when exactly one is ' +
  'restricted, only that field constrains the day; when neither is ' +
  'restricted, every day matches. Minute/hour/month always constrain via ' +
  'plain Set membership on parsed.fields.{minute,hour,month} regardless ' +
  'of DOM/DOW restriction state.';

// ---------------------------------------------------------------------------
// VECTORS: ground-truth cases. Each: { expr, from (ISO-Z), count, expected
// (array of ISO-Z strings) }. See the inline `//` citation above each entry
// for the specific rule it pins down.
// ---------------------------------------------------------------------------
const VECTORS = [
  {
    // (a) SIMPLE STEP: '*/15' expands to {0,15,30,45}; hour/day/month/dow
    // all '*'. `from` (00:05) is NOT itself a match, so this is a plain
    // forward-scan case with no exclusivity subtlety — isolates step
    // expansion from the exclusive-boundary rule (see vector 2 for that).
    expr: '*/15 * * * *',
    from: '2026-07-04T00:05:00Z',
    count: 3,
    expected: [
      '2026-07-04T00:15:00.000Z', // next multiple of 15 after :05
      '2026-07-04T00:30:00.000Z',
      '2026-07-04T00:45:00.000Z',
    ],
  },
  {
    // (b) DAILY + EXCLUSIVITY: '0 0 * * *' fires once a day at 00:00.
    // `from` is set to EXACTLY 2026-07-04T00:00:00Z, a minute that itself
    // satisfies the expression. Per the exclusive-boundary rule the
    // matching `from` minute itself must NOT be returned — the first
    // result is the FOLLOWING day's midnight, not the same one.
    expr: '0 0 * * *',
    from: '2026-07-04T00:00:00Z',
    count: 3,
    expected: [
      '2026-07-05T00:00:00.000Z', // NOT 07-04T00:00 (from IS excluded)
      '2026-07-06T00:00:00.000Z',
      '2026-07-07T00:00:00.000Z',
    ],
  },
  {
    // (c) MONTH ROLLOVER: day 28 exists in every month (safe from the
    // short-month edge, isolating pure month-boundary carry). `from` is
    // exactly on the July 28 00:00 match (also reinforces exclusivity),
    // so the first result must roll into August, then September.
    expr: '0 0 28 * *',
    from: '2026-07-28T00:00:00Z',
    count: 2,
    expected: [
      '2026-08-28T00:00:00.000Z', // dayOfMonth carries the month forward
      '2026-09-28T00:00:00.000Z',
    ],
  },
  {
    // (d) YEAR ROLLOVER: '0 0 1 1 *' fires once a year, Jan 1 00:00.
    // `from` = Dec 31 2025 12:00 (not a match); the month field must
    // carry from 12 back to 1 AND increment the year: Dec 31 -> Jan 1
    // of the FOLLOWING year, then wrap again a full year later.
    expr: '0 0 1 1 *',
    from: '2025-12-31T12:00:00Z',
    count: 2,
    expected: [
      '2026-01-01T00:00:00.000Z', // year rolls 2025 -> 2026
      '2027-01-01T00:00:00.000Z', // and again 2026 -> 2027
    ],
  },
  {
    // (e) LEAP FEB 29: '0 0 29 2 *' can ONLY be satisfied in a leap year
    // (Feb has 29 days only then). From 2023-01-01, the nearest Feb 29 is
    // 2024 (2024 % 4 === 0, not a centurial exception -> leap); 2025,
    // 2026, 2027 are NOT leap (no Feb 29 exists in those years at all, so
    // they contribute zero candidate days, not a skip-and-retry glitch);
    // the next hit after 2024 is 2028 (again % 4 === 0 -> leap).
    expr: '0 0 29 2 *',
    from: '2023-01-01T00:00:00Z',
    count: 2,
    expected: [
      '2024-02-29T00:00:00.000Z', // 2024 is a leap year
      '2028-02-29T00:00:00.000Z', // skips non-leap 2025,2026,2027 entirely
    ],
  },
  {
    // (f-1) DOM/DOW OR QUIRK ("13th OR Friday"): '0 0 13 * 5' has BOTH
    // dayOfMonth={13} and dayOfWeek={5=Fri} restricted, so a day matches
    // if it is the 13th OR a Friday (union), independent of each other.
    // Within July 2026: Fridays fall on 3,10,17,24,31 (dow-only matches)
    // and the 13th falls on a MONDAY (dom-only match, included even
    // though it is not a Friday) — this single vector proves the union
    // includes a day that satisfies EACH field alone, not just their
    // intersection (which would wrongly drop July 13).
    expr: '0 0 13 * 5',
    from: '2026-07-01T00:00:00Z',
    count: 6,
    expected: [
      '2026-07-03T00:00:00.000Z', // Friday (dow-only match)
      '2026-07-10T00:00:00.000Z', // Friday (dow-only match)
      '2026-07-13T00:00:00.000Z', // 13th, a MONDAY (dom-only match)
      '2026-07-17T00:00:00.000Z', // Friday (dow-only match)
      '2026-07-24T00:00:00.000Z', // Friday (dow-only match)
      '2026-07-31T00:00:00.000Z', // Friday (dow-only match)
    ],
  },
  {
    // (f-2) DOM/DOW OR QUIRK ("1st OR Monday") + EXCLUSIVITY: '0 0 1 * 1'
    // has dayOfMonth={1} and dayOfWeek={1=Mon} both restricted. `from` is
    // set to EXACTLY 2026-07-01T00:00:00Z — July 1 IS the 1st of the
    // month, so it satisfies the union even though July 1 is a
    // Wednesday, not a Monday. Because `from` lands exactly on that
    // matching minute, exclusivity requires it be skipped: the first
    // result is the next Monday (July 6), not July 1 itself. The
    // sequence then includes every Monday in July (6,13,20,27) plus the
    // next 1st-of-month (Aug 1, a SATURDAY — dom-only match, proving the
    // union again pulls in a day satisfying only the other field).
    expr: '0 0 1 * 1',
    from: '2026-07-01T00:00:00Z',
    count: 5,
    expected: [
      '2026-07-06T00:00:00.000Z', // Monday (dow-only match)
      '2026-07-13T00:00:00.000Z', // Monday (dow-only match)
      '2026-07-20T00:00:00.000Z', // Monday (dow-only match)
      '2026-07-27T00:00:00.000Z', // Monday (dow-only match)
      '2026-08-01T00:00:00.000Z', // 1st, a SATURDAY (dom-only match)
    ],
  },
  {
    // (g-1) ONE-FIELD-* CASE, dom restricted / dow wildcard: '0 0 15 * *'
    // has dayOfMonth={15} restricted but dayOfWeek='*' (NOT restricted),
    // so per the coupling rule ONLY dayOfMonth constrains the day — the
    // day-of-week of the 15th is irrelevant and is never consulted.
    // Fires on the 15th of every month regardless of weekday.
    expr: '0 0 15 * *',
    from: '2026-01-01T00:00:00Z',
    count: 3,
    expected: [
      '2026-01-15T00:00:00.000Z',
      '2026-02-15T00:00:00.000Z',
      '2026-03-15T00:00:00.000Z',
    ],
  },
  {
    // (g-2) ONE-FIELD-* CASE, dow restricted / dom wildcard: '0 9 * * 1-5'
    // has dayOfWeek={1,2,3,4,5} (Mon-Fri) restricted but dayOfMonth='*'
    // (NOT restricted), so ONLY dayOfWeek constrains the day (weekdays,
    // any date). `from` = Sat 2026-07-04; the next 5 weekdays are
    // Mon 7/6 .. Fri 7/10 (Saturday/Sunday 7/4-7/5 are skipped entirely).
    expr: '0 9 * * 1-5',
    from: '2026-07-04T00:00:00Z',
    count: 5,
    expected: [
      '2026-07-06T09:00:00.000Z', // Monday
      '2026-07-07T09:00:00.000Z', // Tuesday
      '2026-07-08T09:00:00.000Z', // Wednesday
      '2026-07-09T09:00:00.000Z', // Thursday
      '2026-07-10T09:00:00.000Z', // Friday (weekend 7/4-7/5 skipped)
    ],
  },
  {
    // (bonus) END-OF-MONTH SKIP: '0 0 31 * *' can only fire in months
    // that actually have a 31st (Jan,Mar,May,Jul,Aug,Oct,Dec); short
    // months (Feb,Apr,Jun,Sep,Nov) contribute zero candidate days and
    // must be skipped outright, not rounded down to a shorter month's
    // last day. `from` is exactly on the Jan 31 match (exclusivity
    // reinforced again), so results skip Feb/Apr and land on the next
    // three 31-day months: Mar, May, Jul.
    expr: '0 0 31 * *',
    from: '2026-01-31T00:00:00Z',
    count: 3,
    expected: [
      '2026-03-31T00:00:00.000Z', // Feb has no 31st -> skipped entirely
      '2026-05-31T00:00:00.000Z', // Apr has no 31st -> skipped entirely
      '2026-07-31T00:00:00.000Z',
    ],
  },
  {
    // (bonus) STEP ACROSS A RANGE + daily rollover: '0 9-17/4 * * *'
    // expands hour to a-b/n starting at 9: {9,13,17} (9, 9+4=13,
    // 13+4=17; 17+4=21 > 17 so stops). Same three hours fire every day;
    // after the last slot of a day (17:00) the next match rolls to the
    // FOLLOWING day's first slot (09:00), not later the same day.
    expr: '0 9-17/4 * * *',
    from: '2026-07-04T00:00:00Z',
    count: 4,
    expected: [
      '2026-07-04T09:00:00.000Z',
      '2026-07-04T13:00:00.000Z',
      '2026-07-04T17:00:00.000Z',
      '2026-07-05T09:00:00.000Z', // day rolls over after the 17:00 slot
    ],
  },
];

/**
 * Score `nextOccurrencesFn` against every VECTOR in this module.
 *
 * `nextOccurrencesFn` must conform to the interface documented above:
 * nextOccurrences(parsed, fromDate, count) -> Date[]. Imports NO candidate
 * module itself — the caller supplies the function.
 *
 * @param {(parsed: object, fromDate: Date, count: number) => Date[]} nextOccurrencesFn
 * @returns {{passed: number, total: number, failures: Array<{expr: string, expected: string[], got: string[]}>}}
 */
function runAgainst(nextOccurrencesFn) {
  let passed = 0;
  const total = VECTORS.length;
  const failures = [];

  for (const vector of VECTORS) {
    const parsed = parse(vector.expr);
    const fromDate = new Date(vector.from);
    const resultDates = nextOccurrencesFn(parsed, fromDate, vector.count);
    const got = (resultDates || []).map((d) => d.toISOString());

    const matches =
      got.length === vector.expected.length &&
      got.every((iso, i) => iso === vector.expected[i]);

    if (matches) {
      passed += 1;
    } else {
      failures.push({ expr: vector.expr, expected: vector.expected, got });
    }
  }

  return { passed, total, failures };
}

// ---------------------------------------------------------------------------
// Structural self-check: run standalone with `node candidates/vectors.js`.
// Validates only the SHAPE and internal consistency of the golden data
// (parseable expressions, well-formed ISO strings, non-empty coverage) —
// it does NOT run any candidate (none exists yet at T-046 time).
// ---------------------------------------------------------------------------
function selfCheck() {
  if (VECTORS.length === 0) {
    throw new Error('VECTORS must not be empty');
  }

  const isoZRe = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
  let totalExpected = 0;

  for (const vector of VECTORS) {
    if (typeof vector.expr !== 'string' || vector.expr.length === 0) {
      throw new Error(`vector missing expr: ${JSON.stringify(vector)}`);
    }
    // Must be parseable by the real, verified parser (no candidate needed).
    const parsed = parse(vector.expr);
    if (
      !parsed ||
      typeof parsed.domRestricted !== 'boolean' ||
      typeof parsed.dowRestricted !== 'boolean'
    ) {
      throw new Error(`parse() returned an unexpected shape for '${vector.expr}'`);
    }

    if (typeof vector.from !== 'string' || Number.isNaN(new Date(vector.from).getTime())) {
      throw new Error(`vector has invalid from: ${JSON.stringify(vector)}`);
    }
    if (!Number.isInteger(vector.count) || vector.count <= 0) {
      throw new Error(`vector has invalid count: ${JSON.stringify(vector)}`);
    }
    if (!Array.isArray(vector.expected) || vector.expected.length !== vector.count) {
      throw new Error(
        `vector expected.length (${vector.expected && vector.expected.length}) ` +
          `!== count (${vector.count}) for '${vector.expr}'`
      );
    }
    for (const iso of vector.expected) {
      if (typeof iso !== 'string' || !isoZRe.test(iso)) {
        throw new Error(`vector expected entry is not a minute-aligned ISO-Z string: ${iso}`);
      }
      totalExpected += 1;
    }
    // ascending order
    for (let i = 1; i < vector.expected.length; i += 1) {
      if (!(vector.expected[i] > vector.expected[i - 1])) {
        throw new Error(
          `vector expected array not strictly ascending for '${vector.expr}': ` +
            `${vector.expected[i - 1]} then ${vector.expected[i]}`
        );
      }
    }
    // exclusivity sanity: no expected entry may equal `from` verbatim.
    const fromIso = new Date(vector.from).toISOString();
    if (vector.expected.includes(fromIso)) {
      throw new Error(
        `vector for '${vector.expr}' includes fromDate itself (${fromIso}) in expected — ` +
          'violates the strictly-after exclusivity rule'
      );
    }
  }

  console.log('cronsplain schedule golden vectors (T-046) -- self-check OK');
  console.log(`  VECTORS (cases):            ${VECTORS.length}`);
  console.log(`  expected occurrences total: ${totalExpected}`);
  console.log('  categories: step, daily+exclusivity, month rollover, year rollover,');
  console.log('    leap Feb-29, DOM/DOW OR quirk x2, one-field-* x2, end-of-month skip,');
  console.log('    step-across-range');
}

module.exports = { VECTORS, runAgainst, INTERFACE_DOC };

if (require.main === module) {
  selfCheck();
}
