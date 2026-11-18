# Design T-484: the harness console (a local web interface)

Ruled by the operator on 2026-11-17, in answers to the coordinator's questions:

- One interface with four tabs: Live (a wave running), Operator (what waits on the
  operator), Society (names, acts, contracts, suits, precedents), Flows (recipes).
- A local web page, served from the operator's machine, no internet needed.
- It watches, launches, approves, and edits flows.
- It is public in the repository: anyone who clones the repo can run it.
- Launch has two modes: start agents through the Claude Code CLI in print mode
  (`claude -p`, the operator's own subscription, the same pattern as
  `gemini_headless_runner.py`), or only enqueue tasks on the board.
- Approvals: pending decisions, the operator's verdict on a task in review, and the
  gate between one wave and the next.
- Flows are recipes edited with forms. Every agent and task shows a tooltip with what
  that agent is doing right now.
- Spanish and English, with a toggle.

## 1. Shape

```
.harness/bin/console.py        stdlib HTTP server (ThreadingHTTPServer), JSON API, SSE
.harness/bin/flow_runner.py    validates, launches and gates flow runs
.harness/bin/operator_desk.py  decisions, rulings, operator verdicts, wave gates
.harness/ui/                   index.html, app.js, styles.css, i18n/es.json, i18n/en.json
.harness/flows/*.json          flow recipes (tracked)
.harness/decisions/D-NNN.json  pending decision cards (tracked)
.harness/rulings/R-NNN.json    rulings made through the console (tracked, append-only)
.harness/runs/<run-id>/        run state and per-step logs (untracked, .gitignore)
```

Standard library only, no build step, no package installs. Python 3.9 compatible.

## 2. Safety rules (every worker, every file)

1. `console.py` binds 127.0.0.1 only. It refuses any request whose Host header is not
   `127.0.0.1:<port>` or `localhost:<port>` (DNS rebinding).
2. Every state-changing request (POST, PUT) must carry the header `X-Console-Token`
   equal to a random token minted at server start and injected into the served
   `index.html`. GET is read-only and changes nothing on disk.
3. Every write goes through the harness's own tools (`blackboard.py`, `lock.py`,
   `session.py`, `operator_desk.py`, `flow_runner.py`). Nothing hand-edits
   `blackboard.json`, `roster.json`, acts or warrants.
4. The console never signs anything and never reads private keys. A step that needs
   the operator's signature shows the exact command as copyable text. It never serves
   `.harness/keys`, private material under `.harness/trust` or
   `.harness/constitutional`, or `.harness/notify_config.json`.
5. Every string the API returns passes one redaction function: the home directory
   becomes `~`, the OS username becomes `<user>`, system temp paths become `<tmp>`.
6. Commit and push are two separate operator buttons. Each runs the leak scan first and
   refuses on any hit; each shows the diff stat before it acts. Push sends only the
   current branch, never `main`, never with force.
7. `flow_runner.py` never passes `--dangerously-skip-permissions`. Permission flags come
   from the recipe, with a conservative default, and the repo's own hooks (lock check,
   data-loss guard) still apply inside every agent session.
8. Tests never call a real model: `HARNESS_CLAUDE_BIN` points the runner at a fake
   executable that prints a scripted final result.

## 3. Files

### Flow recipe, `.harness/flows/<name>.json`

```json
{
  "name": "speed-wave",
  "description": "one line",
  "tests": "changed",
  "gate": true,
  "defaults": {"model": "sonnet", "effort": "high", "rounds": 2,
               "permissions": ["--permission-mode", "acceptEdits"]},
  "tracks": [
    {"task": "T-480", "verify_task": "T-481", "producer": "worker-x",
     "verifier": "verifier-x", "verify_first": false, "brief": "what to do"}
  ]
}
```

`tests` is `changed` (agents run only the tests their change touches; the runner runs
the full suite once at the gate) or `named` (the brief names the test files). Each
track may override any default. `validate` refuses unknown keys, a task id not on the
board, a producer equal to its verifier, rounds outside 1..3, and permission flags on a
deny list (`--dangerously-skip-permissions`).

### Decision card, `.harness/decisions/D-NNN.json`

```json
{"id": "D-001", "title": "short", "question": "plain words",
 "recommendation": "yes", "if_yes": "what happens", "if_no": "what happens",
 "options": ["yes", "no"], "blocks": ["T-123"], "status": "open",
 "created": "2026-11-17"}
```

