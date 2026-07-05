'use strict';

/**
 * tests/test_integration.js — end-to-end tests that shell out to the real
 * `bin/cronsplain.js` entry point via node:child_process (spawnSync), the
 * way a real user would invoke it: `node bin/cronsplain.js <args...>`.
 *
 * spawnSync (not execFileSync) is used deliberately so a non-zero exit
 * code is observed directly on the returned object instead of being
 * thrown as a JS exception — both the happy path and the error paths are
 * asserted the same way.
 */

const path = require('node:path');
const { test } = require('node:test');
const assert = require('node:assert');
const { spawnSync } = require('node:child_process');

const BIN_PATH = path.join(__dirname, '..', 'bin', 'cronsplain.js');

function runCli(args) {
  return spawnSync(process.execPath, [BIN_PATH, ...args], {
    encoding: 'utf8',
    timeout: 10000,
  });
}

function assertNoStackTrace(text) {
  assert.ok(
    !/\bat .*\(.*:\d+:\d+\)/.test(text),
    `expected no stack-trace frame in: ${JSON.stringify(text)}`
  );
}

test('integration: explain prints the English sentence and exits 0', () => {
  const result = runCli(['explain', '*/15 0 * * 1-5']);
  assert.strictEqual(result.status, 0);
  assert.strictEqual(result.stdout, 'Every 15 minutes during hour 0, on Monday through Friday.\n');
  assert.strictEqual(result.stderr, '');
});

test('integration: next with --from and --count prints exactly --count ISO-8601 UTC lines and exits 0', () => {
  const result = runCli(['next', '0 0 * * *', '--from', '2026-01-01T00:00:00Z', '--count', '3']);
  assert.strictEqual(result.status, 0);
  assert.strictEqual(result.stderr, '');
  const lines = result.stdout.trim().split('\n');
  assert.strictEqual(lines.length, 3);
  assert.deepStrictEqual(lines, [
    '2026-01-02T00:00:00.000Z',
    '2026-01-03T00:00:00.000Z',
    '2026-01-04T00:00:00.000Z',
  ]);
});

test('integration: an invalid expression yields a non-zero exit and a clean one-line stderr, no stack trace', () => {
  const result = runCli(['explain', 'not a cron expression']);
  assert.notStrictEqual(result.status, 0);
  assert.strictEqual(result.stdout, '');
  assert.ok(result.stderr.length > 0);
  assert.strictEqual(result.stderr.trim().split('\n').length, 1, 'stderr must be a single line');
  assertNoStackTrace(result.stderr);
});

test('integration: a rejected Vixie macro (@daily) yields a non-zero exit and a clean stderr', () => {
  const result = runCli(['explain', '@daily']);
  assert.notStrictEqual(result.status, 0);
  assertNoStackTrace(result.stderr);
});

test('integration: an impossible schedule (0 0 30 2 *) fails cleanly and does not hang', () => {
  const result = runCli(['next', '0 0 30 2 *', '--from', '2026-01-01T00:00:00Z']);
  assert.notStrictEqual(result.status, null, 'process must not have been killed by the timeout (must not hang)');
  assert.notStrictEqual(result.status, 0);
  assert.strictEqual(result.stdout, '');
  assert.strictEqual(result.stderr.trim().split('\n').length, 1, 'stderr must be a single line');
  assertNoStackTrace(result.stderr);
});

test('integration: --help exits 0 and prints usage', () => {
  const result = runCli(['--help']);
  assert.strictEqual(result.status, 0);
  assert.ok(result.stdout.includes('Usage: cronsplain <command>'));
});

test('integration: no arguments yields a non-zero exit and a clean stderr', () => {
  const result = runCli([]);
  assert.notStrictEqual(result.status, 0);
  assert.ok(result.stderr.length > 0);
  assertNoStackTrace(result.stderr);
});

test('integration: an unknown command yields a non-zero exit and a clean stderr', () => {
  const result = runCli(['bogus-command']);
  assert.notStrictEqual(result.status, 0);
  assertNoStackTrace(result.stderr);
});

test('integration: missing required <expr> yields a non-zero exit and a clean stderr', () => {
  const result = runCli(['next']);
  assert.notStrictEqual(result.status, 0);
  assertNoStackTrace(result.stderr);
});
