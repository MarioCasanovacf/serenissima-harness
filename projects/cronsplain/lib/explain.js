'use strict';

const { parse } = require('./parser');
const { MONTH_DISPLAY, DOW_DISPLAY } = require('./fields');

/**
 * lib/explain.js — renders a parsed cron expression as a single deterministic
 * English sentence.
 *
 * EXPORTS:
 *   - explain(expr) -> string       : parse(expr) then explainParsed(parsed).
 *   - explainParsed(parsed) -> string: render directly from an already-parsed
 *     ParsedCron object (the shape documented in lib/parser.js). `explain` is
 *     defined purely as `explainParsed(parse(expr))` — it does no rendering
 *     of its own, so the two are guaranteed to agree on any given input.
 *
 * ERROR-HANDLING DECISION (per T-050 acceptance criteria): `explain` does NOT
 * catch or wrap parse errors. An invalid expression propagates the parser's
 * `CronParseError` unchanged — explain.js itself never throws anything else
 * and never lets a raw stack trace originate from its own rendering code
 * (rendering only ever runs against an already-validated ParsedCron shape).
 * This matches the epic-wide convention (see lib/errors.js) that the CLI
 * (T-051) is the sole catch point for CronParseError.
 *
 * DETERMINISM: the same expression always parses to the same Set contents
 * and always renders to the same sentence — there is no randomness, no
 * locale/timezone dependence, and no reliance on Set iteration order (every
 * Set is sorted before rendering).
 *
 * SENTENCE TEMPLATE (stable, documented so tests can pin exact strings):
 *   "<time clause>, <day clause>[, <month clause>]."
 *   - <time clause> describes minute+hour jointly (see timeSegment below).
 *   - <day clause> describes dayOfMonth/dayOfWeek. When neither is
 *     textually restricted (both raw tokens are '*'): "every day". When
 *     exactly one is restricted: that field's clause alone. When BOTH are
 *     restricted (the classic Vixie OR/union quirk — see parser.js), the
 *     clause is "on <dom-phrase> or on <dow-phrase>" to make the
 *     union/OR coupling explicit in the prose.
 *   - <month clause> is included only when the month field is not the bare
 *     wildcard; otherwise it is omitted entirely (kept out of the sentence
 *     rather than rendered as a no-op "every month").
 *   SPECIAL CASE: when literally every field is unrestricted/full-range
 *   (the '* * * * *' family), the whole sentence collapses to the fixed
 *   string "Every minute." (no redundant ", every day" suffix) per the
 *   pinned acceptance-criteria example.
 *
 * FIELD-VALUE CLASSIFICATION (`classify`): each field's fully-expanded
 * Set<int> is classified by its numeric SHAPE (not by re-reading original
 * cron syntax, which the parser does not retain per-field) into one of:
 *   - 'every'      : the Set covers the field's entire [min,max] domain.
 *   - 'single'     : exactly one value.
 *   - 'range'      : a contiguous run of consecutive integers (step 1),
 *                    length >= 2.
 *   - 'step'       : a uniform arithmetic progression (step > 1, length >= 3)
 *                    that starts at the field's domain minimum AND is
 *                    "maximal" (continuing by one more step would exceed the
 *                    domain max) — i.e. exactly what '*\/n' produces. This
 *                    guards against misreading a coincidental 2-point or
 *                    partial arithmetic list as a step (see 'rangeStep').
 *   - 'rangeStep'  : a uniform arithmetic progression (step > 1, length >= 3)
 *                    that does NOT start at the domain min and/or is not
 *                    maximal — i.e. what 'a-b/n' produces.
 *   - 'list'       : anything else (arbitrary values, or a 2-point uniform
 *                    progression — two points are rendered as an explicit
 *                    list rather than implying an open-ended step; this is
 *                    what makes '*\/30 * * * *' render as "minutes 0 and 30"
 *                    rather than an overclaiming "every 30 minutes").
 * Because classification works from the numeric Set alone, syntactically
 * different-but-equivalent inputs (e.g. '*\/15' and '0,15,30,45') render
 * identically — this is intentional: they mean the same schedule.
 */

function pad2(n) {
  return String(n).padStart(2, '0');
}

