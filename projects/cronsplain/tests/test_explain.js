'use strict';

const { test } = require('node:test');
const assert = require('node:assert');

const { explain, explainParsed } = require('../lib/explain');
const { parse } = require('../lib/parser');
const { CronParseError } = require('../lib/errors');

// ---------------------------------------------------------------------------
// explain() composes parse() + explainParsed() — verify they agree.
// ---------------------------------------------------------------------------

test('explain(expr) === explainParsed(parse(expr)) for a representative expression', () => {
  const expr = '*/15 0 * * *';
  assert.strictEqual(explain(expr), explainParsed(parse(expr)));
});

// ---------------------------------------------------------------------------
// Pinned acceptance-criteria exact-sentence cases
// ---------------------------------------------------------------------------

test("'* * * * *' -> the fixed all-wildcard sentence (no redundant 'every day' suffix)", () => {
  assert.strictEqual(explain('* * * * *'), 'Every minute.');
});

test("'*/15 * * * *' -> readable step phrasing ('every 15 minutes')", () => {
  assert.strictEqual(explain('*/15 * * * *'), 'Every 15 minutes, every day.');
});

test("'0 0 * * *' -> specific time + unrestricted day ('At 00:00, every day.')", () => {
  assert.strictEqual(explain('0 0 * * *'), 'At 00:00, every day.');
});

test("'0 9-17 * * 1-5' -> hour range + dayOfWeek range ('Monday through Friday')", () => {
  assert.strictEqual(
    explain('0 9-17 * * 1-5'),
    'At minute 0 past every hour from 9 through 17, on Monday through Friday.'
  );
});

test("both-restricted OR case '0 0 13 * 5' -> explicit OR/union coupling in prose", () => {
  assert.strictEqual(
    explain('0 0 13 * 5'),
    'At 00:00, on the 13th of the month or on Friday.'
  );
});

// ---------------------------------------------------------------------------
// Real-world crons from the task brief
// ---------------------------------------------------------------------------

test("'*/15 0 * * *' -> minute step qualified by a single restricted hour", () => {
  assert.strictEqual(
    explain('*/15 0 * * *'),
    'Every 15 minutes during hour 0, every day.'
  );
});

test("'0 9 * * 1-5' -> specific time + weekday range", () => {
  assert.strictEqual(explain('0 9 * * 1-5'), 'At 09:00, on Monday through Friday.');
});

test("'30 9 1 * *' -> specific time + single day-of-month (ordinal)", () => {
  assert.strictEqual(explain('30 9 1 * *'), 'At 09:30, on the 1st of the month.');
});

test("both-restricted OR case '0 0 1 * 1' -> 1st-of-month OR Monday", () => {
  assert.strictEqual(
    explain('0 0 1 * 1'),
    'At 00:00, on the 1st of the month or on Monday.'
  );
});

// ---------------------------------------------------------------------------
// Additional rendering-branch coverage: 2-point list ('minutes 0 and 30'),
// month name list ('in January and June'), month/day-of-week name resolution.
// ---------------------------------------------------------------------------

test("'0,30 * * * *' -> a 2-point arithmetic set renders as an explicit list, not a step", () => {
  assert.strictEqual(
    explain('0,30 * * * *'),
    'At minutes 0 and 30 past every hour, every day.'
  );
});

test("'0 0 1 1,6 *' -> month list rendered via MONTH_DISPLAY ('in January and June')", () => {
  assert.strictEqual(
    explain('0 0 1 1,6 *'),
    'At 00:00, on the 1st of the month, in January and June.'
  );
});

test("dayOfWeek single value renders via DOW_DISPLAY ('on Wednesday')", () => {
  assert.strictEqual(explain('0 0 * * 3'), 'At 00:00, on Wednesday.');
});

test("month range renders via MONTH_DISPLAY ('from March through May')", () => {
  assert.strictEqual(explain('0 0 1 3-5 *'), 'At 00:00, on the 1st of the month, from March through May.');
});

test("dayOfMonth list uses ordinals ('the 1st, 15th and 20th of the month')", () => {
  assert.strictEqual(
    explain('0 0 1,15,20 * *'),
    'At 00:00, on the 1st, 15th and 20th of the month.'
  );
});

// ---------------------------------------------------------------------------
// Invalid expressions: CronParseError propagates unchanged (no wrapping,
// no stack trace originating from explain.js itself).
// ---------------------------------------------------------------------------

test('an invalid expression throws CronParseError, propagated unchanged from the parser', () => {
  assert.throws(
    () => explain('@daily'),
    (err) => {
      assert.ok(err instanceof CronParseError, `expected CronParseError, got ${err}`);
      assert.strictEqual(err.expression, '@daily');
      return true;
    }
  );
});

test('a field-scoped invalid expression also propagates CronParseError with .field set', () => {
  assert.throws(
    () => explain('60 0 * * *'),
    (err) => {
      assert.ok(err instanceof CronParseError);
      assert.strictEqual(err.field, 'minute');
      return true;
    }
  );
});

// ---------------------------------------------------------------------------
// Determinism: same expression always yields the same string.
// ---------------------------------------------------------------------------

test('explain is deterministic across repeated calls', () => {
  const expr = '0 9-17 * * 1-5';
  const first = explain(expr);
  for (let i = 0; i < 5; i += 1) {
    assert.strictEqual(explain(expr), first);
  }
});

test('explainParsed accepts a pre-parsed object directly', () => {
  const parsed = parse('0 0 13 * 5');
  assert.strictEqual(
    explainParsed(parsed),
    'At 00:00, on the 13th of the month or on Friday.'
  );
});
