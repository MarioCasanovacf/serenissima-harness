'use strict';

const { test } = require('node:test');
const assert = require('node:assert');

const {
  FIELDS,
  MONTH_NAMES,
  DOW_NAMES,
  MONTH_DISPLAY,
  DOW_DISPLAY,
  normalizeDow,
} = require('../lib/fields');

test('FIELDS has length 5 in minute,hour,dayOfMonth,month,dayOfWeek order', () => {
  assert.strictEqual(FIELDS.length, 5);
  assert.deepStrictEqual(
    FIELDS.map((f) => f.name),
    ['minute', 'hour', 'dayOfMonth', 'month', 'dayOfWeek']
  );
});

test('FIELDS bounds per field', () => {
  const byName = Object.fromEntries(FIELDS.map((f) => [f.name, f]));
  assert.strictEqual(byName.minute.min, 0);
  assert.strictEqual(byName.minute.max, 59);
  assert.strictEqual(byName.hour.min, 0);
  assert.strictEqual(byName.hour.max, 23);
  assert.strictEqual(byName.dayOfMonth.min, 1);
  assert.strictEqual(byName.dayOfMonth.max, 31);
  assert.strictEqual(byName.month.min, 1);
  assert.strictEqual(byName.month.max, 12);
  assert.strictEqual(byName.dayOfWeek.min, 0);
  assert.strictEqual(byName.dayOfWeek.max, 7);
});

test('FIELDS entries each carry a display string', () => {
  for (const field of FIELDS) {
    assert.strictEqual(typeof field.display, 'string');
    assert.ok(field.display.length > 0);
  }
});

test('MONTH_NAMES resolves JAN..DEC to 1..12', () => {
  assert.strictEqual(MONTH_NAMES.JAN, 1);
  assert.strictEqual(MONTH_NAMES.FEB, 2);
  assert.strictEqual(MONTH_NAMES.MAR, 3);
  assert.strictEqual(MONTH_NAMES.APR, 4);
  assert.strictEqual(MONTH_NAMES.MAY, 5);
  assert.strictEqual(MONTH_NAMES.JUN, 6);
  assert.strictEqual(MONTH_NAMES.JUL, 7);
  assert.strictEqual(MONTH_NAMES.AUG, 8);
  assert.strictEqual(MONTH_NAMES.SEP, 9);
  assert.strictEqual(MONTH_NAMES.OCT, 10);
  assert.strictEqual(MONTH_NAMES.NOV, 11);
  assert.strictEqual(MONTH_NAMES.DEC, 12);
});

test('MONTH_NAMES is case-insensitive', () => {
  assert.strictEqual(MONTH_NAMES['jan'], 1);
  assert.strictEqual(MONTH_NAMES['Jan'], 1);
  assert.strictEqual(MONTH_NAMES['dec'], 12);
  assert.strictEqual(MONTH_NAMES['Dec'], 12);
  assert.strictEqual(MONTH_NAMES['DEC'], 12);
  assert.ok('dec' in MONTH_NAMES);
  assert.ok(!('xyz' in MONTH_NAMES));
});

test('DOW_NAMES resolves SUN..SAT to 0..6 (SUN=0)', () => {
  assert.strictEqual(DOW_NAMES.SUN, 0);
  assert.strictEqual(DOW_NAMES.MON, 1);
  assert.strictEqual(DOW_NAMES.TUE, 2);
  assert.strictEqual(DOW_NAMES.WED, 3);
  assert.strictEqual(DOW_NAMES.THU, 4);
  assert.strictEqual(DOW_NAMES.FRI, 5);
  assert.strictEqual(DOW_NAMES.SAT, 6);
});

test('DOW_NAMES is case-insensitive', () => {
  assert.strictEqual(DOW_NAMES['sun'], 0);
  assert.strictEqual(DOW_NAMES['Sun'], 0);
  assert.strictEqual(DOW_NAMES['sat'], 6);
  assert.strictEqual(DOW_NAMES['SAT'], 6);
  assert.ok('sun' in DOW_NAMES);
});

test('normalizeDow maps 7 -> 0 and leaves other values unchanged', () => {
  assert.strictEqual(normalizeDow(7), 0);
  assert.strictEqual(normalizeDow(0), 0);
  assert.strictEqual(normalizeDow(1), 1);
  assert.strictEqual(normalizeDow(6), 6);
});

test('MONTH_DISPLAY and DOW_DISPLAY have the right length, order, and content', () => {
  assert.strictEqual(MONTH_DISPLAY.length, 12);
  assert.strictEqual(MONTH_DISPLAY[0], 'January');
  assert.strictEqual(MONTH_DISPLAY[11], 'December');

  assert.strictEqual(DOW_DISPLAY.length, 7);
  assert.strictEqual(DOW_DISPLAY[0], 'Sunday');
  assert.strictEqual(DOW_DISPLAY[6], 'Saturday');
});

test('MONTH_DISPLAY[MONTH_NAMES[name] - 1] round-trips to the display name', () => {
  assert.strictEqual(MONTH_DISPLAY[MONTH_NAMES.jan - 1], 'January');
  assert.strictEqual(MONTH_DISPLAY[MONTH_NAMES.DEC - 1], 'December');
});

test('DOW_DISPLAY[normalizeDow(DOW_NAMES[name])] round-trips to the display name', () => {
  assert.strictEqual(DOW_DISPLAY[normalizeDow(DOW_NAMES.sun)], 'Sunday');
  assert.strictEqual(DOW_DISPLAY[normalizeDow(DOW_NAMES.SAT)], 'Saturday');
});

test('FIELDS (array + each entry), MONTH_DISPLAY, and DOW_DISPLAY are frozen', () => {
  assert.ok(Object.isFrozen(FIELDS), 'FIELDS array should be frozen');
  for (const field of FIELDS) {
    assert.ok(Object.isFrozen(field), `FIELDS entry ${field.name} should be frozen`);
  }
  assert.ok(Object.isFrozen(MONTH_DISPLAY), 'MONTH_DISPLAY should be frozen');
  assert.ok(Object.isFrozen(DOW_DISPLAY), 'DOW_DISPLAY should be frozen');
});

test('mutation attempts on frozen FIELDS/displays throw in strict mode and never stick', () => {
  assert.throws(() => {
    FIELDS[0].max = 999;
  }, TypeError);
  assert.throws(() => {
    FIELDS.push({ name: 'bogus', min: 0, max: 0, display: 'bogus' });
  }, TypeError);
  assert.throws(() => {
    MONTH_DISPLAY[0] = 'Nope';
  }, TypeError);
  assert.throws(() => {
    DOW_DISPLAY[0] = 'Nope';
  }, TypeError);
  // Sanity: values are unchanged after the throwing attempts above.
  assert.strictEqual(FIELDS[0].max, 59);
  assert.strictEqual(FIELDS.length, 5);
  assert.strictEqual(MONTH_DISPLAY[0], 'January');
  assert.strictEqual(DOW_DISPLAY[0], 'Sunday');
});

test('mutation attempts on the MONTH_NAMES/DOW_NAMES Proxy-backed maps throw and never stick', () => {
  assert.throws(() => {
    MONTH_NAMES.JAN = 999;
  }, TypeError);
  assert.throws(() => {
    DOW_NAMES.SUN = 999;
  }, TypeError);
  assert.strictEqual(MONTH_NAMES.JAN, 1);
  assert.strictEqual(DOW_NAMES.SUN, 0);
});
