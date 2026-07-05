'use strict';

const { test } = require('node:test');
const assert = require('node:assert');

const { parse } = require('../lib/parser');
const { CronParseError } = require('../lib/errors');

function setOf(arr) {
  return new Set(arr);
}

function fullRange(min, max) {
  const out = [];
  for (let i = min; i <= max; i += 1) out.push(i);
  return out;
}

// ---------------------------------------------------------------------------
// Per-field syntax: single value, range, step, list, wildcard
// ---------------------------------------------------------------------------

test('single value per field', () => {
  const p = parse('5 10 15 6 3');
  assert.deepStrictEqual(p.fields.minute, setOf([5]));
  assert.deepStrictEqual(p.fields.hour, setOf([10]));
  assert.deepStrictEqual(p.fields.dayOfMonth, setOf([15]));
  assert.deepStrictEqual(p.fields.month, setOf([6]));
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf([3]));
});

test('range a-b', () => {
  const p = parse('0 9-17 * * *');
  assert.deepStrictEqual(p.fields.hour, setOf(fullRange(9, 17)));
});

test('step */n over the wildcard range', () => {
  const p = parse('*/15 * * * *');
  assert.deepStrictEqual(p.fields.minute, setOf([0, 15, 30, 45]));
});

test('step a-b/n over an explicit range', () => {
  const p = parse('0 0-20/5 * * *');
  assert.deepStrictEqual(p.fields.hour, setOf([0, 5, 10, 15, 20]));
});

test('comma list combining value, range, and range-step', () => {
  const p = parse('5,10-12,20-40/10 * * * *');
  // 5 ; 10,11,12 ; 20,30,40 (a-b/n range-step, NOT the bare "a/n" form)
  assert.deepStrictEqual(
    p.fields.minute,
    setOf([5, 10, 11, 12, 20, 30, 40])
  );
});

test('wildcard expands to the full [min,max] range for every field', () => {
  const p = parse('* * * * *');
  assert.deepStrictEqual(p.fields.minute, setOf(fullRange(0, 59)));
  assert.deepStrictEqual(p.fields.hour, setOf(fullRange(0, 23)));
  assert.deepStrictEqual(p.fields.dayOfMonth, setOf(fullRange(1, 31)));
  assert.deepStrictEqual(p.fields.month, setOf(fullRange(1, 12)));
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf(fullRange(0, 6)));
});

// ---------------------------------------------------------------------------
// Names: month JAN-DEC, dayOfWeek SUN-SAT, case-insensitivity, name ranges
// ---------------------------------------------------------------------------

test('month names resolve to 1-12 and are usable in a list', () => {
  const p = parse('0 0 1 JAN,MAR,DEC *');
  assert.deepStrictEqual(p.fields.month, setOf([1, 3, 12]));
});

test('month names are case-insensitive', () => {
  const lower = parse('0 0 1 jan,mar,dec *');
  const mixed = parse('0 0 1 Jan,Mar,Dec *');
  assert.deepStrictEqual(lower.fields.month, setOf([1, 3, 12]));
  assert.deepStrictEqual(mixed.fields.month, setOf([1, 3, 12]));
});

test('dayOfWeek names resolve to 0-6 (SUN=0) and are case-insensitive', () => {
  const p = parse('0 0 * * sun,Wed,SAT');
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf([0, 3, 6]));
});

test('name ranges: MON-FRI and JAN-MAR', () => {
  const dow = parse('0 0 * * MON-FRI');
  assert.deepStrictEqual(dow.fields.dayOfWeek, setOf([1, 2, 3, 4, 5]));

  const month = parse('0 0 1 JAN-MAR *');
  assert.deepStrictEqual(month.fields.month, setOf([1, 2, 3]));
});

// ---------------------------------------------------------------------------
// dayOfWeek 7 -> 0 aliasing
// ---------------------------------------------------------------------------

test('dayOfWeek 7 normalizes to 0', () => {
  const p = parse('0 0 * * 7');
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf([0]));
});

