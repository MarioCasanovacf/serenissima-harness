#!/usr/bin/env python3
"""One-command harness migration to another project (stdlib only, py3.9+).

Ports the deterministic control plane of the Universal Agent Harness from
THIS repo (the source of truth) into a target project directory: the bin/
CLIs, the Claude Code hooks/agents/skill, and the governing docs -- with a
freshly reset board/state (no task history crosses over) and CLAUDE.md
merged rather than overwritten. This encodes the "Llevar el harness a otro
repo" recipe from docs/harness-explainer.html (component 10, id="migrar")
as a single idempotent, dry-run-able CLI -- the harness_init.py the
explainer promises for generation 3.

Usage:
  python3 .harness/bin/migracion_proyecto.py <target-dir> [--dry-run] [--force]

Examples:
  # Preview the full action plan without touching anything
  python3 .harness/bin/migracion_proyecto.py ~/Proyectos/mi-app --dry-run

  # Perform the migration
  python3 .harness/bin/migracion_proyecto.py ~/Proyectos/mi-app

  # Re-run over an already-migrated target (backs up the old .harness first)
  python3 .harness/bin/migracion_proyecto.py ~/Proyectos/mi-app --force

What it does (see docs/harness-explainer.html#migrar for the prose version):
  1. COPY MACHINERY -- .harness/bin/ (all CLIs, including this one), .harness/README.md,
                        .claude/settings.json, .claude/agents/, .claude/skills/harness-status,
                        ORCHESTRATION.md, USAGE.md. Target-owned files with these SAME NAMES
                        are never silently clobbered (see SAFETY below): the .harness/bin and
                        .harness/README.md items are covered by the whole-.harness backup gate
                        (they only ever land on a freshly-emptied .harness/), but
                        .claude/settings.json, ORCHESTRATION.md, USAGE.md, and any
                        colliding-name file under .claude/agents/ or
                        .claude/skills/harness-status get their own per-file guard.
  2. RESET STATE    -- fresh blackboard.json (tasks={}, generation carried over from the
                        source, one migration announcement); fresh state.json (schema/
                        limits/human_gates/agents.registry kept verbatim, reputation
                        zeroed, run counters nulled, evolution.generation preserved with
                        an empty pending/accepted-mutations queue and a provenance note);
                        empty .harness/locks/ + .harness/tasks/; empty logs/events.jsonl
                        + logs/transcript.jsonl; NO session_holders.json (nothing
                        registered yet); template plan.md + task.json.
  3. INTEGRATE      -- merge CLAUDE.md between BEGIN/END UNIVERSAL-HARNESS markers
                        (never overwrites existing content; copies fresh if the target
                        has no CLAUDE.md; skips with a notice if markers are already
                        present); appends dedup'd .gitignore entries for the harness's
                        ephemeral runtime state IF the target is a git repo (creates
                        .gitignore if missing).

SAFETY:
  - Refuses if <target-dir> does not exist.
  - Refuses if <target-dir> exists but is not a directory (says "is not a
    directory", not "does not exist").
  - Refuses if <target-dir>/.harness already exists, unless --force.
  - --force backs up (renames, NEVER deletes) the existing .harness to
    .harness.bak-<n> (first free n) before writing the fresh one.
  - Target-owned .claude/settings.json, ORCHESTRATION.md, USAGE.md, and any
    colliding-name file under .claude/agents/ or .claude/skills/harness-status
    are NEVER silently overwritten: without --force each collision is
    reported as [SKIP-EXISTS] and the target's own file is left byte-for-byte
    intact (diff manually if you want to reconcile); with --force each
    colliding file is individually backed up by RENAME to <name>.bak-<n>
    (first free n, never deleted) before the new copy lands, reported as
    [BACKUP] followed by [COPY]. Non-colliding files in those same
    directories are copied normally regardless of --force.
  - --dry-run prints the full action plan and writes NOTHING (verify with
    `find <target-dir> -newer <marker-file>` -- see T-032 acceptance probe a).
  - Never modifies the SOURCE repo: every write targets <target-dir>.

Exit codes: 0 ok, 1 refused (safety gate), 2 bad invocation (argparse).
"""
import argparse
import copy
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_common as hc

