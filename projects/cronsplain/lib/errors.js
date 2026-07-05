'use strict';

/**
 * CronParseError — the ONLY error type thrown by the cronsplain parser
 * (lib/parser.js) for any invalid cron expression or field. The CLI
 * (bin/cronsplain.js / lib/cli.js) catches this exclusively to print a
 * clean, stack-trace-free message to the user; anything else propagating
 * out of the parser is a bug, not a user input problem.
 *
 * @property {string} name - always 'CronParseError'
 * @property {string|undefined} expression - the raw cron expression string
 *   that failed to parse, when available to the caller.
 * @property {string|undefined} field - the name of the offending field
 *   (one of the FIELDS names in lib/fields.js: minute, hour, dayOfMonth,
 *   month, dayOfWeek), when the error is field-scoped.
 */
class CronParseError extends Error {
  constructor(message, { expression, field } = {}) {
    super(message);
    this.name = 'CronParseError';
    this.expression = expression;
    this.field = field;

    if (typeof Error.captureStackTrace === 'function') {
      Error.captureStackTrace(this, CronParseError);
    }
  }
}

module.exports = { CronParseError };