function ordinal(n) {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

function joinNatural(strs) {
  if (strs.length === 1) return strs[0];
  if (strs.length === 2) return `${strs[0]} and ${strs[1]}`;
  return `${strs.slice(0, -1).join(', ')} and ${strs[strs.length - 1]}`;
}

function numList(values) {
  return joinNatural(values.map(String));
}

function ordinalList(values) {
  return joinNatural(values.map(ordinal));
}

function nameList(values, names) {
  return joinNatural(values.map((v) => names[v]));
}

/**
 * Classify a field's fully-expanded Set<int> by numeric shape. See the
 * module docblock for the full description of each returned `kind`.
 */
function classify(setOfInts, min, max) {
  const sorted = Array.from(setOfInts).sort((a, b) => a - b);
  const n = sorted.length;
  const fullCount = max - min + 1;

  if (n === fullCount && sorted[0] === min && sorted[n - 1] === max) {
    return { kind: 'every' };
  }
  if (n === 1) {
    return { kind: 'single', value: sorted[0] };
  }

  const diff0 = sorted[1] - sorted[0];
  let uniform = true;
  for (let i = 2; i < n; i += 1) {
    if (sorted[i] - sorted[i - 1] !== diff0) {
      uniform = false;
      break;
    }
  }

  if (uniform && diff0 === 1) {
    return { kind: 'range', start: sorted[0], end: sorted[n - 1] };
  }
  if (uniform && diff0 > 1 && n >= 3) {
    const isMaximal = sorted[n - 1] + diff0 > max;
    if (sorted[0] === min && isMaximal) {
      return { kind: 'step', step: diff0, start: sorted[0], end: sorted[n - 1] };
    }
    return { kind: 'rangeStep', step: diff0, start: sorted[0], end: sorted[n - 1] };
  }
  return { kind: 'list', values: sorted };
}

// --- minute/hour ("time") rendering -----------------------------------

function hourQualifier(hc) {
  switch (hc.kind) {
    case 'every':
      return '';
    case 'single':
      return ` during hour ${hc.value}`;
    case 'range':
      return ` between hours ${hc.start} and ${hc.end}`;
    case 'step':
      return ` every ${hc.step} hours`;
    case 'rangeStep':
      return ` every ${hc.step} hours from ${hc.start} through ${hc.end}`;
    case 'list':
      return ` during hours ${numList(hc.values)}`;
    default:
      return '';
  }
}

function hourPastPhrase(hc) {
  switch (hc.kind) {
    case 'every':
      return 'every hour';
    case 'single':
      return `hour ${hc.value}`;
    case 'range':
      return `every hour from ${hc.start} through ${hc.end}`;
    case 'step':
      return `every ${hc.step} hours`;
    case 'rangeStep':
      return `every ${hc.step} hours from ${hc.start} through ${hc.end}`;
    case 'list':
      return `hours ${numList(hc.values)}`;
    default:
      return 'every hour';
  }
}

function minuteNumericPhrase(mc) {
  switch (mc.kind) {
    case 'single':
      return `minute ${mc.value}`;
    case 'range':
      return `minutes ${mc.start} through ${mc.end}`;
    case 'rangeStep':
      return `every ${mc.step} minutes from ${mc.start} through ${mc.end}`;
    case 'list':
      return `minutes ${numList(mc.values)}`;
    default:
      return `minute ${mc.value}`;
  }
}

/**
 * Render the joint minute+hour "time" clause. Priority order:
 *   1. both single             -> "At HH:MM"
 *   2. both every              -> "Every minute"
 *   3. minute step, hour every -> "Every N minutes"
 *   4/5. one of minute/hour every, the other not -> "Every minute<hourQualifier>"
 *        or "Every N minutes<hourQualifier>"
 *   6. fallback (minute single/range/list/rangeStep, any hour) ->
 *        "At <minute phrase> past <hour phrase>"
 */
function timeSegment(mc, hc) {
  if (mc.kind === 'single' && hc.kind === 'single') {
    return `At ${pad2(hc.value)}:${pad2(mc.value)}`;
  }
  if (mc.kind === 'every' && hc.kind === 'every') {
    return 'Every minute';
  }
  if (mc.kind === 'step' && hc.kind === 'every') {
    return `Every ${mc.step} minutes`;
  }
  if (mc.kind === 'every' && hc.kind !== 'every') {
    return `Every minute${hourQualifier(hc)}`;
  }
  if (mc.kind === 'step' && hc.kind !== 'every') {
    return `Every ${mc.step} minutes${hourQualifier(hc)}`;
  }
  return `At ${minuteNumericPhrase(mc)} past ${hourPastPhrase(hc)}`;
}

// --- dayOfMonth / dayOfWeek ("day") rendering ---------------------------

function domPhraseStandalone(dc) {
  switch (dc.kind) {
    case 'every':
      return 'every day of the month';
    case 'step':
      return `every ${dc.step} days of the month`;
    case 'single':
      return `on the ${ordinal(dc.value)} of the month`;
    case 'range':
      return `on days ${dc.start} through ${dc.end} of the month`;
    case 'rangeStep':
      return `on every ${dc.step} days of the month from ${dc.start} through ${dc.end}`;
    case 'list':
      return `on the ${ordinalList(dc.values)} of the month`;
    default:
      return 'every day of the month';
  }
}

function domPhraseForOr(dc) {
  switch (dc.kind) {
    case 'every':
      return 'every day of the month';
    case 'step':
      return `every ${dc.step} days of the month`;
    case 'single':
      return `the ${ordinal(dc.value)} of the month`;
    case 'range':
      return `days ${dc.start} through ${dc.end} of the month`;
    case 'rangeStep':
      return `every ${dc.step} days of the month from ${dc.start} through ${dc.end}`;
    case 'list':
      return `the ${ordinalList(dc.values)} of the month`;
    default:
      return 'every day of the month';
  }
}

function dowPhraseStandalone(wc) {
  switch (wc.kind) {
    case 'every':
      return 'every day of the week';
    case 'step':
      return `every ${wc.step} days of the week`;
    case 'single':
      return `on ${DOW_DISPLAY[wc.value]}`;
    case 'range':
      return `on ${DOW_DISPLAY[wc.start]} through ${DOW_DISPLAY[wc.end]}`;
    case 'rangeStep':
      return `on every ${wc.step} days of the week from ${DOW_DISPLAY[wc.start]} through ${DOW_DISPLAY[wc.end]}`;
    case 'list':
      return `on ${nameList(wc.values, DOW_DISPLAY)}`;
    default:
      return 'every day of the week';
  }
}

function dowPhraseForOr(wc) {
  switch (wc.kind) {
    case 'every':
      return 'every day of the week';
    case 'step':
      return `every ${wc.step} days of the week`;
    case 'single':
      return `${DOW_DISPLAY[wc.value]}`;
    case 'range':
      return `${DOW_DISPLAY[wc.start]} through ${DOW_DISPLAY[wc.end]}`;
    case 'rangeStep':
      return `every ${wc.step} days of the week from ${DOW_DISPLAY[wc.start]} through ${DOW_DISPLAY[wc.end]}`;
    case 'list':
      return `${nameList(wc.values, DOW_DISPLAY)}`;
    default:
      return 'every day of the week';
  }
}

/**
 * Render the day clause. domRestricted/dowRestricted are the parser's
 * TEXTUAL flags (raw token !== '*'), which is exactly what decides whether
 * the Vixie OR/union coupling applies (see lib/parser.js docblock).
 */
function daySegment(parsed) {
  const { domRestricted, dowRestricted, fields } = parsed;
  const domClass = classify(fields.dayOfMonth, 1, 31);
  const dowClass = classify(fields.dayOfWeek, 0, 6);

  if (!domRestricted && !dowRestricted) return 'every day';
  if (domRestricted && !dowRestricted) return domPhraseStandalone(domClass);
  if (!domRestricted && dowRestricted) return dowPhraseStandalone(dowClass);
  return `on ${domPhraseForOr(domClass)} or on ${dowPhraseForOr(dowClass)}`;
}

// --- month rendering -----------------------------------------------------

function monthSegment(monthSet) {
  const mc = classify(monthSet, 1, 12);
  switch (mc.kind) {
    case 'every':
      return null;
    case 'single':
      return `in ${MONTH_DISPLAY[mc.value - 1]}`;
    case 'range':
      return `from ${MONTH_DISPLAY[mc.start - 1]} through ${MONTH_DISPLAY[mc.end - 1]}`;
    case 'step':
      return `every ${mc.step} months`;
    case 'rangeStep':
      return `every ${mc.step} months from ${MONTH_DISPLAY[mc.start - 1]} through ${MONTH_DISPLAY[mc.end - 1]}`;
    case 'list':
      return `in ${nameList(
        mc.values.map((v) => v - 1),
        MONTH_DISPLAY
      )}`;
    default:
      return null;
  }
}

/**
 * Render an already-parsed ParsedCron (see lib/parser.js) as one
 * deterministic English sentence.
 *
 * @param {{fields: object, domRestricted: boolean, dowRestricted: boolean, source: string}} parsed
 * @returns {string}
 */
function explainParsed(parsed) {
  const { fields } = parsed;
  const minuteClass = classify(fields.minute, 0, 59);
  const hourClass = classify(fields.hour, 0, 23);
  const monthClass = classify(fields.month, 1, 12);

  const allWildcard =
    minuteClass.kind === 'every' &&
    hourClass.kind === 'every' &&
    !parsed.domRestricted &&
    !parsed.dowRestricted &&
    monthClass.kind === 'every';

  if (allWildcard) {
    return 'Every minute.';
  }

  const time = timeSegment(minuteClass, hourClass);
  const day = daySegment(parsed);
  const month = monthSegment(fields.month);

  const segments = [time, day];
  if (month) segments.push(month);
  return `${segments.join(', ')}.`;
}

/**
 * Parse `expr` then render it as one deterministic English sentence.
 * Invalid expressions propagate the parser's CronParseError unchanged (see
 * the ERROR-HANDLING DECISION note above).
 *
 * @param {string} expr
 * @returns {string}
 */
function explain(expr) {
  return explainParsed(parse(expr));
}

module.exports = { explain, explainParsed };