### Ruling, `.harness/rulings/R-NNN.json` (append-only, never edited)

```json
{"id": "R-001", "decision": "D-001", "choice": "yes", "note": "",
 "ts": "ISO-8601 Z", "by": "operator", "via": "console"}
```

Ruling a decision writes one new R file and flips the card's status to `ruled` through
`operator_desk.py`. Dated records (`operator-rulings-*.md`, `coordinator-decisions-*`)
are never edited by any of this.

### Run state, `.harness/runs/<run-id>/run.json`

```json
{"id": "...", "flow": "speed-wave", "mode": "agents", "status": "running",
 "started": "...", "steps": [{"track": "T-480", "role": "producer", "round": 1,
 "agent": "worker-x", "status": "running", "started": "...", "ended": null,
 "last_action": "Bash: fast_tests.py test_fast_tests.py", "verdict": null}],
 "gate": {"status": "pending", "suite": null}}
```

Status values: `running`, `awaiting_operator` (gate), `approved`, `rejected`,
`failed`, `stopped`. `last_action` is the newest harness event attributed to that
agent (a claim, a lock on a file, a test run, a handoff), read from the event log. The
runner keeps only each step's final result, for the run report; it reads nothing the
agent prints while it works.

## 4. flow_runner.py

`validate <name>`, `launch <name> --mode agents|enqueue`, `status [<run-id>]`,
`gate <run-id> --approve|--reject [--note]`, `stop <run-id>`.

- `enqueue`: ensures each track's tasks exist on the board and does nothing else.
- `agents`: registers producer names with `session.py` (coordinator act), then for
  each track, in parallel across tracks: producer, then verifier, up to `rounds`; a
  verifier that sends the task back starts the next round. Each step runs the CLI
  binary in print mode with its single JSON final result, cwd at the repo root, and a prompt
  built from one PROTOCOL template (the 2026-11-17 wave rule: only the tests your
  change touches, never the full suite, never sleep, return blocked instead) plus the
  track's brief. Verdicts are read back from the board, not trusted from the agent's
  text. Producer names are unregistered at the end.
- With `gate: true`, after all tracks the runner runs `fast_tests.py` once, records the
  result in `run.json`, and stops at `awaiting_operator`.
- The run continues in a detached background process; the console reads `run.json`.
- Every step start and end is logged through `log_event.py`.
- Check the real CLI flags with `claude --help` before coding them; do not guess.

## 5. operator_desk.py

`decisions [--json]`, `rule <D-id> --choice C [--note]`, `verdict <T-id> --done|--open
--note`, `gate <run-id> --approve|--reject`, `commit --message-file F`, `push`.

- `verdict` acts as agent `operator` through `blackboard.py`, only on a task in review,
  and refuses when the operator is that task's producer.
- `commit` and `push` implement safety rule 6, with the leak-scan pattern held in one
  constant that tests pin.

## 6. console.py API

GET (read-only): `/` (index.html with the token), `/ui/*` (static files),
`/api/board`, `/api/locks`, `/api/events?since=N`, `/api/stream` (Server-Sent
Events: new event-log lines and a `changed` ping when board, run or decision files
change, polled once a second), `/api/activity`, `/api/society`, `/api/decisions`,
`/api/flows`, `/api/flows/<name>`, `/api/runs`, `/api/runs/<id>`, `/api/charts/waves`.

POST/PUT (token): `/api/tasks` (add-task form), `/api/tasks/<id>/verdict`,
`/api/decisions/<id>/rule`, `PUT /api/flows/<name>` (validated before save),
`/api/flows/<name>/launch` (`{"mode": "agents" | "enqueue"}`),
`/api/runs/<id>/gate`, `/api/runs/<id>/stop`, `/api/git/commit`, `/api/git/push`.

`/api/activity` is what the tooltips show, one entry per agent name:
`{name, task, role, step, since, last_action, last_note, tests_run, source}`. Sources,
merged: run.json step status, the board (claims, last note), locks, and the event log.
`fast_tests.py` logs a `tests_run` event (files selected, counts, seconds) so the
tooltip can show a test run.

`/api/society`: roster names with colegiado, plaza and revoked flag; warrants with
signed or unsigned; acts per name (count, last kind, retractions); forks count; cases
with suit state in words; precedents list. Read through the existing tools' JSON output
or their read functions, never by re-implementing their rules.

