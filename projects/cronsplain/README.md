# cronsplain

`cronsplain` is a zero-dependency Node.js CLI that explains standard
5-field cron expressions in plain English and computes their upcoming
occurrences in UTC.

```
cronsplain explain <expr>
cronsplain next <expr> [--from ISO] [--count N]
```

- **explain** renders a cron expression as one deterministic English
  sentence.
- **next** prints the next N occurrences of a cron expression, one per
  line, in UTC ISO-8601 with a trailing `Z`.

Zero npm dependencies — the whole package is CommonJS + Node's built-in
`node:test` runner. Tested on `node v24`; `engines.node` requires `>=18`
(the `node:test` module has been built in since Node 18).

## Install / run

No install step is required (zero dependencies). From inside
`projects/cronsplain/`, run either style:

```sh
# Directly via the entry-point script:
node bin/cronsplain.js explain "*/15 0 * * 1-5"

# Or via the package.json "bin" target, once linked/installed
# (npm link, or npm install -g .) as `cronsplain`:
cronsplain explain "*/15 0 * * 1-5"
```

Both invocation styles run the exact same code path — `bin/cronsplain.js`
is a thin shebang (`#!/usr/bin/env node`) wrapper around
`lib/cli.js`'s `run(argv)`.

Run `cronsplain --help`, `cronsplain explain --help`, or
`cronsplain next --help` for full usage text.

## Supported grammar

Standard 5-field POSIX cron: `minute hour dayOfMonth month dayOfWeek`.

| Field        | Range | Names |
|--------------|-------|-------|
| minute       | 0-59  | -     |
| hour         | 0-23  | -     |
| day of month | 1-31  | -     |
| month        | 1-12  | `JAN`-`DEC` (case-insensitive) |
| day of week  | 0-7   | `SUN`-`SAT` (case-insensitive); `SUN`=0, and `7` is an alias for Sunday |

Each field accepts, and these may be combined with commas into a list:

- `*` — wildcard (every value in the field's range).
- `a` — a single value, or (month/dayOfWeek only) a 3-letter name.
- `a-b` — an inclusive range (`b` must be `>= a`; a reversed range like
  `10-5` is rejected).
- `*/n` or `a-b/n` — a step of `n` starting at the wildcard's or range's
  start.
- `x,y,z` — a comma-separated list combining any of the above.

**Out of scope (rejected with a clean error):** Vixie extensions —
`@daily`/`@hourly`/`@reboot`-style macros, `L`, `W`, `#`, `?`, and the
bare start-step form `a/n` (e.g. `3/5`, as opposed to the supported
`a-b/n`) are all invalid input and produce a `CronParseError`, not a
silent best-effort interpretation.

### The day-of-month / day-of-week OR note

This is the classic cron quirk, preserved here on purpose: when **both**
the day-of-month and day-of-week fields are restricted (i.e. neither is
the bare `*`), a day matches if it satisfies **either** field (a union/OR
of the two, not an AND). When only one of the two fields is restricted,
only that field constrains matching. When both are `*`, every day
matches. For example, `0 0 13 * 5` fires at midnight on the 13th of
**every** month **and** on **every** Friday — not only on Fridays that
happen to be the 13th.

### UTC / timezone note

All matching and all `next` output is in **UTC**. `--from` accepts an
ISO-8601 string:

- A **naive** value with no offset and no trailing `Z` (e.g.
  `2026-01-01T00:00:00`) is interpreted **as UTC**.
- A value carrying an explicit offset or a trailing `Z` (e.g.
  `2026-01-01T00:00:00+02:00`) is respected and converted to its UTC
  instant before matching.

Output timestamps are always ISO-8601 with a trailing `Z`
(`Date.prototype.toISOString()`), e.g. `2026-01-02T00:00:00.000Z`.

`next` occurrences are **strictly after** `--from` (exclusive) — if
`--from` itself falls exactly on a matching minute, that minute is
skipped and the first occurrence returned is the following match.

## Commands

### `explain <expr>`

Prints a human-readable English description of `<expr>` and exits `0`.

```sh
$ node bin/cronsplain.js explain "*/15 0 * * 1-5"
Every 15 minutes during hour 0, on Monday through Friday.

$ node bin/cronsplain.js explain "0 0 13 * 5"
At 00:00, on the 13th of the month or on Friday.

$ node bin/cronsplain.js explain "* * * * *"
Every minute.
```

An invalid expression exits non-zero with a single-line message on
stderr and prints nothing to stdout — never a raw stack trace:

```sh
$ node bin/cronsplain.js explain "@daily"
cronsplain: Expected 5 whitespace-separated fields, got 1
$ echo $?
1
```

### `next <expr> [--from ISO] [--count N]`

Prints the next `N` occurrences of `<expr>`, one per line, in UTC
ISO-8601 with a trailing `Z`, and exits `0`.

- `--count N` — how many occurrences to print. **Default: 5.**
- `--from ISO` — the exclusive starting instant. **Default: now().**

```sh
$ node bin/cronsplain.js next "0 9 * * 1-5" --from 2026-01-01T00:00:00Z --count 3
2026-01-01T09:00:00.000Z
2026-01-02T09:00:00.000Z
2026-01-05T09:00:00.000Z

$ node bin/cronsplain.js next "0 0 * * *" --from 2026-01-01T00:00:00Z
2026-01-02T00:00:00.000Z
2026-01-03T00:00:00.000Z
2026-01-04T00:00:00.000Z
2026-01-05T00:00:00.000Z
2026-01-06T00:00:00.000Z
```

A schedule that can never be satisfied (e.g. day-of-month 30 in a
month-restricted-to-February expression) fails cleanly — it does not
hang and does not silently return fewer dates than requested:

```sh
$ node bin/cronsplain.js next "0 0 30 2 *" --from 2026-01-01T00:00:00Z
cronsplain: cronsplain schedule: no valid day found within 3660 day-carries starting after 2026-1-1 (schedule is likely impossible, e.g. a day-of-month that never exists in the given month, such as '0 0 30 2 *')
$ echo $?
1
```

## Running the tests

From `projects/cronsplain/`:

```sh
node --test tests/*.js
```

(Using `node --test` with no arguments also works, since `node --test`'s
default glob discovery finds every file under `tests/`; `tests/*.js` is
the form `package.json`'s `"test"` script and this repository's
convention pin, so both invocations run the identical suite.)

This runs every `test_*.js` file — field bounds/name maps, the parser
grammar, the promoted schedule engine (including the golden vectors from
`candidates/vectors.js`), `explain`'s sentence rendering, the in-process
CLI tests (`tests/test_cli.js`), and the subprocess end-to-end tests
(`tests/test_integration.js`) that shell out to `bin/cronsplain.js`
exactly as a real user would invoke it.

Zero npm dependencies are required to run either the CLI or its test
suite.
