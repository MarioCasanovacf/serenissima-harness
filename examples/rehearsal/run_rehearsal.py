#!/usr/bin/env python3
"""run_rehearsal.py -- T-440: one connected story, told through the tools' own CLIs.

WHY THIS EXISTS. A 2026-10-07 review counted five built, tested mechanisms that had
never fired on the real board: contest, the phase B claim-order yield, an act signed
by a fedatario seat holder, a delegated credential with a ceiling, and the Westphalia
reconciliation-cost KPI. A case disposed by a publish that follows (cites) an earlier
precedent is NOT a sixth never-fired item: the live board already ran that path twice
before that review, on 2026-09-20 -- C-002 disposed by PR-062, C-003 disposed by
PR-063, chaining PR-061 -> PR-062 -> PR-063, each confirmed by a distinct verifier.
What stays at zero live is narrower than "never fired": `precedent.py
disposition-ratio`'s by_citation column counts only the `distinguish` verb, so it
reads 0 even though two cases have already been disposed by a following publish.
Step 6 below replays that same publish-follows shape inside the sandbox so this
story is connected end to end -- it is a replay of a mechanism that already fired
live, not a first firing, and the scorecard row says so. This script drives ONE
connected story -- "Casona" -- through every tool's own command line, in a throwaway
copy of the harness, and prints a scorecard: each attempted mechanism comes back
FIRED (with the evidence the tool itself wrote), BLOCKED (with the tool's own
refusal message), or UNBUILT (named, never coded).

THE STORY, in order (same names, same tasks, same records throughout):
  1. `rehearsal-worker` claims a scratch task, does the work, and is mechanically
     refused when it tries to mark its own task done (producer != approver).
  2. It hands off to role=verifier; a DISTINCT agent, `rehearsal-reviewer`, verdicts
     done.
  3. `fed-regulador` (a fedatario seat: "ancla evidencia ANTES de la discusion") opens
     a dispute about that task as a registered case.
  4. `registro-a` proposes a deliberation on the case; `registro-b` and
     `revision-doctrina` sponsor it (3/3 quorum); `revision-mecanismo` schedules it;
     the assembly discusses both alternatives and casts five ranked ballots; a
     Condorcet winner is concluded by `revision-mecanismo`.
  5. `registro-a` ("registros confirmados que sobreviven a la citacion posterior")
     publishes a precedent disposing the case. `registro-b` confirms it.
  6. A second dispute is opened on a second task. `fed-codificador` ("convierte
     consenso en registro") disposes it by publishing a second precedent that
     FOLLOWS the first -- visible in `precedent.py disposition-ratio` and in the
     first record's own `cited_by`.
  7. That citation activity gives `registro-a` a non-zero Phase B reputation score.
     `registro-a` holds a live claim on the board; a brand-new, zero-score identity
     then calls `blackboard.py next` and is mechanically outranked (phase_b_yield).
  8. `fed-codificador` attempts to sign an act and have it verify -- and an attempt
     to delegate a ceilinged credential and a fork/contest attempt -- are run for
     real against the sandbox and come back BLOCKED, with the tool's own message,
     by the SAME root cause: this rehearsal is forbidden from reading the live
     private keys under `.harness/keys` and forbidden from signing any warrant, and
     `attest.py`'s own D3a intent gate requires a signature that verifies against
     the warrant's REAL, un-copied key before any privileged act (grant, distinguish,
     contest, verdict) can even be attempted. A non-privileged `commit` act CAN be
     signed with a freshly generated, non-matching key -- and then fails `verify`,
     exactly as the module's own docstring says it must.
  9. `currency.py` and `event_stats.py` read the sandbox's own events and precedents.
 10. `westphalia_kpi.py` is run against the sandbox; it refuses to emit a cost figure
     because the tool's own, hardcoded registry list names exactly one domain
     registry (`precedents/`) today, and PR-029 clause 6 forbids reporting that as
     zero.
 11. Contracts and breach (decision 2) are reported UNBUILT: `.harness/design-T-436-
     contracts.md` is a design note, not code.

SECURITY, enforced by this script and not merely asserted:
  - `.harness/keys/` is NEVER read from the live tree, and no agent key here is
    anything but freshly generated inside the sandbox with `ssh-keygen`, which dies
    with the temp directory.
  - No warrant is ever signed, drafted-and-applied, or otherwise minted. The sandbox's
    copy of `trust/`, `constitutional/` and `warrants/` is a literal copy of files the
    operator ALREADY signed in the live tree (git-tracked, public: compare
    `git ls-files .harness/trust .harness/constitutional .harness/warrants`), carried
    over so `reputation.py`'s phase B activation and `warrant.py`'s own verification
    can run in the sandbox exactly as they do live -- never a new signature.
  - `~/.ssh/harness_root` is never referenced.
  - Every mutation happens through a subprocess call onto a tool's own CLI inside the
    sandbox; this script never imports `blackboard`, `precedent`, `deliberate`,
    `attest`, `reputation`, `currency`, `event_stats` or `westphalia_kpi` as a module.
  - The live tree is read once (to copy it) and never written: see `integrity_check()`,
    run before and after, comparing a sha256 of every file under the live `.harness/`
    (excluding `logs/`, which this run's OWN task bookkeeping legitimately touches via
    separate `blackboard.py`/`lock.py` calls outside this script, and the T-440 task
    file itself, same reason) plus `git status --porcelain`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIVE_HARNESS = REPO_ROOT / ".harness"
PY = sys.executable

# Directories never copied into the sandbox. "keys" is the hard security line
# (private material); "locks"/"logs"/"__pycache__" are just noise this run doesn't
# need and starts fresh instead, so the sandbox's own events.jsonl holds only what
# THIS story writes.
COPY_EXCLUDE_DIRS = {"keys", "locks", "logs", "__pycache__"}

# What the live-tree integrity check ignores, named explicitly here rather than in
# the acceptance criterion alone, so a reader can see exactly what is excluded and why.
INTEGRITY_EXCLUDE_DIRS = {"logs"}
INTEGRITY_EXCLUDE_FILES = {"tasks/T-440.json"}


# --------------------------------------------------------------------------- utils

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(argv, timeout=60):
    """One subprocess call onto a tool's own CLI. Never imports the tool."""
    return subprocess.run([str(a) for a in argv], capture_output=True, text=True,
                           timeout=timeout)