BEGIN_MARKER = "<!-- BEGIN UNIVERSAL-HARNESS -->"
END_MARKER = "<!-- END UNIVERSAL-HARNESS -->"

# Source paths always resolve to THIS repo: hc.ROOT is derived from
# harness_common.py's own location, and harness_common.py travels alongside
# this script (both live in .harness/bin/) -- so after this file is copied
# into a target and re-run there, the SAME code would resolve to the
# target as its own "source" (self-propagating, per T-032 acceptance e).
SRC_ROOT = hc.ROOT
SRC_HARNESS_BIN = SRC_ROOT / ".harness" / "bin"
SRC_HARNESS_README = SRC_ROOT / ".harness" / "README.md"
SRC_CLAUDE_SETTINGS = SRC_ROOT / ".claude" / "settings.json"
SRC_CLAUDE_AGENTS = SRC_ROOT / ".claude" / "agents"
SRC_CLAUDE_SKILL = SRC_ROOT / ".claude" / "skills" / "harness-status"
SRC_ORCHESTRATION = SRC_ROOT / "ORCHESTRATION.md"
SRC_USAGE = SRC_ROOT / "USAGE.md"
SRC_CLAUDE_MD = SRC_ROOT / "CLAUDE.md"
SRC_STATE = SRC_ROOT / ".harness" / "state.json"
SRC_BLACKBOARD = SRC_ROOT / ".harness" / "blackboard.json"

GITIGNORE_ENTRIES = [
    "# Universal Agent Harness (seeded by migracion_proyecto.py) -- ephemeral runtime state",
    ".harness/locks/*.lock",
    ".harness/locks/.guard",
    ".harness/logs/*.jsonl",
    ".harness/session_holders.json",
]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _next_backup_path(path):
    """First free '<path>.bak-<n>' sibling of path (works for files or dirs)."""
    n = 1
    while True:
        candidate = path.parent / "{}.bak-{}".format(path.name, n)
        if not candidate.exists():
            return candidate
        n += 1


def _is_git_repo(target):
    return (target / ".git").exists()


def _plan_template(source_root, source_gen, now):
    return (
        "# Harness Build Plan (maintained by Thinkers; workers execute, verifiers gate)\n\n"
        "> Owner: TBD -- assign a planner agent for this project.\n"
        "> Rule: this file states WHY and IN WHAT ORDER; the blackboard states WHO and WHAT NOW.\n"
        "> Lock this file (`lock.py acquire .harness/plan.md --holder <you>`) before rewriting it.\n\n"
        "## Migration provenance\n"
        "This harness substrate was seeded by `migracion_proyecto.py` from\n"
        "`{source}` (generation {gen}) on {now}. No task history was carried over --\n"
        "the blackboard starts empty (see the migration announcement in blackboard.json).\n\n"
        "Work already in this repo does NOT get migrated as tasks -- it gets\n"
        "RE-DESCRIBED as a goal. Tell the planner what is pending; it decomposes it\n"
        "into a dependency-DAG on the blackboard, exactly like a fresh project.\n\n"
        "## Generation 0 -- TBD\n"
        "(Planner: fill in the dependency-DAG for this project's first milestone.)\n"
    ).format(source=source_root, gen=source_gen, now=now)


def _task_json_template(now):
    return {
        "_comment": "Mirror of the CURRENT task for single-runner sessions (claude.md §4 tree). "
                    "Multi-agent sessions should rely on the blackboard instead; a solo runner "
                    "may copy its claimed task payload here for quick reference.",
        "active_task": None,
        "claimed_via": "python3 .harness/bin/blackboard.py claim <T-ID> --agent <you>",
        "updated_at": now,
    }


# --------------------------------------------------------------------------
# step 1: copy machinery
# --------------------------------------------------------------------------

