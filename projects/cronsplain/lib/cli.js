'use strict';

const { parse } = require('./parser');
const { explain } = require('./explain');
const { nextOccurrences } = require('./schedule');
const { CronParseError } = require('./errors');

/**
 * lib/cli.js — cronsplain's command-line logic.
 *
 * export run(argv) -> { code, stdout, stderr }
 *
 * `run` is pure/testable: it takes the argv slice AFTER `node <script>`
 * (i.e. `process.argv.slice(2)`), performs no I/O of its own (no
 * process.stdout.write, no process.exit), and returns a plain result
 * object. bin/cronsplain.js is the sole place that writes the returned
 * strings to the real streams and calls process.exit(result.code).
 *
 * COMMANDS:
 *   explain <expr>
 *     stdout = explain(expr) + '\n', code 0.
 *
 *   next <expr> [--from ISO] [--count N]
 *     stdout = the next `count` occurrences, one per line, each rendered
 *     as ISO-8601 UTC with a trailing 'Z' (Date.prototype.toISOString()),
 *     ascending, STRICTLY AFTER --from (exclusive) — see lib/schedule.js.
 *       --count   defaults to 5; must be a positive integer.
 *       --from    defaults to now(); a naive ISO string (no offset/'Z')
 *                 is interpreted as UTC; a string carrying an explicit
 *                 offset or trailing 'Z' is respected and converted to
 *                 its UTC instant.
 *     code 0 on success.
 *
 * ERROR HANDLING (the epic-wide convention: the CLI is the sole catch
 * point for CronParseError — see lib/explain.js / lib/parser.js docs):
 *   - An unknown command, a missing/extra positional argument, an unknown
 *     flag, a flag missing its value, an invalid --count, or an
 *     unparsable --from all throw a local UsageError.
 *   - An invalid cron expression throws the parser's CronParseError
 *     (propagated through explain()/parse() unchanged).
 *   - An impossible/out-of-horizon schedule (e.g. '0 0 30 2 *') throws a
 *     plain Error from the PROMOTED lib/schedule.js.
 *   Every one of these is caught here and turned into a single-line
 *   message written to `stderr` with a non-zero `code` — the raw
 *   `err.stack` is NEVER read or printed, so no stack trace ever reaches
 *   the user.
 *
 * `-h`/`--help` at the top level or inside either subcommand prints a
 * usage string to `stdout` with code 0 (not an error path).
 */

const PROGRAM_NAME = 'cronsplain';

const TOP_USAGE_LINE = `Usage: ${PROGRAM_NAME} <command> [options]`;

const TOP_HELP = `${TOP_USAGE_LINE}

cronsplain -- parse standard 5-field cron expressions.

Commands:
  explain <expr>           Print an English description of <expr>.
  next <expr> [options]    Print the next occurrences of <expr>.

Options:
  -h, --help                Show this help message.

Run '${PROGRAM_NAME} <command> --help' for command-specific help.
`;

const EXPLAIN_HELP = `Usage: ${PROGRAM_NAME} explain <expr>

Print a human-readable English description of a 5-field cron expression
(minute hour dayOfMonth month dayOfWeek).

Arguments:
  <expr>       A quoted 5-field cron expression, e.g. "*/15 0 * * 1-5"

Options:
  -h, --help   Show this help message.

Example:
  ${PROGRAM_NAME} explain "*/15 0 * * 1-5"
`;

const NEXT_HELP = `Usage: ${PROGRAM_NAME} next <expr> [--from ISO] [--count N]

Print the next N occurrences of a 5-field cron expression, one per line,
each in UTC ISO-8601 with a trailing 'Z'. Occurrences are STRICTLY AFTER
--from (exclusive).

Arguments:
  <expr>        A quoted 5-field cron expression, e.g. "0 9 * * 1-5"

Options:
  --from ISO    Start instant (exclusive). A naive ISO string (no
                offset/'Z') is read as UTC; an explicit offset or 'Z' is
                converted to UTC. Default: the current time (now).
  --count N     Number of occurrences to print. Default: 5.
  -h, --help    Show this help message.

Example:
  ${PROGRAM_NAME} next "0 9 * * 1-5" --from 2026-01-01T00:00:00Z --count 3
`;

/** Local error type for argument/usage problems (never escapes run()). */
class UsageError extends Error {
  constructor(message) {
    super(message);
    this.name = 'UsageError';
  }
}

function ok(stdout) {
  return { code: 0, stdout, stderr: '' };
}

function fail(message) {
  return { code: 1, stdout: '', stderr: `${message}\n` };
}

/**
 * Split a subcommand's argv into positional arguments and `--flag value`
 * pairs (also accepting `--flag=value`). `-h`/`--help` is recognized
 * universally and reported via `flags.help = true`. Throws UsageError on
 * an unrecognized `--flag` or a `--flag` missing its value.
 */
