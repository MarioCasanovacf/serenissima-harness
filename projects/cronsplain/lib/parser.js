'use strict';

const { CronParseError } = require('./errors');
const { FIELDS, MONTH_NAMES, DOW_NAMES, normalizeDow } = require('./fields');

/**
 * lib/parser.js — cronsplain's 5-field POSIX cron expression parser.
 *
 * parse(expression) -> ParsedCron
 *
 * ParsedCron SHAPE (PINNED — this is the epic's central contract; T-046's
 * golden vectors, the T-047/T-048 schedule candidates, and T-050's explain
 * module all read this shape verbatim. Do not change field names, Set
 * semantics, or the two *Restricted booleans without updating every
 * downstream consumer):
 *
 *   {
 *     fields: {
 *       minute:     Set<int>,   // fully-expanded allowed values, 0-59
 *       hour:       Set<int>,   // fully-expanded allowed values, 0-23
 *       dayOfMonth: Set<int>,   // fully-expanded allowed values, 1-31
 *       month:      Set<int>,   // fully-expanded allowed values, 1-12
 *       dayOfWeek:  Set<int>,   // fully-expanded allowed values, 0-6
 *                               // (7 is accepted as an alias for Sunday
 *                               // and normalized to 0 via fields.normalizeDow;
 *                               // if both 0 and 7 are supplied they
 *                               // collapse to the single Set entry 0)
 *     },
 *     domRestricted: boolean,   // true iff the RAW dayOfMonth field text
 *                               // (the literal token, e.g. '*\/5' or
 *                               // '1,15') is anything other than exactly
 *                               // the string '*'. This is a TEXTUAL check,
 *                               // not a semantic "covers every value"
 *                               // check.
 *     dowRestricted: boolean,   // same textual check for the dayOfWeek field.
 *     source: string,           // the original, unmodified expression string
 *                               // exactly as passed to parse().
 *   }
 *
 * domRestricted/dowRestricted exist so downstream schedule code
 * (T-047/T-048) can implement the classic Vixie day-of-month OR
 * day-of-week coupling without re-parsing text: when BOTH flags are true,
 * a candidate day matches if it is present in EITHER the dayOfMonth OR
 * the dayOfWeek Set (union); when exactly one flag is true, only that
 * field's Set constrains matching; when both are false, every day
 * matches. Set-of-ints + two booleans was chosen (over a matcher
 * function) so downstream code needs no knowledge of parser internals.
 *
 * GRAMMAR accepted per field (minute, hour, dayOfMonth, month, dayOfWeek —
 * see lib/fields.js FIELDS for the exact bounds and display strings):
 *   - '*'                wildcard: expands to the field's full [min, max].
 *   - 'a'                single value (an integer literal, or — for
 *                        month/dayOfWeek only — a case-insensitive 3-letter
 *                        name: JAN-DEC -> 1-12, SUN-SAT -> 0-6).
 *   - 'a-b'              inclusive range; a and b may be integers or (for
 *                        month/dayOfWeek) names, e.g. MON-FRI, JAN-MAR.
 *                        b < a (a "reversed" range) is REJECTED — see
 *                        DECISION below.
 *   - '*\/n' / 'a-b/n'    step, n a positive integer: every n-th value
 *                        starting at the wildcard's/range's start.
 *   - 'x,y,z'            comma list combining any of the above items.
 * dayOfWeek additionally accepts 0-7 with 7 == 0 (Sunday); this applies
 * uniformly across single values, ranges, steps, wildcard, and lists.
 *
 * DECISION (documented per T-045 acceptance criteria): a reversed range
 * (b < a, e.g. '10-5') is REJECTED with CronParseError rather than being
 * interpreted as a wrap-around range. This keeps the grammar unambiguous
 * and matches the POSIX baseline this parser targets.
 *
 * REJECTED (always throws CronParseError with `.expression` set to the
 * original input and, whenever a single field is at fault, `.field` set
 * to one of the FIELDS names — minute/hour/dayOfMonth/month/dayOfWeek):
 *   - Any field count other than 5 (fields are split on one-or-more
 *     whitespace characters after trimming the ends; a Vixie `@macro`
 *     like '@daily' is a single token and is therefore naturally rejected
 *     here as a field-count mismatch, with no special-case needed).
 *   - An empty list element, e.g. '1,,5', '1,2,', ',1,2' (an empty
 *     top-level field is likewise rejected, though because fields come
 *     from a whitespace-collapsing split, a genuinely empty field token
 *     cannot actually be produced by that split — the check exists as a
 *     defensive guard documenting the rule regardless of tokenization
 *     strategy).
 *   - A value outside the field's [min, max] bounds.
 *   - A reversed range (b < a).
 *   - A step that is zero, negative, or not a plain non-negative integer
 *     literal (e.g. '*\/0', '*\/-5', '*\/2.5').
 *   - An unrecognized name, or a name used in a field that does not
 *     support names (minute/hour/dayOfMonth).
 *   - The bare Vixie start-step form 'a/n' (e.g. '3/5') — only '*\/n' and
 *     'a-b/n' are valid step forms; a bare value before '/' is rejected
 *     explicitly with a message naming this as an unsupported extension.
 *   - Any other Vixie extension (L, W, #, ?) or trailing-garbage token
 *     (e.g. '5x', '1-5/2/3', '1-5-10'): these are not special-cased —
 *     they simply fail to match any accepted grammar form and are
 *     rejected as an unrecognized value/name or a malformed range/step.
 *
 * Zero runtime dependencies; CommonJS only (package.json / T-044 contract).
 */

