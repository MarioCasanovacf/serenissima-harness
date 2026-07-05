'use strict';

/**
 * lib/fields.js — shared field metadata for the cronsplain epic.
 *
 * Consumed by lib/parser.js (bounds + name maps), lib/explain.js (display
 * strings), and lib/schedule.js / the candidates/ tournament (field order +
 * normalizeDow). This is pure data + tiny pure helpers: no parsing logic,
 * no I/O, no throw (see lib/errors.js for the error type parsers use when
 * a value from these tables doesn't match).
 */

/**
 * Build a case-insensitive lookup map from [KEY, value] pairs. Reads via
 * bracket or dot access with any casing (MONTH_NAMES.jan, MONTH_NAMES['JAN'],
 * MONTH_NAMES['Jan']) all resolve to the same entry; `in` checks are
 * likewise case-insensitive. Keys are stored/enumerated upper-cased.
 *
 * @param {Array<[string, *]>} entries
 * @returns {Object} a Proxy-backed, read-only-by-convention case-insensitive map
 */
function makeCaseInsensitiveMap(entries) {
  const store = Object.create(null);
  for (const [key, value] of entries) {
    store[key.toUpperCase()] = value;
  }
  Object.freeze(store);
  return new Proxy(store, {
    get(target, prop, receiver) {
      if (typeof prop === 'string') {
        const upper = prop.toUpperCase();
        if (upper in target) return target[upper];
      }
      return Reflect.get(target, prop, receiver);
    },
    has(target, prop) {
      if (typeof prop === 'string') {
        return prop.toUpperCase() in target;
      }
      return Reflect.has(target, prop);
    },
    ownKeys(target) {
      return Reflect.ownKeys(target);
    },
    getOwnPropertyDescriptor(target, prop) {
      if (typeof prop === 'string') {
        const upper = prop.toUpperCase();
        if (upper in target) {
          return Object.getOwnPropertyDescriptor(target, upper);
        }
      }
      return Object.getOwnPropertyDescriptor(target, prop);
    },
  });
}

/**
 * FIELDS — ordered 5-field POSIX cron layout. Order matters: parser output,
 * explain sentence order, and CLI positional-expression splitting all rely
 * on this exact array order (minute, hour, dayOfMonth, month, dayOfWeek).
 */
const FIELDS = [
  { name: 'minute', min: 0, max: 59, display: 'minute' },
  { name: 'hour', min: 0, max: 23, display: 'hour' },
  { name: 'dayOfMonth', min: 1, max: 31, display: 'day of month' },
  { name: 'month', min: 1, max: 12, display: 'month' },
  { name: 'dayOfWeek', min: 0, max: 7, display: 'day of week' },
];
// Hardening (verifier-c advisory, T-044 re-handoff): this module is a shared
// singleton require()d by parser/explain/schedule across the epic. Freeze
// each entry AND the array so a stray mutation in one consumer cannot
// silently corrupt state observed by every other consumer.
FIELDS.forEach((field) => Object.freeze(field));
Object.freeze(FIELDS);

/** MONTH_NAMES — case-insensitive JAN..DEC -> 1..12. */
const MONTH_NAMES = makeCaseInsensitiveMap([
  ['JAN', 1],
  ['FEB', 2],
  ['MAR', 3],
  ['APR', 4],
  ['MAY', 5],
  ['JUN', 6],
  ['JUL', 7],
  ['AUG', 8],
  ['SEP', 9],
  ['OCT', 10],
  ['NOV', 11],
  ['DEC', 12],
]);

/** DOW_NAMES — case-insensitive SUN..SAT -> 0..6 (SUN=0). */
const DOW_NAMES = makeCaseInsensitiveMap([
  ['SUN', 0],
  ['MON', 1],
  ['TUE', 2],
  ['WED', 3],
  ['THU', 4],
  ['FRI', 5],
  ['SAT', 6],
]);

/** MONTH_DISPLAY — 1-indexed by (month - 1); January..December, for explain. */
const MONTH_DISPLAY = Object.freeze([
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]);

/** DOW_DISPLAY — 0-indexed (SUN=0); Sunday..Saturday, for explain. */
const DOW_DISPLAY = Object.freeze([
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
]);

/**
 * normalizeDow — collapse the POSIX dow alias 7 (Sunday, per `7 === 0`) down
 * to the canonical 0. Every other value passes through unchanged (bounds
 * validation is the parser's job, not this helper's).
 *
 * @param {number} n
 * @returns {number}
 */
function normalizeDow(n) {
  return n === 7 ? 0 : n;
}

module.exports = {
  FIELDS,
  MONTH_NAMES,
  DOW_NAMES,
  MONTH_DISPLAY,
  DOW_DISPLAY,
  normalizeDow,
};