def _copy_guarded_file(src, dst, note, dry, force):
    """Copy a single file, never silently clobbering a pre-existing target file.

    Without --force: if dst already exists, [SKIP-EXISTS] and leave it
    byte-for-byte intact. With --force: [BACKUP] the existing dst by RENAME
    to <name>.bak-<n> (first free n, never deleted), then [COPY] the new
    file in. If dst does not exist yet, plain [COPY].
    """
    if dst.exists():
        if not force:
            note("SKIP-EXISTS", "{} already exists -- left intact (target-owned; diff "
                                 "manually against {} if you want to reconcile)".format(dst, src))
            return
        backup = _next_backup_path(dst)
        note("BACKUP", "{} -> {} (rename, no delete)".format(dst, backup))
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.rename(backup)
    note("COPY", "{} -> {}".format(src, dst))
    if not dry:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _copy_guarded_dir(src, dst_root, note, dry, force):
    """Copy a directory tree file-by-file, guarding each colliding filename
    individually (non-colliding files in the same tree are always copied)."""
    if not src.exists():
        note("SKIP", "source {} not found -- nothing to copy".format(src))
        return
    for src_file in sorted(src.rglob("*")):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(src)
        _copy_guarded_file(src_file, dst_root / rel, note, dry, force)


def _copy_machinery(target, note, dry, force):
    # These two live entirely under .harness/, which is guarded as a whole
    # (refuse-unless-force + whole-dir backup-by-rename) before this function
    # ever runs -- by the time we get here the destination .harness/ is
    # always freshly empty, so a bulk copytree/copy2 here can never clobber
    # target-owned content. Left exactly as before (T-032 behavior).
    bulk_items = [
        (SRC_HARNESS_BIN, target / ".harness" / "bin", "dir"),
        (SRC_HARNESS_README, target / ".harness" / "README.md", "file"),
    ]
    for src, dst, kind in bulk_items:
        if not src.exists():
            note("SKIP", "source {} not found -- nothing to copy".format(src))
            continue
        note("COPY", "{} -> {}".format(src, dst))
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if kind == "dir":
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    # These live outside .harness/ -- the target may already own a version
    # of any of them (its own hooks/permissions, its own docs, its own
    # agents/skill). Guard each one individually: never silently overwrite.
    guarded_files = [
        (SRC_CLAUDE_SETTINGS, target / ".claude" / "settings.json"),
        (SRC_ORCHESTRATION, target / "ORCHESTRATION.md"),
        (SRC_USAGE, target / "USAGE.md"),
    ]
    for src, dst in guarded_files:
        if not src.exists():
            note("SKIP", "source {} not found -- nothing to copy".format(src))
            continue
        _copy_guarded_file(src, dst, note, dry, force)

    guarded_dirs = [
        (SRC_CLAUDE_AGENTS, target / ".claude" / "agents"),
        (SRC_CLAUDE_SKILL, target / ".claude" / "skills" / "harness-status"),
    ]
    for src, dst in guarded_dirs:
        _copy_guarded_dir(src, dst, note, dry, force)


# --------------------------------------------------------------------------
# step 2: reset state
# --------------------------------------------------------------------------

