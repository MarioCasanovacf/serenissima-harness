'use strict';

/**
 * tests/test_cli.js — in-process tests for lib/cli.js's run(argv).
 *
 * `run()` is pure (no process.stdout.write / process.exit of its own), so
 * every assertion here calls it directly and inspects the returned
 * { code, stdout, stderr } object — no subprocess involved (see
 * tests/test_integration.js for the shell-out end-to-end coverage).
 */

const { test } = require('node:test');
const assert = require('node:assert');

const { run } = require('../lib/cli');

function assertNoStackTrace(text) {
  assert.ok(
    !/\bat .*\(.*:\d+:\d+\)/.test(text) && !text.includes('.stack'),
    `expected no stack-trace frame in: ${JSON.stringify(text)}`
  );
}

// ---------------------------------------------------------------------------
// explain
// ---------------------------------------------------------------------------

test('explain: prints the English sentence to stdout with code 0', () => {
  const result = run(['explain', '*/15 0 * * 1-5']);
  assert.strictEqual(result.code, 0);
  assert.strictEqual(result.stderr, '');
  assert.strictEqual(
    result.stdout,
    'Every 15 minutes during hour 0, on Monday through Friday.\n'
  );
});

test('explain: the pinned all-wildcard sentence', () => {
  const result = run(['explain', '* * * * *']);
  assert.strictEqual(result.code, 0);
  assert.strictEqual(result.stdout, 'Every minute.\n');
});

test('explain --help: usage text on stdout, code 0', () => {
  const result = run(['explain', '--help']);
  assert.strictEqual(result.code, 0);
  assert.strictEqual(result.stderr, '');
  assert.ok(result.stdout.includes('Usage: cronsplain explain <expr>'));
});

// ---------------------------------------------------------------------------
// next
// ---------------------------------------------------------------------------

test('next: default count (5), fixed --from, UTC ISO-8601 Z lines, ascending, exclusive', () => {
  const result = run(['next', '0 0 * * *', '--from', '2026-01-01T00:00:00Z']);
  assert.strictEqual(result.code, 0);
  assert.strictEqual(result.stderr, '');
  const lines = result.stdout.trim().split('\n');
  assert.strictEqual(lines.length, 5, 'default --count is 5');
  assert.deepStrictEqual(lines, [
    '2026-01-02T00:00:00.000Z',
    '2026-01-03T00:00:00.000Z',
    '2026-01-04T00:00:00.000Z',
    '2026-01-05T00:00:00.000Z',
    '2026-01-06T00:00:00.000Z',
  ]);
  for (const line of lines) {
    assert.ok(line.endsWith('Z'), `expected trailing Z in ${line}`);
    assert.ok(!Number.isNaN(new Date(line).getTime()), `expected a valid ISO date in ${line}`);
  }
});

test('next: --count overrides the default and controls line count', () => {
  const result = run(['next', '0 9 * * 1-5', '--from', '2026-01-01T00:00:00Z', '--count', '3']);
  assert.strictEqual(result.code, 0);
  const lines = result.stdout.trim().split('\n');
  assert.strictEqual(lines.length, 3);
});

test('next: naive --from (no offset/Z) is interpreted as UTC', () => {
  const naive = run(['next', '0 0 * * *', '--from', '2026-01-01T00:00:00', '--count', '1']);
  const withZ = run(['next', '0 0 * * *', '--from', '2026-01-01T00:00:00Z', '--count', '1']);
  assert.strictEqual(naive.code, 0);
  assert.strictEqual(naive.stdout, withZ.stdout);
});

test('next: --from with an explicit offset is converted to its UTC instant', () => {
  // 2026-01-01T00:00:00+02:00 == 2025-12-31T22:00:00Z; the next 00:00 UTC
  // daily occurrence strictly after that instant is 2026-01-01T00:00:00Z.
  const result = run(['next', '0 0 * * *', '--from', '2026-01-01T00:00:00+02:00', '--count', '1']);
  assert.strictEqual(result.code, 0);
  assert.strictEqual(result.stdout, '2026-01-01T00:00:00.000Z\n');
});

test('next: --from default is now() (produces occurrences strictly in the future)', () => {
  const before = Date.now();
  const result = run(['next', '* * * * *', '--count', '1']);
  assert.strictEqual(result.code, 0);
  const returned = new Date(result.stdout.trim()).getTime();
  assert.ok(returned > before, 'expected the returned occurrence to be after "now" at call time');
});