function splitArgs(args, allowedFlags) {
  const positionals = [];
  const flags = {};
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '-h' || arg === '--help') {
      flags.help = true;
      continue;
    }
    if (arg.startsWith('--')) {
      const eqIdx = arg.indexOf('=');
      let name;
      let value;
      if (eqIdx !== -1) {
        name = arg.slice(2, eqIdx);
        value = arg.slice(eqIdx + 1);
      } else {
        name = arg.slice(2);
        if (i + 1 >= args.length) {
          throw new UsageError(`Option '--${name}' requires a value`);
        }
        value = args[i + 1];
        i += 1;
      }
      if (!allowedFlags.includes(name)) {
        throw new UsageError(`Unknown option '--${name}'`);
      }
      flags[name] = value;
    } else {
      positionals.push(arg);
    }
  }
  return { positionals, flags };
}

/**
 * Parse a --from value into a Date representing its UTC instant. A value
 * containing a 'T' (a date-time form) with no trailing 'Z' or explicit
 * +HH:MM/-HH:MM offset is treated as naive-UTC (a 'Z' is appended before
 * parsing); any other form (date-only, or one already carrying 'Z'/an
 * offset) is passed to Date() unchanged. Throws UsageError on an
 * unparsable result.
 */
function parseFromDate(raw) {
  const hasOffset = /(Z|[+-]\d{2}:\d{2})$/i.test(raw);
  const source = raw.includes('T') && !hasOffset ? `${raw}Z` : raw;
  const date = new Date(source);
  if (Number.isNaN(date.getTime())) {
    throw new UsageError(`Invalid --from date '${raw}': must be a valid ISO-8601 date/time`);
  }
  return date;
}

/** Parse a --count value into a positive integer. Throws UsageError otherwise. */
function parseCount(raw) {
  if (!/^\d+$/.test(raw) || parseInt(raw, 10) <= 0) {
    throw new UsageError(`Invalid --count '${raw}': must be a positive integer`);
  }
  return parseInt(raw, 10);
}

function runExplain(rest) {
  const { positionals, flags } = splitArgs(rest, []);
  if (flags.help) {
    return ok(EXPLAIN_HELP);
  }
  if (positionals.length === 0) {
    throw new UsageError(`Missing required <expr> argument. ${EXPLAIN_HELP.split('\n')[0]}`);
  }
  if (positionals.length > 1) {
    throw new UsageError('explain accepts exactly one <expr> argument');
  }
  const [expr] = positionals;
  const text = explain(expr); // may throw CronParseError
  return ok(`${text}\n`);
}

function runNext(rest) {
  const { positionals, flags } = splitArgs(rest, ['from', 'count']);
  if (flags.help) {
    return ok(NEXT_HELP);
  }
  if (positionals.length === 0) {
    throw new UsageError(`Missing required <expr> argument. ${NEXT_HELP.split('\n')[0]}`);
  }
  if (positionals.length > 1) {
    throw new UsageError('next accepts exactly one <expr> argument');
  }
  const [expr] = positionals;

  const count = flags.count !== undefined ? parseCount(flags.count) : 5;
  const fromDate = flags.from !== undefined ? parseFromDate(flags.from) : new Date();

  const parsed = parse(expr); // may throw CronParseError
  const dates = nextOccurrences(parsed, fromDate, count); // may throw on impossible schedule
  const lines = dates.map((d) => d.toISOString());
  return ok(`${lines.join('\n')}\n`);
}

/**
 * Render any thrown error as a single-line, stack-trace-free message.
 * `err.stack` is never read here.
 */
function formatError(err) {
  if (err instanceof CronParseError) {
    return `${PROGRAM_NAME}: ${err.message}`;
  }
  if (err instanceof UsageError) {
    return `${PROGRAM_NAME}: ${err.message}`;
  }
  if (err instanceof Error) {
    // Covers the promoted lib/schedule.js's plain Error for an
    // impossible/out-of-horizon schedule. Defensively collapse to the
    // first line in case a future message ever spans multiple lines.
    const firstLine = String(err.message).split('\n')[0];
    return `${PROGRAM_NAME}: ${firstLine}`;
  }
  return `${PROGRAM_NAME}: ${String(err)}`;
}

/**
 * run(argv) -> { code, stdout, stderr }
 * `argv` is the args AFTER node+script (process.argv.slice(2)).
 */
function run(argv) {
  try {
    if (!argv || argv.length === 0) {
      return fail(`Missing command. ${TOP_USAGE_LINE}`);
    }
    if (argv[0] === '-h' || argv[0] === '--help') {
      return ok(TOP_HELP);
    }
    const [command, ...rest] = argv;
    if (command === 'explain') {
      return runExplain(rest);
    }
    if (command === 'next') {
      return runNext(rest);
    }
    return fail(`Unknown command '${command}'. ${TOP_USAGE_LINE}`);
  } catch (err) {
    return fail(formatError(err));
  }
}

module.exports = { run };