Start: `python3 .harness/bin/console.py [--port 8765] [--root R] [--open]`. It prints
the local URL. `--root` serves a throwaway root for tests and demos.

## 7. The page

Four tabs, a language toggle (es/en, remembered in localStorage), live updates over
SSE, no external requests at all (no web fonts, no CDNs).

- **Live**: one lane per agent of the running wave (name, task, step, elapsed time),
  task cards by status, the full-suite result, a bar chart of wave minutes. Hovering an
  agent or a task shows the activity tooltip.
- **Operator**: decision cards (question, recommendation, if yes, if no, a choice
  button), tasks in review with a verdict button, waves awaiting the gate, commands
  waiting for the operator's signature as copyable text, the latest epic-close report,
  and the commit and push buttons with the diff stat.
- **Society**: names and seats, acts and chains, contracts, suits with their state,
  precedents. Each item expands in place.
- **Flows**: the recipe list, a form editor (tracks as rows; producer, verifier,
  rounds, model, brief), validate and save, launch as agents or enqueue, and run
  history with each run's steps.

Visual language: warm paper ground `#f3efe4`, ink `#1a1814`, grey `#6b655c`, forest
`#2e4a3f` (done, approve), ochre `#a87333` (in progress, attention), oxblood `#6e1f1f`
(refused, rejected). Serif display stack (Didot, "Bodoni 72", Georgia, serif), text
stack ("EB Garamond", Garamond, Georgia, serif), interface and numbers stack ("IBM Plex
Sans", "Helvetica Neue", Arial, sans-serif) and mono ("IBM Plex Mono", Menlo,
monospace), all system-installed or falling back. Tabular figures. No emojis. Works at
1280 px and down to 400 px.

## 8. Tests

`test_console.py` (server on a throwaway root and a free port: Host check, token check,
redaction, every GET shape, no GET writes anything), `test_flow_runner.py` (fake CLI:
a produce-verify-done track, a sent-back second round, enqueue mode, gate,
validation refusals), `test_operator_desk.py` (rule, verdict refusals, gate, leak-scan
refusal on commit and push, no push of `main`, no force). The page is checked by a
static test that every i18n key exists in both languages and that `index.html` loads
nothing from another origin.

## 9. As built (2026-11-18): where the build departs from this design

The dispatched producers stopped before writing code, so the coordinator built
`console.py`, `flow_runner.py` and the page directly from this document. Departures,
each for the reason given:

- `flow_runner.py` registers no session holders. Each step is its own CLI process whose
  ambient identity is the agent's name, so the lock hook already matches that agent's own
  locks; registering would only let the coordinator's session write through them, and
  `session.py` keeps registration a coordinator-only act.
- A track may carry a `title`. Validation accepts a task id that is not yet on the board
  only when the track has one, and launch creates it (`add-task`, epic `flow:<name>`),
  with the verify task depending on the task, the cascade the board already uses.
- Two run statuses were added: `enqueued` (an enqueue run) and `finished` (an agents run
  with no gate whose every track ended `done`).
- The prompt goes to the CLI on stdin, so a variadic flag such as `--allowedTools` cannot
  swallow it. Permission flags come from an allow list (`--permission-mode` with any mode
  but `bypassPermissions`, and the tool-list flags); everything else is refused.
- Each step has a timeout (recipe key `timeout`, 60 to 7200 seconds, default 1800).
- Extra read routes: `/api/operator` (everything the Operator tab shows, in one answer)
  and `/api/close-report` (`close_checks.py --json epic-close`, read-only). The unsigned
  drafts are listed with the operator's own commands, taken from `warrant.py`.
- The wave chart reads its baseline from `.harness/ui/waves-measured.json` (the three
  waves measured on 2026-11-17) and adds every agents run.
- The page accepts `?tab=` and `?lang=`, and `#still` turns off the live stream so a
  headless browser can take a screenshot.
- No `?demo` mode and no `.harness/ui/demo.json` (T-491 criterion 3). That mode existed
  so the page could be built before the server; the page and the server were built
  together, so the page always reads the API. A demonstration on sample data runs the
  real server on a throwaway root: `console.py --root <dir>`. Named as a gap by the
  page's verifier on 2026-11-18.