test('next --help: usage text on stdout, code 0', () => {
  const result = run(['next', '--help']);
  assert.strictEqual(result.code, 0);
  assert.strictEqual(result.stderr, '');
  assert.ok(result.stdout.includes('Usage: cronsplain next <expr>'));
});

// ---------------------------------------------------------------------------
// top-level help
// ---------------------------------------------------------------------------

test('--help / -h at the top level: usage text on stdout, code 0', () => {
  for (const flag of ['--help', '-h']) {
    const result = run([flag]);
    assert.strictEqual(result.code, 0);
    assert.strictEqual(result.stderr, '');
    assert.ok(result.stdout.includes('Usage: cronsplain <command>'));
  }
});

// ---------------------------------------------------------------------------
// error cases: non-zero code, clean one-line stderr, no stack trace
// ---------------------------------------------------------------------------

test('no command: non-zero exit, clean stderr, no stack trace', () => {
  const result = run([]);
  assert.notStrictEqual(result.code, 0);
  assert.strictEqual(result.stdout, '');
  assert.ok(result.stderr.length > 0);
  assertNoStackTrace(result.stderr);
});

test('unknown command: non-zero exit, clean stderr', () => {
  const result = run(['bogus']);
  assert.notStrictEqual(result.code, 0);
  assert.ok(result.stderr.includes('bogus'));
  assertNoStackTrace(result.stderr);
});

test('explain with an invalid cron expression: non-zero exit, no stack trace', () => {
  const result = run(['explain', 'not a cron']);
  assert.notStrictEqual(result.code, 0);
  assert.strictEqual(result.stdout, '');
  assert.ok(result.stderr.trim().split('\n').length === 1, 'stderr must be a single line');
  assertNoStackTrace(result.stderr);
});

test('explain with a Vixie macro (out of grammar, Q1): non-zero exit, clean message', () => {
  const result = run(['explain', '@daily']);
  assert.notStrictEqual(result.code, 0);
  assertNoStackTrace(result.stderr);
});

test('explain missing <expr>: non-zero exit, clean stderr', () => {
  const result = run(['explain']);
  assert.notStrictEqual(result.code, 0);
  assert.ok(result.stderr.length > 0);
  assertNoStackTrace(result.stderr);
});

test('next missing <expr>: non-zero exit, clean stderr', () => {
  const result = run(['next']);
  assert.notStrictEqual(result.code, 0);
  assertNoStackTrace(result.stderr);
});

test('next with an invalid --count: non-zero exit, clean stderr', () => {
  for (const bad of ['0', '-1', 'abc', '3.5']) {
    const result = run(['next', '* * * * *', '--count', bad]);
    assert.notStrictEqual(result.code, 0, `expected failure for --count ${bad}`);
    assertNoStackTrace(result.stderr);
  }
});

test('next with an unparsable --from: non-zero exit, clean stderr', () => {
  const result = run(['next', '* * * * *', '--from', 'not-a-date']);
  assert.notStrictEqual(result.code, 0);
  assertNoStackTrace(result.stderr);
});

test('next with an unknown flag: non-zero exit, clean stderr', () => {
  const result = run(['next', '* * * * *', '--bogus', '1']);
  assert.notStrictEqual(result.code, 0);
  assertNoStackTrace(result.stderr);
});

test('next with an impossible schedule (Feb 30th): non-zero exit, clean one-line stderr, no hang', () => {
  const result = run(['next', '0 0 30 2 *', '--from', '2026-01-01T00:00:00Z']);
  assert.notStrictEqual(result.code, 0);
  assert.strictEqual(result.stdout, '');
  const stderrLines = result.stderr.trim().split('\n');
  assert.strictEqual(stderrLines.length, 1, 'stderr must be a single line');
  assertNoStackTrace(result.stderr);
});

test('extra positional arguments are rejected', () => {
  const explainResult = run(['explain', 'a', 'b']);
  assert.notStrictEqual(explainResult.code, 0);
  assertNoStackTrace(explainResult.stderr);

  const nextResult = run(['next', 'a', 'b']);
  assert.notStrictEqual(nextResult.code, 0);
  assertNoStackTrace(nextResult.stderr);
});