const DIGITS_ONLY = /^\d+$/;

function nameMapFor(fieldDef) {
  if (fieldDef.name === 'month') return MONTH_NAMES;
  if (fieldDef.name === 'dayOfWeek') return DOW_NAMES;
  return null;
}

/**
 * Resolve a single token (numeric literal or, for month/dayOfWeek, a
 * case-insensitive name) to its in-range integer value for fieldDef.
 * Throws CronParseError for empty/unrecognized tokens or out-of-bounds
 * values. Does NOT apply dayOfWeek's 7->0 normalization — callers collect
 * raw values first and normalize when inserting into the result Set, so
 * that "0 and 7 both present" collapses correctly regardless of order.
 */
function resolveValue(fieldDef, token, expression) {
  if (token === '') {
    throw new CronParseError(
      `Empty value in '${fieldDef.display}' field`,
      { expression, field: fieldDef.name }
    );
  }

  let value;
  if (DIGITS_ONLY.test(token)) {
    value = parseInt(token, 10);
  } else {
    const nameMap = nameMapFor(fieldDef);
    if (nameMap && token in nameMap) {
      value = nameMap[token];
    } else {
      throw new CronParseError(
        `Unrecognized value '${token}' in '${fieldDef.display}' field`,
        { expression, field: fieldDef.name }
      );
    }
  }

  if (value < fieldDef.min || value > fieldDef.max) {
    throw new CronParseError(
      `Value ${value} out of range [${fieldDef.min}-${fieldDef.max}] ` +
        `for '${fieldDef.display}' field`,
      { expression, field: fieldDef.name }
    );
  }
  return value;
}

/**
 * Expand a single comma-list item (no commas inside) — a wildcard,
 * single value, range, or step form — into an array of raw (pre
 * dayOfWeek-normalization) integers. Throws CronParseError for any
 * malformed or out-of-grammar item.
 */
