# Gemini native adapter scope

Repository capability note (non-normative): Gemini CLI automatically discovers repo-scoped
workspace skills from [.agents/skills/](.agents/skills/), as documented in the official
[Gemini CLI skill discovery tiers](https://geminicli.com/docs/cli/using-agent-skills/). This
discovery is independent of context-file injection through [.gemini/settings.json](.gemini/settings.json).
It does not change the precedence of gemini.md or the shared blackboard lifecycle, and it is not a
claim that this repository provides an installable Gemini distribution.

This file interprets the existing `gemini.md` constitution for the native surfaces shipped by
this repository; it does not replace that constitution or the shared blackboard invariants.

When work starts through `.gemini/agents/`, a `/harness:*` command, an `.agents/workflows/`
workflow, or `.harness/bin/gemini_headless_runner.py`, Gemini CLI or Antigravity may act as the
coordinator and dispatch Gemini harness identities directly. The reference in `gemini.md` to a
main Claude Code coordinator describes the optional cross-engine Claude-to-Gemini topology, not
a requirement for these Gemini-native entry points. Every route still uses legal claims, TTL
locks, bounded execution, replayable evidence, and a verifier identity different from the
producer.

Hard boundary: a Claude-coordinated session must never invoke `gemini_headless_runner.py` to
outsource reasoning to another model — the no-external-LLM rule extends to local model
subprocesses; engines coordinate through the blackboard, not through each other.

Remote webhooks, notifications, messaging, telemetry export, and any other external side effect
are disabled unless the human operator explicitly opts in for that run and approves the target.
Local `events.jsonl` evidence remains the default observability floor.