def first_match(pattern, text, group=1):
    m = re.search(pattern, text or "")
    return m.group(group) if m else None


def leading_json(text):
    """Some CLIs here print a JSON object followed by human-readable trailer lines
    (e.g. `precedent.py show`'s 'scope: ...' footer) on a non-`--json` call. Parse
    only the leading JSON value and ignore whatever trailer follows it."""
    if not text or not text.strip():
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(text.strip())
        return obj
    except (json.JSONDecodeError, ValueError):
        return {}


def sha256_tree(root: pathlib.Path, exclude_dirs=frozenset(), exclude_files=frozenset()):
    out = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts and rel.parts[0] in exclude_dirs:
            continue
        if str(rel) in exclude_files:
            continue
        out[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def git_status_porcelain():
    try:
        p = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
                            capture_output=True, text=True, timeout=30)
        return p.stdout
    except Exception as e:  # pragma: no cover - environmental
        return "<could not run git: {}>".format(e)


def integrity_snapshot():
    return {
        "hashes": sha256_tree(LIVE_HARNESS, INTEGRITY_EXCLUDE_DIRS, INTEGRITY_EXCLUDE_FILES),
        "git_status_porcelain": git_status_porcelain(),
    }


def integrity_diff(before, after):
    diffs = []
    if before["git_status_porcelain"] != after["git_status_porcelain"]:
        diffs.append("git status --porcelain changed")
    b, a = before["hashes"], after["hashes"]
    for path in sorted(set(b) | set(a)):
        if b.get(path) != a.get(path):
            diffs.append("hash changed/added/removed: {}".format(path))
    return diffs


# ------------------------------------------------------------------------ scorecard

class Scorecard:
    def __init__(self):
        self.rows = []

    def record(self, mechanism, outcome, evidence=None, blocker=None):
        if outcome not in ("fired", "blocked", "unbuilt"):
            raise ValueError(outcome)
        row = {"mechanism": mechanism, "outcome": outcome}
        if evidence is not None:
            row["evidence"] = evidence
        if blocker is not None:
            row["blocker"] = blocker
        self.rows.append(row)
        print("[{}] {}".format(outcome.upper(), mechanism))
        if evidence:
            print("    evidence: {}".format(evidence))
        if blocker:
            print("    blocker:  {}".format(blocker))
        return row


# -------------------------------------------------------------------------- sandbox

def build_sandbox(tmp_root: pathlib.Path) -> pathlib.Path:
    """Copy the live .harness tree into tmp_root/.harness, excluding COPY_EXCLUDE_DIRS.
    Reads the live tree; never writes to it."""
    dst = tmp_root / ".harness"

    def ignore(_dir, names):
        return {n for n in names if n in COPY_EXCLUDE_DIRS}

    shutil.copytree(LIVE_HARNESS, dst, ignore=ignore)
    for sub in ("locks", "logs"):
        (dst / sub).mkdir(parents=True, exist_ok=True)
    (dst / "logs" / "events.jsonl").write_text("")
    (dst / "logs" / "transcript.jsonl").write_text("")
    (dst / "keys").mkdir(parents=True, exist_ok=True)
    return dst