test('dayOfWeek 0 and 7 both present collapse to a single 0 entry', () => {
  const p = parse('0 0 * * 0,7');
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf([0]));
  assert.strictEqual(p.fields.dayOfWeek.size, 1);
});

test('dayOfWeek range 5-7 normalizes the 7 endpoint to 0', () => {
  const p = parse('0 0 * * 5-7');
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf([5, 6, 0]));
});

// ---------------------------------------------------------------------------
// domRestricted / dowRestricted flags
// ---------------------------------------------------------------------------

test('domRestricted/dowRestricted are both false for the all-wildcard expression', () => {
  const p = parse('* * * * *');
  assert.strictEqual(p.domRestricted, false);
  assert.strictEqual(p.dowRestricted, false);
});

test('domRestricted true, dowRestricted false when only dayOfMonth is restricted', () => {
  const p = parse('0 0 15 * *');
  assert.strictEqual(p.domRestricted, true);
  assert.strictEqual(p.dowRestricted, false);
});

test('domRestricted false, dowRestricted true when only dayOfWeek is restricted', () => {
  const p = parse('*/15 0 * * 1-5');
  assert.strictEqual(p.domRestricted, false);
  assert.strictEqual(p.dowRestricted, true);
});

test('both domRestricted and dowRestricted true when neither field is a bare wildcard', () => {
  const p = parse('0 0 1,15 * MON');
  assert.strictEqual(p.domRestricted, true);
  assert.strictEqual(p.dowRestricted, true);
});

// ---------------------------------------------------------------------------
// Full expanded-Set correctness for a couple of complete expressions
// ---------------------------------------------------------------------------

test('expanded sets for a full multi-field expression', () => {
  const p = parse('0 12 1,15 * *');
  assert.deepStrictEqual(p.fields.minute, setOf([0]));
  assert.deepStrictEqual(p.fields.hour, setOf([12]));
  assert.deepStrictEqual(p.fields.dayOfMonth, setOf([1, 15]));
  assert.deepStrictEqual(p.fields.month, setOf(fullRange(1, 12)));
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf(fullRange(0, 6)));
  assert.strictEqual(p.source, '0 12 1,15 * *');
});

test('expanded sets for a second full multi-field expression (names + step + list)', () => {
  const p = parse('*/20 9-17 * 1,6,12 MON,WED,FRI');
  assert.deepStrictEqual(p.fields.minute, setOf([0, 20, 40]));
  assert.deepStrictEqual(p.fields.hour, setOf(fullRange(9, 17)));
  assert.deepStrictEqual(p.fields.dayOfMonth, setOf(fullRange(1, 31)));
  assert.deepStrictEqual(p.fields.month, setOf([1, 6, 12]));
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf([1, 3, 5]));
  assert.strictEqual(p.domRestricted, false);
  assert.strictEqual(p.dowRestricted, true);
});

// ---------------------------------------------------------------------------
// Boundary values
// ---------------------------------------------------------------------------

test('boundary values at each field min/max are accepted', () => {
  assert.deepStrictEqual(parse('0 0 1 1 0').fields.minute, setOf([0]));
  assert.deepStrictEqual(parse('59 23 31 12 6').fields.minute, setOf([59]));
  const p = parse('59 23 31 12 6');
  assert.deepStrictEqual(p.fields.hour, setOf([23]));
  assert.deepStrictEqual(p.fields.dayOfMonth, setOf([31]));
  assert.deepStrictEqual(p.fields.month, setOf([12]));
  assert.deepStrictEqual(p.fields.dayOfWeek, setOf([6]));
  // dayOfWeek upper bound alias 7 (-> 0) also accepted, see the 7->0 tests above.
});

// ---------------------------------------------------------------------------
// source field
// ---------------------------------------------------------------------------

test('source carries the original, unmodified expression string', () => {
  const expr = '  */5 * * * *  ';
  const p = parse(expr);
  assert.strictEqual(p.source, expr);
});

// ---------------------------------------------------------------------------
// VERIFY command from the acceptance criteria (pinned regression)
// ---------------------------------------------------------------------------