function expandItem(fieldDef, item, expression) {
  if (item === '') {
    throw new CronParseError(
      `Empty value in list for '${fieldDef.display}' field`,
      { expression, field: fieldDef.name }
    );
  }

  const slashParts = item.split('/');
  if (slashParts.length > 2) {
    throw new CronParseError(
      `Malformed step expression '${item}' in '${fieldDef.display}' field`,
      { expression, field: fieldDef.name }
    );
  }
  const [rangeToken, stepToken] = slashParts;

  let step = 1;
  if (stepToken !== undefined) {
    if (stepToken === '' || !DIGITS_ONLY.test(stepToken)) {
      throw new CronParseError(
        `Step value '${stepToken}' must be a positive integer in ` +
          `'${fieldDef.display}' field`,
        { expression, field: fieldDef.name }
      );
    }
    step = parseInt(stepToken, 10);
    if (step <= 0) {
      throw new CronParseError(
        `Step value must be greater than zero in '${fieldDef.display}' field`,
        { expression, field: fieldDef.name }
      );
    }
    if (rangeToken !== '*' && !rangeToken.includes('-')) {
      // Bare Vixie start-step form, e.g. "3/5". Only '*\/n' and 'a-b/n'
      // are in the accepted grammar (see Q1, plan.md Unknowns).
      throw new CronParseError(
        `Unsupported step form '${item}' in '${fieldDef.display}' field ` +
          `(only '*/n' and 'a-b/n' are valid step forms; a bare 'a/n' is ` +
          `a Vixie extension and is not supported)`,
        { expression, field: fieldDef.name }
      );
    }
  }

  let start;
  let end;
  if (rangeToken === '*') {
    start = fieldDef.min;
    end = fieldDef.max;
  } else if (rangeToken.includes('-')) {
    const rangeParts = rangeToken.split('-');
    if (rangeParts.length !== 2) {
      throw new CronParseError(
        `Malformed range '${rangeToken}' in '${fieldDef.display}' field`,
        { expression, field: fieldDef.name }
      );
    }
    const [startToken, endToken] = rangeParts;
    start = resolveValue(fieldDef, startToken, expression);
    end = resolveValue(fieldDef, endToken, expression);
    if (end < start) {
      throw new CronParseError(
        `Reversed range '${rangeToken}' (end < start) in ` +
          `'${fieldDef.display}' field`,
        { expression, field: fieldDef.name }
      );
    }
  } else {
    // Single bare value. (A bare value combined with a step was already
    // rejected above as the unsupported Vixie start-step form.)
    start = resolveValue(fieldDef, rangeToken, expression);
    end = start;
  }

  const values = [];
  for (let v = start; v <= end; v += step) {
    values.push(v);
  }
  return values;
}

/**
 * Expand one whitespace-delimited field's raw text into its fully
 * expanded Set<int> of allowed values (with dayOfWeek's 7->0 aliasing
 * applied on insertion).
 */
function expandField(fieldDef, fieldText, expression) {
  if (fieldText === '') {
    throw new CronParseError(
      `Empty '${fieldDef.display}' field`,
      { expression, field: fieldDef.name }
    );
  }

  const items = fieldText.split(',');
  const set = new Set();
  for (const item of items) {
    const rawValues = expandItem(fieldDef, item, expression);
    for (const v of rawValues) {
      set.add(fieldDef.name === 'dayOfWeek' ? normalizeDow(v) : v);
    }
  }
  return set;
}

/**
 * Parse a 5-field POSIX cron expression string into the pinned ParsedCron
 * shape documented above. Throws CronParseError for any invalid input.
 *
 * @param {string} expression
 * @returns {{fields: object, domRestricted: boolean, dowRestricted: boolean, source: string}}
 */
function parse(expression) {
  if (typeof expression !== 'string') {
    throw new CronParseError('Cron expression must be a string', {
      expression,
    });
  }

  const trimmed = expression.trim();
  if (trimmed === '') {
    throw new CronParseError('Cron expression must not be empty', {
      expression,
    });
  }

  const rawFields = trimmed.split(/\s+/);
  if (rawFields.length !== FIELDS.length) {
    throw new CronParseError(
      `Expected ${FIELDS.length} whitespace-separated fields, got ` +
        `${rawFields.length}`,
      { expression }
    );
  }

  const fields = {};
  FIELDS.forEach((fieldDef, i) => {
    fields[fieldDef.name] = expandField(fieldDef, rawFields[i], expression);
  });

  const domIndex = FIELDS.findIndex((f) => f.name === 'dayOfMonth');
  const dowIndex = FIELDS.findIndex((f) => f.name === 'dayOfWeek');

  return {
    fields,
    domRestricted: rawFields[domIndex] !== '*',
    dowRestricted: rawFields[dowIndex] !== '*',
    source: expression,
  };
}

module.exports = { parse };