def _reset_state(target, note, dry, source_state, source_bb, now):
    dst_harness = target / ".harness"
    source_gen = source_state.get("harness_generation", source_bb.get("generation", 0))

    bb = {
        "schema_version": source_bb.get("schema_version", "0.1.0"),
        "generation": source_gen,
        "updated_at": now,
        "updated_by": "migracion_proyecto.py",
        "protocol": copy.deepcopy(source_bb.get("protocol", {})),
        "announcements": [
            {
                "ts": now,
                "from": "migracion_proyecto.py",
                "message": "Migrated from {} (generation {}) on {}. Seeded by "
                           "migracion_proyecto.py.".format(SRC_ROOT, source_gen, now),
            }
        ],
        "epics": {},
        "tasks": {},
    }
    note("RESET", "{}/blackboard.json -> fresh board (generation {}, empty tasks{{}}, "
                  "1 migration announcement)".format(dst_harness, source_gen))
    if not dry:
        hc.atomic_write_json(dst_harness / "blackboard.json", bb)

    registry = copy.deepcopy(source_state.get("agents", {}).get("registry", {}))
    limits = copy.deepcopy(source_state.get("limits", {}))
    human_gates = copy.deepcopy(source_state.get("human_gates", {}))
    state = {
        "schema_version": source_state.get("schema_version", "0.1.0"),
        "harness_generation": source_gen,
        "created_at": now,
        "created_by": "migracion_proyecto.py (migrated from {})".format(SRC_ROOT),
        "run": {"run_counter": 0, "last_run_id": None, "last_session_start": None},
        "limits": limits,
        "human_gates": human_gates,
        "agents": {
            "_comment": source_state.get("agents", {}).get("_comment", ""),
            "registry": registry,
            "reputation": {},
        },
        "evolution": {
            "generation": source_gen,
            "last_audit_at": None,
            "pending_proposals": [],
            "accepted_mutations": [],
            "audit_artifacts": [],
            "notes": "Migrated from {} (generation {}) on {} by migracion_proyecto.py. "
                     "Evolution history prior to this point lives in the source repo's git "
                     "log / state.json; this board starts a fresh evolution loop.".format(
                         SRC_ROOT, source_gen, now),
            "next_audit_inputs": [],
        },
    }
    note("RESET", "{}/state.json -> schema/limits/human_gates/agents.registry kept verbatim, "
                  "reputation zeroed, run counters nulled, generation {} preserved with a "
                  "provenance note".format(dst_harness, source_gen))
    if not dry:
        hc.atomic_write_json(dst_harness / "state.json", state)

    for d in ("locks", "tasks"):
        note("RESET", "{}/{}/ -> empty directory".format(dst_harness, d))
        if not dry:
            (dst_harness / d).mkdir(parents=True, exist_ok=True)

    for f in ("events.jsonl", "transcript.jsonl"):
        note("RESET", "{}/logs/{} -> empty file".format(dst_harness, f))
        if not dry:
            (dst_harness / "logs").mkdir(parents=True, exist_ok=True)
            (dst_harness / "logs" / f).write_text("", encoding="utf-8")

    note("SKIP", "{}/session_holders.json -> NOT created (no session holders registered "
                 "yet in the target)".format(dst_harness))

    note("RESET", "{}/plan.md -> template with migration provenance note".format(dst_harness))
    if not dry:
        (dst_harness / "plan.md").write_text(
            _plan_template(SRC_ROOT, source_gen, now), encoding="utf-8")

    note("RESET", "{}/task.json -> template (active_task=null)".format(dst_harness))
    if not dry:
        hc.atomic_write_json(dst_harness / "task.json", _task_json_template(now))


# --------------------------------------------------------------------------
# step 3: integrate
# --------------------------------------------------------------------------