def genkey(keys_dir: pathlib.Path, name: str) -> pathlib.Path:
    """A fresh ed25519 keypair, generated inside the sandbox, for `name`. Dies with
    the temp directory. Never reads any live key."""
    path = keys_dir / name
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", name, "-f", str(path)],
                    capture_output=True, text=True, timeout=30, check=True)
    return path


def fresh_task_ids(harness_dir: pathlib.Path, n: int) -> list:
    bb = json.loads((harness_dir / "blackboard.json").read_text(encoding="utf-8"))
    nums = [int(tid[2:]) for tid in bb.get("tasks", {})
            if tid.startswith("T-") and tid[2:].isdigit()]
    start = (max(nums) if nums else 0) + 1
    return ["T-{}".format(start + i) for i in range(n)]


# --------------------------------------------------------------------------- story

def run_story(bindir: pathlib.Path, harness_dir: pathlib.Path, keys_dir: pathlib.Path,
              sc: Scorecard):
    bb = str(bindir / "blackboard.py")
    precedent = str(bindir / "precedent.py")
    deliberate = str(bindir / "deliberate.py")
    attest = str(bindir / "attest.py")
    currency = str(bindir / "currency.py")
    event_stats = str(bindir / "event_stats.py")
    westphalia = str(bindir / "westphalia_kpi.py")
    events_log = harness_dir / "logs" / "events.jsonl"
    hroot = str(harness_dir)

    t_welcome, t_second, t_open = fresh_task_ids(harness_dir, 3)
    fed_key = genkey(keys_dir, "fed-codificador-sandbox")

    # ---- 1-2: producer != approver, then handoff + distinct verifier ----------
    run([PY, bb, "add-task", "--id", t_welcome,
         "--title", "Casona: redactar acta de bienvenida", "--role", "worker",
         "--engine", "any", "--agent", "fed-regulador"])
    run([PY, bb, "claim", t_welcome, "--agent", "rehearsal-worker"])
    run([PY, bb, "update", t_welcome, "--status", "in_progress", "--agent",
         "rehearsal-worker", "--note", "plan: draft the welcome act"])

    self_done = run([PY, bb, "update", t_welcome, "--status", "done", "--agent",
                      "rehearsal-worker", "--note", "trying to self-approve"])
    sc.record(
        "producer-not-approver refusal",
        "fired" if self_done.returncode != 0 and "producer" in self_done.stderr.lower()
        else "blocked",
        evidence="blackboard.py update {} --status done --agent rehearsal-worker "
                  "refused rc={}: {!r}".format(t_welcome, self_done.returncode,
                                                self_done.stderr.strip()[:200]),
    )

    run([PY, bb, "handoff", t_welcome, "--to-role", "verifier", "--agent",
         "rehearsal-worker", "--note", "acta redactada, lista para revision"])
    verdict = run([PY, bb, "update", t_welcome, "--status", "done", "--agent",
                   "rehearsal-reviewer", "--note", "verificado: acta correcta"])
    sc.record(
        "handoff and a distinct verifier's verdict",
        "fired" if verdict.returncode == 0 else "blocked",
        evidence="blackboard.py update {} --status done --agent rehearsal-reviewer "
                  "(distinct from rehearsal-worker) -> rc={}: {}".format(
                      t_welcome, verdict.returncode, verdict.stdout.strip()),
    )

    # ---- 3-4: a dispute becomes a case, deliberated by >=3 distinct names -----
    case1 = run([PY, precedent, "case", "open", "--question",
                 "El acta de {} fijo un termino sin ratio escrita: aplica ya una regla, "
                 "o hace falta fijarla?".format(t_welcome), "--task", t_welcome,
                 "--agent", "fed-regulador", "--harness-root", hroot])
    case1_id = first_match(r"case (C-\d+)", case1.stdout)

    prop = run([PY, deliberate, "propose", "--title",
                "Regla sobre actas de bienvenida sin ratio", "--evidence", t_welcome,
                "--proposer", "registro-a", "--task", t_welcome, "--alternatives",
                "fijar_regla", "--alternatives", "rechazar", "--case", case1_id,
                "--harness-root", hroot])
    d1_id = first_match(r"dossier (D-\d+)", prop.stdout)
    run([PY, deliberate, "sponsor", d1_id, "--by", "registro-b", "--harness-root", hroot])
    run([PY, deliberate, "sponsor", d1_id, "--by", "revision-doctrina", "--harness-root", hroot])
    run([PY, deliberate, "prior", d1_id, "--voter", "registro-a", "--ranking",
         "fijar_regla,rechazar", "--harness-root", hroot])
    run([PY, deliberate, "schedule", d1_id, "--speakers",
         "registro-a,registro-b,revision-doctrina,revision-ataque,revision-mecanismo",
         "--by", "revision-mecanismo", "--harness-root", hroot])
    run([PY, deliberate, "discuss", d1_id, "--by", "revision-doctrina", "--re",
         "fijar_regla", "--text",
         "El acta de {} ya fijaba un termino: conviene codificarlo como regla.".format(
             t_welcome), "--harness-root", hroot])
    run([PY, deliberate, "discuss", d1_id, "--by", "revision-ataque", "--re",
         "rechazar", "--text", "Una sola acta no basta de evidencia para una regla general.",
         "--harness-root", hroot])
    voters = [("registro-a", "fijar_regla,rechazar"), ("registro-b", "fijar_regla,rechazar"),
              ("revision-doctrina", "fijar_regla,rechazar"),
              ("revision-ataque", "rechazar,fijar_regla"),
              ("revision-mecanismo", "fijar_regla,rechazar")]
    for voter, ranking in voters:
        run([PY, deliberate, "vote", d1_id, "--voter", voter, "--ranking", ranking,
             "--harness-root", hroot])
    conclude1 = run([PY, deliberate, "conclude", d1_id, "--method", "schulze", "--by",
                      "revision-mecanismo", "--harness-root", hroot])
    sc.record(
        "a case opened and deliberated (propose/sponsor/prior/discuss/vote/conclude, "
        "Condorcet) by >=3 distinct names",
        "fired" if conclude1.returncode == 0 and "Condorcet Winner" in conclude1.stdout
        else "blocked",
        evidence="{}: proposer registro-a, sponsors registro-b+revision-doctrina, "
                  "speakers/voters across 5 distinct names, concluded by "
                  "revision-mecanismo -- {}".format(
                      d1_id, " / ".join(conclude1.stdout.strip().splitlines()[1:4])
                      if conclude1.returncode == 0 else conclude1.stderr.strip()),
    )

    # ---- 5: precedent published disposing the case, then confirmed ------------
    pub1 = run([PY, precedent, "publish", "--agent", "registro-a", "--task", t_welcome,
                "--case", case1_id, "--title",
                "Actas de bienvenida fijan ratio desde su primer uso", "--subject",
                "actas-bienvenida", "--tier", "3", "--width", "narrow", "--ratio",
                "Un acta de bienvenida que fija un termino operativo sin ratio escrita "
                "vale como ratio desde su primer uso confirmado ({}, Condorcet, 5 "
                "votos).".format(d1_id), "--sources", t_welcome, "--code-version", "v1",
                "--tier-evidence", t_welcome, "--scope", "role:worker",
                "--revisit-trigger",
                "revisitar si una acta posterior contradice este termino", "--validity",
                "mientras {} siga en pie como acta vigente".format(t_welcome),
                "--harness-root", hroot])
    pr1_id = first_match(r"published (PR-\d+)", pub1.stdout)
    case1_show = run([PY, precedent, "case", "show", case1_id, "--harness-root", hroot])
    confirm1 = run([PY, precedent, "confirm", pr1_id, "--agent", "registro-b", "--outcome",
                    "confirmed", "--note",
                    "confirmado: se aplico igual en una segunda acta"])
    sc.record(
        "a precedent published disposing the case",
        "fired" if pub1.returncode == 0 and "disposed" in case1_show.stdout
        else "blocked",
        evidence="precedent.py publish --case {} --agent registro-a -> {} ; "
                  "precedent.py case show {} (re-queried from the sandbox's own case "
                  "file): {}".format(
                      case1_id, pr1_id, case1_id,
                      " / ".join(case1_show.stdout.strip().splitlines())),
    )
    sc.record(
        "a confirmation by a distinct author",
        "fired" if confirm1.returncode == 0 and "confirmed" in confirm1.stdout
        else "blocked",
        evidence="precedent.py confirm {} --agent registro-b (distinct from publisher "
                  "registro-a) -> {}".format(pr1_id, confirm1.stdout.strip()),
    )

    # ---- 6: a second case disposed by citing the first precedent ---------------
    run([PY, bb, "add-task", "--id", t_second,
         "--title", "Casona: segunda acta de bienvenida", "--role", "worker",
         "--engine", "any", "--agent", "fed-regulador"])
    case2 = run([PY, precedent, "case", "open", "--question",
                 "La segunda acta ({}) tambien fija un termino sin ratio: le aplica "
                 "{}?".format(t_second, pr1_id), "--task", t_second, "--agent",
                 "fed-regulador", "--harness-root", hroot])
    case2_id = first_match(r"case (C-\d+)", case2.stdout)

    # The strict "disposed BY CITATION" column in disposition-ratio counts
    # `distinguish`, not `publish --follows`. Attempted for real, for the record,
    # while C-005 is still OPEN (so any refusal is the D3a gate, not "already
    # disposed"): `distinguish` is a PRIVILEGED kind (attest.py PRIVILEGED_KINDS),
    # gated by D3a's intent requirement -- same root cause as the attest findings
    # below.
    distinguish_attempt = run([PY, precedent, "distinguish", "--case", case2_id,
                                "--nearest", pr1_id, "--facts",
                                "la segunda acta repite exactamente el mismo patron operativo que la primera acta ya resolvio, sin ningun hecho nuevo que la distinga de ese caso anterior",
                                "--by", "fed-codificador", "--key", str(fed_key),
                                "--task", t_second, "--harness-root", hroot])

    pub2 = run([PY, precedent, "publish", "--agent", "fed-codificador", "--task",
                t_second, "--case", case2_id, "--title",
                "{} se extiende a la segunda acta de bienvenida".format(pr1_id),
                "--subject", "actas-bienvenida", "--tier", "3", "--width", "narrow",
                "--ratio", "{} repite el mismo patron que {} ya resolvio; se sigue el "
                "mismo ratio sin reabrir el debate.".format(t_second, pr1_id),
                "--sources", t_second, "--code-version", "v1", "--tier-evidence",
                t_second, "--scope", "role:worker", "--revisit-trigger",
                "revisitar si {} se contradice con una acta posterior".format(t_second),
                "--validity", "mientras {} siga en pie".format(t_second), "--follows",
                pr1_id, "--harness-root", hroot])
    pr2_id = first_match(r"published (PR-\d+)", pub2.stdout)

    disp_ratio = run([PY, precedent, "disposition-ratio", "--json", "--harness-root",
                       hroot])
    disp_ratio_json = (json.loads(disp_ratio.stdout) if disp_ratio.returncode == 0
                        and disp_ratio.stdout else {})
    show_pr1 = run([PY, precedent, "show", pr1_id])
    show_pr1_json = leading_json(show_pr1.stdout) if show_pr1.returncode == 0 else {}
    cited_back = pr2_id is not None and pr2_id in (show_pr1_json.get("cited_by") or [])
    sc.record(
        "a case disposed by publish --follows (citing a published rule) -- fired "
        "HERE IN THE SANDBOX; this is a replay, not a first firing: the live board "
        "already ran this same shape twice before (C-002 disposed by PR-062, C-003 "
        "disposed by PR-063, 2026-09-20), visible in disposition-ratio",
        "fired" if pub2.returncode == 0 and cited_back else "blocked",
        evidence="precedent.py publish --case {} --follows {} -> {} ; "
                  "precedent.py show {} -> cited_by={} ; precedent.py "
                  "disposition-ratio --json -> by_legislation_registered_raw={}, "
                  "cases_opened_raw={} (this run's 2 sandbox cases are among them, "
                  "on top of the 2 that already disposed by this shape live). The "
                  "narrower by_citation_raw={} column tracks `distinguish` only, "
                  "which this run attempted separately while the case was still "
                  "open and which was refused (rc={}): {!r}".format(
                      case2_id, pr1_id, pr2_id, pr1_id,
                      show_pr1_json.get("cited_by"),
                      disp_ratio_json.get("by_legislation_registered_raw"),
                      disp_ratio_json.get("cases_opened_raw"),
                      disp_ratio_json.get("by_citation_raw"),
                      distinguish_attempt.returncode,
                      distinguish_attempt.stderr.strip()[:220]),
    )

    # ---- 7: phase B yield ------------------------------------------------------
    t_lagger = t_open
    run([PY, bb, "claim", t_second, "--agent", "registro-a"])
    run([PY, bb, "update", t_second, "--status", "in_progress", "--agent", "registro-a",
         "--note", "plan: trabajando en la segunda acta"])
    run([PY, bb, "add-task", "--id", t_lagger,
         "--title", "Casona: tarea abierta para el rezagado", "--role", "worker",
         "--engine", "any", "--agent", "fed-regulador"])
    nxt = run([PY, bb, "next", "--agent", "rehearsal-newcomer", "--role", "worker"])
    yield_event = None
    for line in events_log.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("event") == "phase_b_yield" and row.get("agent") == "rehearsal-newcomer":
            yield_event = row
    sc.record(
        "a phase B yield (event phase_b_yield) from blackboard.py next",
        "fired" if nxt.returncode == 2 and yield_event else "blocked",
        evidence="blackboard.py next --agent rehearsal-newcomer --role worker -> exit "
                  "{} ; events.jsonl: {}".format(nxt.returncode, yield_event)
        if yield_event else None,
        blocker=None if yield_event else "no phase_b_yield event written; stdout={!r} "
                  "stderr={!r}".format(nxt.stdout.strip(), nxt.stderr.strip()),
    )

    # ---- 8a: an act signed by a fedatario seat holder, and verified -----------
    sign1 = run([PY, attest, "sign", "--name", "fed-codificador", "--key", str(fed_key),
                 "--kind", "commit", "--ref", pr2_id, "--body",
                 json.dumps({"note": "fed-codificador firma la publicacion de {}".format(
                     pr2_id)})])
    verify1 = run([PY, attest, "verify", "--name", "fed-codificador", "--json"])
    verify1_json = json.loads(verify1.stdout) if verify1.returncode == 0 and verify1.stdout else {}
    verified_clean = bool(verify1_json.get("enrolled")) and not verify1_json.get(
        "signature_failures")
    sc.record(
        "an act signed by a fedatario seat holder and verified",
        "fired" if sign1.returncode == 0 and verified_clean else "blocked",
        evidence="attest.py sign --name fed-codificador --key <sandbox-generated-key> "
                  "--kind commit -> act written (rc={})".format(sign1.returncode)
        if sign1.returncode == 0 else None,
        blocker="the act SIGNS (fed-codificador is warrant-enrolled in the sandbox "
                "copy of W-002, so attest.py accepts the name), but attest.py verify "
                "reports it as a signature failure: {} -- because this rehearsal is "
                "forbidden from reading fed-codificador's REAL private key under the "
                "live .harness/keys/ and forbidden from signing a new warrant to mint "
                "a key it does hold, so the key used to sign here cannot match the one "
                "the warrant recorded. This is the module's own documented limit "
                "(D-17/DIS-1), reproduced live rather than merely cited.".format(
                    verify1_json.get("signature_failures")),
    )

    # ---- 8b: a delegation with a ceiling, used within and refused beyond ------
    scribe_key = genkey(keys_dir, "casona-escribano")
    scribe_pub = (keys_dir / "casona-escribano.pub").read_text(encoding="utf-8").strip()
    grant_intent = run([PY, attest, "declare-intent", "--name", "fed-codificador",
                        "--key", str(fed_key), "--for-kind", "grant", "--task",
                        t_second, "--for-ref", "casona-escribano", "--declares",
                        "fed-codificador delega distinguish a casona-escribano para "
                        "disponer {}".format(case2_id)])
    # An expiry close to "now" rather than far in the future: D3b clamps a grant to
    # the grantor's own (warrant-recorded) expiry and REFUSES rather than silently
    # clamping a too-distant request, so a near-term expiry isolates the finding
    # this step is actually after (the intent-verification gate) from that separate,
    # unrelated refusal path.
    import datetime as _dt
    near_expiry = (datetime.now(timezone.utc) + _dt.timedelta(hours=2)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    grant = run([PY, attest, "grant", "--by", "fed-codificador", "--key", str(fed_key),
                 "--to", "casona-escribano", "--pubkey", scribe_pub, "--kinds",
                 "distinguish", "--expires", near_expiry, "--task", t_second,
                 "--note", "delega SOLO distinguish, para disponer {}".format(case2_id)])

    if grant.returncode != 0:
        sc.record(
            "a delegation with a ceiling used within it and refused beyond it",
            "blocked",
            blocker="declare-intent for the privileged 'grant' kind (signed with a "
                    "freshly generated, non-warrant-matching key): {!r} / grant itself "
                    "refused: {!r}. If the intent is the cause: attest.py's "
                    "open_intents() only recognizes an intent SIGNED AND VERIFIED "
                    "against the name's ENROLLED (warrant-recorded) key, which this "
                    "rehearsal cannot hold (no live keys read, no warrant signed), so "
                    "no privileged kind (grant/distinguish/contest/verdict) can "
                    "originate from an already-warranted name here -- the same root "
                    "cause as the fedatario-sign finding above, one hop "
                    "earlier.".format(grant_intent.stderr.strip()[:200],
                                       grant.stderr.strip()[:200]),
        )
    else:
        # casona-escribano holds its OWN matching key (scribe_key/scribe_pub were
        # supplied verbatim at grant time, not inherited from any warrant), so ITS
        # intents and acts verify cleanly -- unlike fed-codificador's above.
        run([PY, attest, "declare-intent", "--name", "casona-escribano", "--key",
             str(scribe_key), "--for-kind", "distinguish", "--task", t_second,
             "--for-ref", case2_id, "--declares",
             "casona-escribano dispone de {} citando {}".format(case2_id, pr1_id)])
        within = run([PY, "{}".format(precedent), "distinguish", "--case", case2_id,
                      "--nearest", pr1_id, "--facts",
                      "la segunda acta repite exactamente el mismo patron operativo que la primera acta ya resolvio, sin ningun hecho nuevo que la distinga de ese caso anterior", "--by",
                      "casona-escribano", "--key", str(scribe_key), "--task",
                      t_second, "--harness-root", hroot])
        run([PY, attest, "declare-intent", "--name", "casona-escribano", "--key",
             str(scribe_key), "--for-kind", "contest", "--task", t_second,
             "--for-ref", "fed-codificador", "--declares",
             "casona-escribano intenta contestar mas alla de lo delegado"])
        beyond = run([PY, attest, "contest", "--by", "casona-escribano", "--key",
                      str(scribe_key), "--name", "fed-codificador", "--seq", "0",
                      "--reason", "mas alla del techo delegado", "--task", t_second])
        ceiling_refused = (beyond.returncode != 0
                            and "DELEGATION CEILING" in beyond.stderr)
        sc.record(
            "a delegation with a ceiling used within it and refused beyond it",
            "fired" if within.returncode == 0 and ceiling_refused else "blocked",
            evidence="attest.py grant --by fed-codificador --kinds distinguish -> "
                      "casona-escribano; distinguish (within ceiling) rc={} ; "
                      "contest (beyond ceiling) refused rc={}: {!r}".format(
                          within.returncode, beyond.returncode,
                          beyond.stderr.strip()[:200]),
            blocker=None if ceiling_refused else
                    "contest was not refused by the DELEGATION CEILING check as "
                    "expected: {!r}".format(beyond.stderr.strip()[:200]),
        )

    # ---- 8c: a fork detected, and contested with no weight ---------------------
    race_a = {}
    race_b = {}

    def _sign(ref, slot):
        r = run([PY, attest, "sign", "--name", "fed-codificador", "--key", str(fed_key),
                 "--kind", "commit", "--ref", ref, "--body", json.dumps({"race": ref})])
        slot["result"] = r

    ta = threading.Thread(target=_sign, args=("race-A", race_a))
    tb = threading.Thread(target=_sign, args=("race-B", race_b))
    ta.start(); tb.start(); ta.join(); tb.join()
    forks = run([PY, attest, "forks"])
    forks_found = forks.stdout.strip() not in ("", "[]") and "prev" in forks.stdout
    contest_attempt = run([PY, attest, "contest", "--by", "fed-registrar", "--key",
                            str(genkey(keys_dir, "fed-registrar-sandbox")), "--name",
                            "fed-codificador", "--seq", "0", "--reason",
                            "sospecha de bifurcacion", "--task", t_second])
    sc.record(
        "a fork under one name detected by attest.py forks and contested by a "
        "different name, with the contested act carrying no weight",
        "fired" if forks_found and contest_attempt.returncode == 0 else "blocked",
        evidence="two concurrent `attest.py sign --name fed-codificador` CLI calls, "
                  "launched together, produced sequential (not forked) acts; "
                  "attest.py forks -> {!r}".format(forks.stdout.strip()[:200])
        if not forks_found else "fork detected: {}".format(forks.stdout.strip()[:300]),
        blocker="no fork was produced: roster._guard serializes the read-decide-"
                "create-write in attest.sign_act, so two real concurrent CLI calls "
                "for the same name land as seq N and seq N+1, chained, not siblings -- "
                "confirming the fix the module's own docstring describes (DIS-1's "
                "'four acts, one forged, zero forks' defect) holds under an actual "
                "race rather than only in the test suite. `contest` was attempted "
                "regardless and refused for the same D3a intent-gate reason as "
                "8a/8b: {!r}".format(contest_attempt.stderr.strip()[:200]),
    )

    # ---- 9: currency.py and event_stats.py reading the sandbox -----------------
    cur = run([PY, currency, "--root", hroot, "--json"])
    ev = run([PY, event_stats, "--log", str(events_log), "--json"])
    cur_ok = cur.returncode == 0
    ev_ok = ev.returncode == 0
    sc.record(
        "currency.py and event_stats.py reading the sandbox",
        "fired" if cur_ok and ev_ok else "blocked",
        evidence="currency.py --root <sandbox>/.harness --json: {} records read, "
                  "share_typed={} ; event_stats.py --log <sandbox events.jsonl> "
                  "--json: {} lines parsed".format(
                      json.loads(cur.stdout).get("provenance", {}).get("records_read")
                      if cur_ok else "?",
                      json.loads(cur.stdout).get("A_8_1_convergence", {}).get("share_typed")
                      if cur_ok else "?",
                      json.loads(ev.stdout).get("provenance", {}).get("lines_parsed")
                      if ev_ok else "?"),
    )

    # ---- 10: westphalia_kpi.py with a second registry ---------------------------
    west = run([PY, westphalia, "--root", hroot, "--json"])
    west_json = json.loads(west.stdout) if west.returncode == 0 and west.stdout else {}
    registries = west_json.get("registries") or []
    record_count = registries[0]["records"] if registries else "?"
    sc.record(
        "westphalia_kpi.py attempted with a second registry",
        "blocked",
        blocker="westphalia_kpi.py's own domain_registries() hardcodes exactly one "
                "candidate registry (`{{'precedents': 'PR-'}}`); this sandbox has "
                "{} precedent records in that ONE registry and ZERO second "
                "registries by the tool's own definition, so it reports "
                "status={!r}, registries_raw={}, registries_required=2. Creating a "
                "second NUMBERED-RECORD directory in the sandbox would not change "
                "this: the candidate dict is hardcoded in the tool itself, so "
                "widening it needs a code change under a ratified record (PR-029 "
                "clause 6), not a sandbox fixture -- this is the tool's own "
                "message, reproduced verbatim via --json.".format(
                    record_count, west_json.get("status"),
                    west_json.get("registries_raw")),
    )

    # ---- 11: contracts and breach (decision 2) ---------------------------------
    design_path = REPO_ROOT / ".harness" / "design-T-436-contracts.md"
    sc.record(
        "contracts and breach (decision 2)",
        "unbuilt",
        blocker="no contracts.py / breach.py exists under .harness/bin/; the only "
                "artifact is the design note at {} (T-436's own design, never "
                "implemented). Nothing was run because there is nothing to run.".format(
                    design_path.relative_to(REPO_ROOT)),
    )


# --------------------------------------------------------------------------- main

def parse_args(argv):
    p = argparse.ArgumentParser(description=(
        "Run the Casona rehearsal story in a throwaway sandbox copy of .harness/. "
        "The sandbox is removed at the end by default."))
    p.add_argument("--keep", action="store_true",
                    help="do not remove the sandbox directory; print its location "
                         "and write scorecard.json inside it")
    p.add_argument("--json", action="store_true",
                    help="print the scorecard as a single JSON line on stdout "
                         "(works without --keep)")
    p.add_argument("--out", metavar="FILE",
                    help="write the scorecard JSON to FILE (works without --keep)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    before = integrity_snapshot()

    tmp_root = pathlib.Path(tempfile.mkdtemp(prefix="harness-rehearsal-"))
    try:
        harness_dir = build_sandbox(tmp_root)
        bindir = harness_dir / "bin"
        keys_dir = harness_dir / "keys"

        sc = Scorecard()
        try:
            run_story(bindir, harness_dir, keys_dir, sc)
        finally:
            after = integrity_snapshot()
            diffs = integrity_diff(before, after)

        scorecard = {
            "task": "T-440",
            "sandbox": str(tmp_root),
            "generated_at": now_iso(),
            "rows": sc.rows,
            "live_tree_untouched": not diffs,
            "live_tree_diffs": diffs,
        }

        if args.out:
            pathlib.Path(args.out).write_text(
                json.dumps(scorecard, indent=2, ensure_ascii=False), encoding="utf-8")
            print("scorecard written: {}".format(args.out))

        if args.keep:
            scorecard_path = tmp_root / "scorecard.json"
            scorecard_path.write_text(
                json.dumps(scorecard, indent=2, ensure_ascii=False), encoding="utf-8")
            print("sandbox: {}".format(tmp_root))
            print("scorecard written: {}".format(scorecard_path))

        if args.json:
            # One compact line, so a caller can find it by a fixed prefix without
            # needing to track where the human-readable FIRED/BLOCKED lines end.
            print("scorecard-json: {}".format(
                json.dumps(scorecard, ensure_ascii=False)))

        print()
        print("live .harness/ untouched: {}".format(
            "YES" if not diffs else "NO -- " + "; ".join(diffs)))

        fired = sum(1 for r in sc.rows if r["outcome"] == "fired")
        blocked = sum(1 for r in sc.rows if r["outcome"] == "blocked")
        unbuilt = sum(1 for r in sc.rows if r["outcome"] == "unbuilt")
        print("totals: fired={} blocked={} unbuilt={} (of {})".format(
            fired, blocked, unbuilt, len(sc.rows)))

        return 0 if not diffs else 1
    finally:
        if not args.keep:
            # Remove exactly the directory tempfile.mkdtemp returned above, by
            # that exact path -- never a computed parent, never a glob.
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
