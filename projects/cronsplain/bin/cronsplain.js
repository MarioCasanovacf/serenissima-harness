#!/usr/bin/env node
'use strict';

const { run } = require('../lib/cli');

const result = run(process.argv.slice(2));
if (result.stdout) process.stdout.write(result.stdout);
if (result.stderr) process.stderr.write(result.stderr);
process.exit(result.code);