test('acceptance-criteria VERIFY expression matches the pinned output', () => {
  const p = parse('*/15 0 * * 1-5');
  assert.strictEqual(p.fields.minute.size, 4);
  assert.strictEqual(p.domRestricted, false);
  assert.strictEqual(p.dowRestricted, true);
});

// ---------------------------------------------------------------------------
// INVALID INPUT TABLE — every entry must throw CronParseError
// ---------------------------------------------------------------------------

const INVALID_CASES = [
  { label: 'wrong field count (4 fields)', expr: '* * * *' },
  { label: 'wrong field count (6 fields)', expr: '* * * * * *' },
  { label: 'out-of-range minute (60)', expr: '60 0 * * *', field: 'minute' },
  {
    label: 'out-of-range dayOfWeek (8)',
    expr: '0 0 * * 8',
    field: 'dayOfWeek',
  },
  {
    label: 'reversed range (10-5)',
    expr: '0 0 10-5 * *',
    field: 'dayOfMonth',
  },
  { label: 'step of zero (*/0)', expr: '*/0 * * * *', field: 'minute' },
  {
    label: 'non-integer/negative step (*/-5)',
    expr: '*/-5 * * * *',
    field: 'minute',
  },
  { label: 'Vixie macro (@daily)', expr: '@daily' },
  {
    label: 'Vixie last-day-of-month (L)',
    expr: '0 0 L * *',
    field: 'dayOfMonth',
  },
  {
    label: 'Vixie nearest-weekday (15W)',
    expr: '0 0 15W * *',
    field: 'dayOfMonth',
  },
  {
    label: 'Vixie nth-weekday (MON#2)',
    expr: '0 0 * * MON#2',
    field: 'dayOfWeek',
  },
  { label: 'Vixie unspecified (?)', expr: '0 0 ? * *', field: 'dayOfMonth' },
  {
    label: 'bare Vixie start-step form (3/5)',
    expr: '3/5 * * * *',
    field: 'minute',
  },
  { label: 'unknown month name', expr: '0 0 * FOO *', field: 'month' },
  {
    label: 'empty list element (middle)',
    expr: '1,,5 0 * * *',
    field: 'minute',
  },
  {
    label: 'empty list element (trailing comma)',
    expr: '0 0 * * 1,2,',
    field: 'dayOfWeek',
  },
  {
    label: 'empty list element (leading comma)',
    expr: '0 0 * * ,1,2',
    field: 'dayOfWeek',
  },
  { label: 'trailing garbage on a value (5x)', expr: '5x 0 * * *', field: 'minute' },
  {
    label: 'too many step separators (1-5/2/3)',
    expr: '1-5/2/3 0 * * *',
    field: 'minute',
  },
  {
    label: 'malformed range (1-5-10)',
    expr: '1-5-10 0 * * *',
    field: 'minute',
  },
  {
    label: 'reversed name range (FRI-MON)',
    expr: '0 0 * * FRI-MON',
    field: 'dayOfWeek',
  },
  { label: 'empty expression string', expr: '' },
  { label: 'whitespace-only expression string', expr: '   ' },
];

test(`invalid-input table: ${INVALID_CASES.length} cases each throw CronParseError`, () => {
  assert.ok(
    INVALID_CASES.length >= 8,
    'invalid-input table must cover at least 8 cases'
  );
  for (const { label, expr, field } of INVALID_CASES) {
    assert.throws(
      () => parse(expr),
      (err) => {
        assert.ok(
          err instanceof CronParseError,
          `[${label}] expected CronParseError, got ${err}`
        );
        assert.strictEqual(
          err.expression,
          expr,
          `[${label}] expected .expression to be the original input`
        );
        if (field !== undefined) {
          assert.strictEqual(
            err.field,
            field,
            `[${label}] expected .field to be '${field}', got '${err.field}'`
          );
        }
        return true;
      },
      `[${label}] parse('${expr}') should throw CronParseError`
    );
  }
});

test('non-string input throws CronParseError', () => {
  assert.throws(() => parse(null), CronParseError);
  assert.throws(() => parse(undefined), CronParseError);
  assert.throws(() => parse(12345), CronParseError);
});