def _integrate(target, note, dry):
    dst_claude = target / "CLAUDE.md"
    src_text = SRC_CLAUDE_MD.read_text(encoding="utf-8") if SRC_CLAUDE_MD.exists() else None
    if src_text is None:
        note("SKIP", "source CLAUDE.md not found -- nothing to integrate")
    elif dst_claude.exists():
        existing = dst_claude.read_text(encoding="utf-8")
        if BEGIN_MARKER in existing and END_MARKER in existing:
            note("SKIP", "{} already has UNIVERSAL-HARNESS markers -- left untouched "
                         "(never overwrite)".format(dst_claude))
        else:
            note("MERGE", "append source CLAUDE.md to {} between {} / {} markers "
                          "(existing content untouched)".format(dst_claude, BEGIN_MARKER, END_MARKER))
            if not dry:
                block = "\n\n{}\n{}\n{}\n".format(BEGIN_MARKER, src_text.rstrip("\n"), END_MARKER)
                with open(dst_claude, "a", encoding="utf-8") as f:
                    f.write(block)
    else:
        note("COPY", "{} -> {} (new file, wrapped in UNIVERSAL-HARNESS markers)".format(
            SRC_CLAUDE_MD, dst_claude))
        if not dry:
            block = "{}\n{}\n{}\n".format(BEGIN_MARKER, src_text.rstrip("\n"), END_MARKER)
            dst_claude.write_text(block, encoding="utf-8")

    if not _is_git_repo(target):
        note("SKIP", "{} is not a git repo -- .gitignore left untouched".format(target))
        return
    gi = target / ".gitignore"
    existing_lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    to_add = [e for e in GITIGNORE_ENTRIES if e not in existing_lines]
    if not to_add:
        note("SKIP", "{} already has all harness ignore entries".format(gi))
    else:
        note("APPEND", "{} += {} line(s): {}".format(gi, len(to_add), ", ".join(to_add)))
        if not dry:
            with open(gi, "a", encoding="utf-8") as f:
                if existing_lines:
                    f.write("\n")
                f.write("\n".join(to_add) + "\n")


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def _render_report(target, dry, report):
    lines = ["=== migracion_proyecto.py: {} for {} ===".format(
        "ACTION PLAN (dry-run -- nothing written)" if dry else "MIGRATION REPORT", target)]
    lines.append("source: {}".format(SRC_ROOT))
    for tag, text in report:
        lines.append("  [{:<11}] {}".format(tag, text))
    return "\n".join(lines)


def _next_steps_text(target):
    return (
        "\nNext steps for the human (siguientes pasos):\n"
        "  1. cd {t}\n"
        "  2. Open Claude Code IN {t} -- hooks only load when the session root is this dir.\n"
        "  3. Read ORCHESTRATION.md and USAGE.md.\n"
        "  4. Pose the goal, e.g.:\n"
        "     \"Lee ORCHESTRATION.md y USAGE.md. El proyecto esta a medias: [contexto].\n"
        "      Planner: descompon lo pendiente en el tablero y despacha.\"\n"
    ).format(t=target)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args(argv):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target_dir", help="destination project directory (must already exist)")
    parser.add_argument("--dry-run", action="store_true",
                         help="print the full action plan; write NOTHING")
    parser.add_argument("--force", action="store_true",
                         help="if <target-dir>/.harness already exists, back it up "
                              "(rename to .harness.bak-<n>, never delete) and migrate again")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    target = Path(args.target_dir).expanduser().resolve()
    dry = args.dry_run

    if not target.exists():
        print("refused: target directory does not exist: {}".format(target), file=sys.stderr)
        return 1
    if not target.is_dir():
        print("refused: {} is not a directory".format(target), file=sys.stderr)
        return 1

    dst_harness = target / ".harness"
    backup_dst = None
    if dst_harness.exists():
        if not args.force:
            print("refused: {} already exists. Re-run with --force to back it up "
                  "(renamed to .harness.bak-<n>, nothing is deleted) and migrate "
                  "again.".format(dst_harness), file=sys.stderr)
            return 1
        backup_dst = _next_backup_path(dst_harness)

    report = []

    def note(tag, text):
        report.append((tag, text))

    if backup_dst is not None:
        note("BACKUP", "{} -> {} (rename, no delete)".format(dst_harness, backup_dst))
        if not dry:
            dst_harness.rename(backup_dst)

    _copy_machinery(target, note, dry, args.force)

    now = hc.now_iso()
    source_state = hc.read_json(SRC_STATE, default={}) or {}
    source_bb = hc.read_json(SRC_BLACKBOARD, default={}) or {}
    _reset_state(target, note, dry, source_state, source_bb, now)

    _integrate(target, note, dry)

    print(_render_report(target, dry, report))
    if dry:
        print("\nDRY-RUN: no files were written. Re-run without --dry-run to perform "
              "the migration.")
    else:
        print(_next_steps_text(target))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
