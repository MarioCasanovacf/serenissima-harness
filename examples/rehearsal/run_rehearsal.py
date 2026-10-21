#!/usr/bin/env python3
"""run_rehearsal.py -- T-440/T-444: one connected story, told through the tools' own CLIs,
under its OWN throwaway root (operator ruling, decision 9, .harness/operator-rulings-
2026-10-21.md).

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
A replay of that same publish-follows shape runs inside the sandbox below so this
story is connected end to end -- it is a replay of a mechanism that already fired
live, not a first firing, and the scorecard row says so.

T-440's first build ran this story with the sandbox's copy of `trust/`, `warrants/`
and `constitutional/` carried over VERBATIM from the live tree -- never a new
signature, because the coordinator was barred from copying the operator's private
keys or from signing anything. That bar is exactly what stopped four mechanisms cold:
a fedatario act could sign but never verify, a delegation could never be granted, a
fork could never be contested, and a case could never be disposed by `distinguish` --
all four for the SAME root cause, named in the T-440 scorecard's own blocker text:
the sandbox held no key recorded in any warrant.

Decision 9 (2026-10-21) lifts exactly that bar, inside the sandbox only: this script
now MINTS ITS OWN ROOT, generated with ssh-keygen inside the very temp directory it
creates, and re-mints the same 9 W-002 names with fresh keys through warrant.py's own
`draft`/`apply` CLI verbs, signing the draft the way the operator signs
(`ssh-keygen -Y sign`) -- except the key is this run's own throwaway root, never
`~/.ssh/harness_root`. The sandbox's copy of `trust/`, `warrants/` and `roster.json`
(carried over from the live tree by `build_sandbox`) is REPLACED, not layered on top
of, by `mint_sandbox_root`: the live warrants were signed by the OPERATOR's real root
and would simply fail to verify under this fresh anchor, which would pollute
`reconcile`/`audit` with "invalid" rows this story has no interest in. The sandbox's
copy of `constitutional/reputation.json` is RE-SIGNED, same bytes, under the same
fresh root, so Phase B's gate (`reputation.py`) still verifies here -- without that,
minting a new root would silently turn OFF the one mechanism (`phase B yield`) that
already fired under the old, carried-over trust.

THIS IS THE DEFAULT, UNCONDITIONALLY, not a flag. The thing a flag would gate -- the
old, shared-trust path -- was never exercising a different MECHANISM; it was
reproducing the exact same D-17/DIS-1 limit (no key, no signature, no privileged act)
four times over, in four different tools, for one root cause the T-440 scorecard had
already named once. Keeping it switchable would mean testing and maintaining two
sandbox-construction paths for the sake of re-demonstrating one already-written-down
limit. There is nothing left for a flag to choose between.

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
     first record's own `cited_by`. This is the publish-follows REPLAY described above.
  6b. A THIRD dispute is opened on a third task, and `fed-codificador` disposes it
     for real by CITATION (`precedent.py distinguish`, not `publish`): signed under
     the sandbox root's own warrant, this is the first of the mechanisms decision 9
     unblocks, and it moves `disposition-ratio`'s `by_citation` column off zero.
  7. That citation activity gives `registro-a` a non-zero Phase B reputation score.
     `registro-a` holds a live claim on the board; a brand-new, zero-score identity
     then calls `blackboard.py next` and is mechanically outranked (phase_b_yield).
     This mechanism fired under the OLD carried-over trust too; it is listed here as
     depending on the sandbox root because `constitutional/reputation.json` had to be
     re-signed under the fresh anchor for it to keep firing at all.
  8a. `fed-codificador` signs an act with ITS OWN freshly-minted, warrant-matching key
     and `attest.py verify` reports it clean -- the second mechanism decision 9
     unblocks: under the OLD carried-over trust this step could sign but never verify,
     because the sandbox held no private key matching any warrant-recorded pubkey.
  8b. `fed-codificador` delegates `distinguish` to `casona-escribano` with a ceiling
     (expiry, kind subset); the delegate disposes a fourth case WITHIN that ceiling,
     then attempts `contest`, which it was never granted, and is refused by the
     DELEGATION CEILING check -- the third mechanism decision 9 unblocks.
  8c. A fork is produced under `fed-codificador`'s name and detected by `attest.py
     forks`, then contested by a DIFFERENT name, `fed-registrar`, with the contested
     act carrying no weight (PR-022 clause 4) -- the fourth mechanism decision 9
     unblocks. The shipped `sign` verb appends at the tip BY DESIGN (DIS-1), so no
     amount of concurrency through that verb alone ever produces a fork (T-440 proved
     that live, with two real concurrent CLI calls landing as sequential acts, not
     siblings). The fork below is produced the only other way one can exist: a sibling
     act file written directly to disk, OUTSIDE `attest.py sign`, by this script --
     signed with `fed-codificador`'s own (sandbox-minted) key, the way a forger who
     already holds the key would. The scorecard labels that step a SIMULATED FORGER;
     detection and the no-weight report are the tool's own, exercised for real.
  9. `currency.py` and `event_stats.py` read the sandbox's own events and precedents.
 10. `westphalia_kpi.py` is run against the sandbox; it refuses to emit a cost figure
     because the tool's own, hardcoded registry list names exactly one domain
     registry (`precedents/`) today, and PR-029 clause 6 forbids reporting that as
     zero. Unaffected by decision 9.
 11. Contracts and breach (decision 2) are reported UNBUILT: `.harness/design-T-436-
     contracts.md` is a design note, not code. Unaffected by decision 9.

SECURITY, enforced by this script and not merely asserted:
  - `.harness/keys/` under the LIVE tree is NEVER read, and `~/.ssh/harness_root` is
    never referenced. Every key this script ever holds -- the sandbox's own root
    AND the 9 re-minted W-002 names AND the one delegated identity -- is generated
    fresh with `ssh-keygen` INSIDE the temp directory this run created, and every one
    of them dies with it (removed by default, T-442; see `--keep`).
  - The sandbox's copy of `trust/`, `warrants/` and `roster.json` -- carried over as a
    literal copy of the live tree by `build_sandbox` -- is REPLACED by
    `mint_sandbox_root` before the story runs: the live copies are signed by the
    operator's real key and are of no further use once this run has its own anchor.
    `constitutional/reputation.json` is the one exception that is RE-SIGNED rather
    than replaced: same bytes, new detached signature, under the sandbox root.
  - No warrant that authorizes anything on the LIVE board is ever signed, drafted,
    applied or even read for private material. Every signature this script produces
    is over a payload living inside THIS run's own temp directory, verified against
    THIS run's own anchor, by THIS run's own copy of the tools (see `bindir` below --
    every subprocess call in `run_story` and `mint_sandbox_root` invokes the SANDBOX
    copy of a tool, never the live one, because a tool resolves its own default root
    from its own file's location).
  - Every mutation happens through a subprocess call onto a tool's own CLI inside the
    sandbox; this script never imports `blackboard`, `precedent`, `deliberate`,
    `attest`, `warrant`, `reputation`, `currency`, `event_stats` or `westphalia_kpi`
    as a module.
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
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
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

# The same 9 names W-002 issued live (.harness/warrants/W-002.json), re-minted here
# under the SANDBOX's own root with FRESH keys (decision 9). Hardcoded rather than
# read off the live warrant: these identities and seats ARE the story's cast, named
# identically throughout `run_story` below, not a value this script discovers.
W002_SEATS = {
    "fed-registrar": ("fedatario", "registrar"),
    "fed-relator": ("fedatario", "relator"),
    "fed-regulador": ("fedatario", "regulador"),
    "fed-codificador": ("fedatario", "codificador"),
    "registro-a": ("registro", "author"),
    "registro-b": ("registro", "verifier"),
    "revision-doctrina": ("revision", "verifier"),
    "revision-ataque": ("revision", "verifier"),
    "revision-mecanismo": ("revision", "verifier"),
}
W002_COLEGIADOS = {
    "fedatario": "integridad del proceso; NO legisla, NO vota, NO tiene stake "
                 "(AgentCity clerk constraint)",
    "registro": "registros confirmados que sobreviven a la citacion posterior",
    "revision": "refutaciones que se sostienen contra replica; PR-025 c1: el trabajo "
                "adversarial paga mas",
}

# Cited verbatim from the tools that own them (warrant.py's NAMESPACE,
# reputation.py's CONSTITUTIONAL_NAMESPACE, attest.py's NAMESPACE) rather than
# imported, consistent with this script never importing a tool as a module.
WARRANT_NAMESPACE = "harness-warrant"
CONSTITUTIONAL_NAMESPACE = "harness-constitutional"
ATTEST_NAMESPACE = "harness-act"


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
    (e.g. `precedent.py show`'s 'scope: ...' footer, `warrant.py init`'s
    'VERIFY THIS FINGERPRINT' banner) on a non-`--json` call. Parse only the leading
    JSON value and ignore whatever trailer follows it."""
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
    Reads the live tree; never writes to it. `trust/`, `warrants/`, `roster.json` and
    `constitutional/` are copied here too (live, literal bytes) but `mint_sandbox_root`
    replaces or re-signs them before the story runs -- see module docstring."""
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


def root_sign(payload_path, key_path, namespace):
    """`ssh-keygen -Y sign`, the way the operator signs a warrant -- except the key
    here is a throwaway, passphrase-less key this run generated with `genkey`, never
    `~/.ssh/harness_root`. (The SSH_AUTH_SOCK dance warrant.py's own SIGN_RATIONALE
    documents is for a PASSPHRASE-PROTECTED key falling back to an agent that cannot
    confirm; it does not apply here, because every key this script holds has no
    passphrase at all.)"""
    return subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key_path), "-n", namespace,
         str(payload_path)], capture_output=True, text=True, timeout=30)


def mint_sandbox_root(bindir: pathlib.Path, harness_dir: pathlib.Path,
                       keys_dir: pathlib.Path) -> dict:
    """Decision 9: generate the sandbox's own throwaway root, enroll it as the
    SANDBOX's trust root (the sandbox copy of trust/ only -- the live
    .harness/trust is never read for private material and never written), and
    re-mint the same 9 W-002 names with fresh keys through warrant.py's own
    draft/apply CLI, signed under this root the way the operator signs.

    Replaces (never layers onto) the sandbox's copied trust/, warrants/ and
    roster.json: those were copied from the live tree by `build_sandbox` and are
    signed by the OPERATOR's real root, which this fresh anchor cannot verify.
    Re-signs (same bytes, new signature) the sandbox's copied
    constitutional/reputation.json, so Phase B's gate still verifies here.

    Returns {"fingerprint": str, "warrant_id": str, "keys": {name: priv_key_path}}.
    Every subprocess call below runs the SANDBOX's own warrant.py (bindir/warrant.py,
    which resolves its own default root from its own file location) -- never the
    live one.
    """
    warrant_py = bindir / "warrant.py"

    # ---- a clean slate for the sandbox's OWN trust/warrants/roster -------------
    # (the sandbox copy only; see module docstring's SECURITY section)
    shutil.rmtree(harness_dir / "trust", ignore_errors=True)
    shutil.rmtree(harness_dir / "warrants", ignore_errors=True)
    shutil.rmtree(harness_dir / "acts", ignore_errors=True)
    (harness_dir / "roster.json").write_text(
        json.dumps({"schema_version": 1, "colegiados": {}, "plazas": {}, "names": {}},
                   indent=2) + "\n", encoding="utf-8")

    # ---- the sandbox's own root key, generated and dying inside this run's tmp dir
    root_key = genkey(keys_dir, "sandbox-root")
    root_pub = pathlib.Path(str(root_key) + ".pub")

    init_out = run([PY, warrant_py, "--root", str(harness_dir), "init",
                    "--root-pub", str(root_pub)])
    if init_out.returncode != 0:
        raise RuntimeError("sandbox root init failed: {}".format(init_out.stderr))
    fingerprint = leading_json(init_out.stdout).get("fingerprint")

    # ---- fresh keys for the same 9 W-002 names, and a warrant that re-mints them
    name_keys, name_specs, plaza_counts = {}, [], {}
    for name, (colegiado, role) in W002_SEATS.items():
        kp = genkey(keys_dir, name)
        name_keys[name] = kp
        pub = pathlib.Path(str(kp) + ".pub")
        name_specs.append("{}:{}/{}:{}".format(name, colegiado, role, pub))
        seat = (colegiado, role)
        plaza_counts[seat] = plaza_counts.get(seat, 0) + 1

    draft_argv = [PY, warrant_py, "--root", str(harness_dir), "draft",
                  "--epic", "casona-sandbox-root"]
    for colegiado, incentive in W002_COLEGIADOS.items():
        draft_argv += ["--colegiado", "{}={}".format(colegiado, incentive)]
    for (colegiado, role), n in plaza_counts.items():
        draft_argv += ["--plaza", "{}/{}={}".format(colegiado, role, n)]
    for spec in name_specs:
        draft_argv += ["--name", spec]
    draft_out = run(draft_argv)
    if draft_out.returncode != 0:
        raise RuntimeError("sandbox warrant draft failed: {}".format(draft_out.stderr))
    draft = json.loads(draft_out.stdout)
    wid, payload_path = draft["warrant_id"], pathlib.Path(draft["path"])

    sig = root_sign(payload_path, root_key, WARRANT_NAMESPACE)
    if sig.returncode != 0:
        raise RuntimeError(
            "sandbox root signature over the warrant failed: {}".format(sig.stderr))

    apply_out = run([PY, warrant_py, "--root", str(harness_dir), "apply",
                      "--warrant", wid])
    if apply_out.returncode != 0:
        raise RuntimeError("sandbox warrant apply failed: {}".format(apply_out.stderr))

    # ---- re-sign the COPIED constitutional file under the SAME sandbox root, so
    # Phase B's gate (reputation.py) still verifies here (decision 9's own condition)
    const_path = harness_dir / "constitutional" / "reputation.json"
    if const_path.exists():
        const_sig = pathlib.Path(str(const_path) + ".sig")
        const_sig.unlink(missing_ok=True)
        csig = root_sign(const_path, root_key, CONSTITUTIONAL_NAMESPACE)
        if csig.returncode != 0:
            raise RuntimeError(
                "sandbox root signature over the constitutional file failed: {}"
                .format(csig.stderr))

    return {"fingerprint": fingerprint, "warrant_id": wid, "keys": name_keys,
            "root_key": root_key}


def forge_sibling_act(harness_dir: pathlib.Path, name: str, key_path, prev: str,
                       seq: int, kind="commit"):
    """Write ONE sibling act file directly to `name`'s chain, bypassing
    `attest.py sign` entirely -- the only way to produce a fork, because the shipped
    verb always appends at the TIP (DIS-1; T-440 measured that two real concurrent
    CLI calls land as sequential acts, never siblings). Signed with `name`'s own key:
    a SIMULATED FORGER who already holds it (D-17), not a stolen one. Detection is
    `attest.py forks`' job, called separately, for real, on the result."""
    d = pathlib.Path(harness_dir) / "acts" / name
    d.mkdir(parents=True, exist_ok=True)
    path = d / "{:03d}.json".format(seq)
    path.write_text(json.dumps({
        "schema_version": 1, "name": name, "seq": seq, "kind": kind, "ref": "",
        "body": {"SIMULATED_FORGER": "written directly to {} by run_rehearsal.py, "
                                      "outside attest.py sign, to produce the sibling "
                                      "the shipped verb by design cannot".format(path.name)},
        "prev": prev, "ts": now_iso(), "namespace": ATTEST_NAMESPACE,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sig = root_sign(path, key_path, ATTEST_NAMESPACE)
    return path, sig


def fresh_task_ids(harness_dir: pathlib.Path, n: int) -> list:
    bb = json.loads((harness_dir / "blackboard.json").read_text(encoding="utf-8"))
    nums = [int(tid[2:]) for tid in bb.get("tasks", {})
            if tid.startswith("T-") and tid[2:].isdigit()]
    start = (max(nums) if nums else 0) + 1
    return ["T-{}".format(start + i) for i in range(n)]


# --------------------------------------------------------------------------- story

def run_story(bindir: pathlib.Path, harness_dir: pathlib.Path, keys_dir: pathlib.Path,
              root: dict, sc: Scorecard):
    bb = str(bindir / "blackboard.py")
    precedent = str(bindir / "precedent.py")
    deliberate = str(bindir / "deliberate.py")
    attest = str(bindir / "attest.py")
    currency = str(bindir / "currency.py")
    event_stats = str(bindir / "event_stats.py")
    westphalia = str(bindir / "westphalia_kpi.py")
    events_log = harness_dir / "logs" / "events.jsonl"
    hroot = str(harness_dir)

    root_fp = root["fingerprint"]
    root_note = ("signed under the rehearsal's own throwaway root ({}, warrant {}), "
                 "never the operator's ~/.ssh/harness_root".format(root_fp, root["warrant_id"]))
    root_keys = root["keys"]
    fed_key = root_keys["fed-codificador"]

    (t_welcome, t_second, t_third, t_fourth, t_open) = fresh_task_ids(harness_dir, 5)

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

    # ---- 6: a second case disposed by citing the first precedent (REPLAY) -----
    run([PY, bb, "add-task", "--id", t_second,
         "--title", "Casona: segunda acta de bienvenida", "--role", "worker",
         "--engine", "any", "--agent", "fed-regulador"])
    case2 = run([PY, precedent, "case", "open", "--question",
                 "La segunda acta ({}) tambien fija un termino sin ratio: le aplica "
                 "{}?".format(t_second, pr1_id), "--task", t_second, "--agent",
                 "fed-regulador", "--harness-root", hroot])
    case2_id = first_match(r"case (C-\d+)", case2.stdout)

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
        "disposed by PR-063, 2026-09-20), visible in disposition-ratio. Does not "
        "depend on the sandbox root: precedent.py publish is not a signed act.",
        "fired" if pub2.returncode == 0 and cited_back else "blocked",
        evidence="precedent.py publish --case {} --follows {} -> {} ; "
                  "precedent.py show {} -> cited_by={} ; precedent.py "
                  "disposition-ratio --json -> by_legislation_registered_raw={}, "
                  "cases_opened_raw={} (this run's sandbox cases are among them, on "
                  "top of the 2 that already disposed by this shape live).".format(
                      case2_id, pr1_id, pr2_id, pr1_id,
                      show_pr1_json.get("cited_by"),
                      disp_ratio_json.get("by_legislation_registered_raw"),
                      disp_ratio_json.get("cases_opened_raw")),
    )

    # ---- 6b: a THIRD case disposed by `distinguish` (by_citation), decision 9 -
    run([PY, bb, "add-task", "--id", t_third,
         "--title", "Casona: tercera acta de bienvenida", "--role", "worker",
         "--engine", "any", "--agent", "fed-regulador"])
    case3 = run([PY, precedent, "case", "open", "--question",
                 "La tercera acta ({}) repite el mismo patron operativo: se dispone "
                 "citando {}, o hace falta legislar de nuevo?".format(t_third, pr1_id),
                 "--task", t_third, "--agent", "fed-regulador", "--harness-root", hroot])
    case3_id = first_match(r"case (C-\d+)", case3.stdout)

    intent3 = run([PY, attest, "declare-intent", "--name", "fed-codificador", "--key",
                   str(fed_key), "--for-kind", "distinguish", "--task", t_third,
                   "--for-ref", pr1_id, "--declares",
                   "fed-codificador dispone de {} citando {}, dentro de su propia "
                   "autoridad de warrant".format(case3_id, pr1_id)])
    distinguish3 = run([PY, precedent, "distinguish", "--case", case3_id, "--nearest",
                         pr1_id, "--facts",
                         "la tercera acta repite exactamente el mismo patron operativo "
                         "que la primera acta ya resolvio, sin ningun hecho nuevo que "
                         "la distinga de ese caso anterior", "--by", "fed-codificador",
                         "--key", str(fed_key), "--task", t_third, "--harness-root",
                         hroot])
    disp_ratio3 = run([PY, precedent, "disposition-ratio", "--json", "--harness-root",
                        hroot])
    disp_ratio3_json = (json.loads(disp_ratio3.stdout)
                         if disp_ratio3.returncode == 0 and disp_ratio3.stdout else {})
    # T-445 round 2: `by_citation_raw` counts signed `distinguish` ACTS off the attest
    # chain, not the case record's own disposal field, so a regression inside
    # `dispose_case()` (the call that actually flips the case to disposed) can leave
    # that counter and this row's evidence untouched while the case stays open. Read
    # the case record itself back through `case show --json` -- a path that does not
    # go anywhere near the attest chain -- so this row (and the test pinning it) are
    # sensitive to the thing the mechanism's name claims: the CASE was disposed, not
    # merely that an act was signed and a counter moved.
    case3_show = run([PY, precedent, "case", "show", case3_id, "--json", "--harness-root",
                       hroot])
    case3_show_json = (json.loads(case3_show.stdout)
                        if case3_show.returncode == 0 and case3_show.stdout else {})
    case3_disposal = case3_show_json.get("disposal") or {}
    case3_disposed_by_distinguish = (
        case3_show_json.get("status") == "disposed"
        and case3_disposal.get("verb") == "distinguish"
    )
    sc.record(
        "a case disposed by `distinguish` (by_citation), " + root_note,
        "fired" if distinguish3.returncode == 0
        and disp_ratio3_json.get("by_citation_raw", 0) >= 1
        and case3_disposed_by_distinguish else "blocked",
        evidence="attest.py declare-intent --name fed-codificador --for-kind distinguish "
                  "(rc={}) ; precedent.py distinguish --case {} --nearest {} --by "
                  "fed-codificador --key <sandbox-minted, warrant-matching key> -> "
                  "rc={}: {} ; disposition-ratio --json -> by_citation_raw={} ; "
                  "case show {} --json -> case_status={} disposal_verb={}".format(
                      intent3.returncode, case3_id, pr1_id, distinguish3.returncode,
                      distinguish3.stdout.strip().splitlines()[0]
                      if distinguish3.returncode == 0 else distinguish3.stderr.strip()[:200],
                      disp_ratio3_json.get("by_citation_raw"),
                      case3_id, case3_show_json.get("status"), case3_disposal.get("verb")),
        blocker=None if (distinguish3.returncode == 0 and case3_disposed_by_distinguish)
                 else distinguish3.stderr.strip()[:300] or "case {} shows status={} "
                      "disposal={} after `distinguish` claimed rc=0 -- the case record "
                      "itself was never disposed".format(
                          case3_id, case3_show_json.get("status"), case3_disposal),
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
        "a phase B yield (event phase_b_yield) from blackboard.py next -- " + root_note
        + "; the constitutional gate (reputation.py) only verifies because "
          "mint_sandbox_root re-signed constitutional/reputation.json under this run's "
          "own root",
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
        "an act signed by a fedatario seat holder and verified -- " + root_note,
        "fired" if sign1.returncode == 0 and verified_clean else "blocked",
        evidence="attest.py sign --name fed-codificador --key <sandbox-minted, "
                  "warrant-matching key> --kind commit -> act written (rc={}) ; "
                  "attest.py verify --name fed-codificador --json -> enrolled={}, "
                  "signature_failures={}".format(
                      sign1.returncode, verify1_json.get("enrolled"),
                      verify1_json.get("signature_failures"))
        if sign1.returncode == 0 else None,
        blocker=None if verified_clean else
                "attest.py verify reported a signature failure even though the key "
                "matches this run's own sandbox warrant: {}".format(
                    verify1_json.get("signature_failures")),
    )

    # ---- 8b: a delegation with a ceiling, used within and refused beyond ------
    scribe_key = genkey(keys_dir, "casona-escribano")
    scribe_pub = (keys_dir / "casona-escribano.pub").read_text(encoding="utf-8").strip()
    grant_intent = run([PY, attest, "declare-intent", "--name", "fed-codificador",
                        "--key", str(fed_key), "--for-kind", "grant", "--task",
                        t_second, "--for-ref", "casona-escribano", "--declares",
                        "fed-codificador delega distinguish a casona-escribano"])
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
                 "--note", "delega SOLO distinguish, con techo de 2h"])

    run([PY, bb, "add-task", "--id", t_fourth,
         "--title", "Casona: cuarta acta de bienvenida", "--role", "worker",
         "--engine", "any", "--agent", "fed-regulador"])
    case4 = run([PY, precedent, "case", "open", "--question",
                 "La cuarta acta ({}) repite el mismo patron operativo: dispone "
                 "casona-escribano, bajo el techo delegado?".format(t_fourth),
                 "--task", t_fourth, "--agent", "fed-regulador", "--harness-root", hroot])
    case4_id = first_match(r"case (C-\d+)", case4.stdout)

    if grant.returncode != 0:
        sc.record(
            "a delegation with a ceiling used within it and refused beyond it -- "
            + root_note,
            "blocked",
            blocker="declare-intent for the privileged 'grant' kind: {!r} / grant "
                    "itself refused: {!r}. If the intent is the cause: attest.py's "
                    "open_intents() only recognizes an intent SIGNED AND VERIFIED "
                    "against the name's ENROLLED (warrant-recorded) key -- this "
                    "should not happen once fed-codificador's key matches this run's "
                    "own sandbox warrant; treat this branch as a regression if it "
                    "fires.".format(grant_intent.stderr.strip()[:200],
                                       grant.stderr.strip()[:200]),
        )
    else:
        # casona-escribano holds its OWN matching key (scribe_key/scribe_pub were
        # supplied verbatim at grant time, not inherited from any warrant), so ITS
        # intents and acts verify cleanly.
        run([PY, attest, "declare-intent", "--name", "casona-escribano", "--key",
             str(scribe_key), "--for-kind", "distinguish", "--task", t_fourth,
             "--for-ref", pr1_id, "--declares",
             "casona-escribano dispone de {} citando {}, dentro del techo "
             "delegado".format(case4_id, pr1_id)])
        within = run([PY, precedent, "distinguish", "--case", case4_id, "--nearest",
                      pr1_id, "--facts",
                      "la cuarta acta repite exactamente el mismo patron operativo "
                      "que la primera acta ya resolvio, sin ningun hecho nuevo que la "
                      "distinga de ese caso anterior", "--by", "casona-escribano",
                      "--key", str(scribe_key), "--task", t_fourth, "--harness-root",
                      hroot])
        run([PY, attest, "declare-intent", "--name", "casona-escribano", "--key",
             str(scribe_key), "--for-kind", "contest", "--task", t_fourth,
             "--for-ref", "fed-codificador#0", "--declares",
             "casona-escribano intenta contestar mas alla de lo delegado"])
        beyond = run([PY, attest, "contest", "--by", "casona-escribano", "--key",
                      str(scribe_key), "--name", "fed-codificador", "--seq", "0",
                      "--reason", "mas alla del techo delegado", "--task", t_fourth])
        ceiling_refused = (beyond.returncode != 0
                            and "DELEGATION CEILING" in beyond.stderr)
        sc.record(
            "a delegation with a ceiling used within it and refused beyond it -- "
            + root_note,
            "fired" if within.returncode == 0 and ceiling_refused else "blocked",
            evidence="attest.py grant --by fed-codificador --kinds distinguish -> "
                      "casona-escribano; precedent.py distinguish --case {} (within "
                      "ceiling) by casona-escribano -> rc={} ; attest.py contest "
                      "(beyond ceiling) refused rc={}: {!r}".format(
                          case4_id, within.returncode, beyond.returncode,
                          beyond.stderr.strip()[:200]),
            blocker=None if ceiling_refused else
                    "contest was not refused by the DELEGATION CEILING check as "
                    "expected: within.rc={} within.stderr={!r} beyond.stderr={!r}"
                    .format(within.returncode, within.stderr.strip()[:200],
                            beyond.stderr.strip()[:200]),
        )

    # ---- 8c: a fork, produced by a simulated forger, detected and contested ---
    fork_first = run([PY, attest, "sign", "--name", "fed-codificador", "--key",
                       str(fed_key), "--kind", "commit", "--ref", "fork-story-genesis",
                       "--body", json.dumps({"note": "primer acto honesto, antes de "
                                                      "la bifurcacion simulada"})])
    fork_first_json = (json.loads(fork_first.stdout) if fork_first.returncode == 0
                        and fork_first.stdout.strip() else {})
    # The forged sibling must share fork_first's OWN `prev`, not a guessed value --
    # fed-codificador already signed once in step 8a, so fork_first's prev is THAT
    # act's digest, not "genesis". Matching test_warrant.py's ForkDetection.forge():
    # two acts claiming the SAME predecessor IS the fork.
    fork_prev = fork_first_json.get("prev")
    forged_path, forged_sig = forge_sibling_act(
        harness_dir, "fed-codificador", fed_key, prev=fork_prev, seq=99)
    forks = run([PY, attest, "forks"])
    forks_list = leading_json(forks.stdout) if forks.stdout.strip().startswith("[") else []
    # forks() (the flattened, cross-name view) does not tag each fork with a `name`
    # field -- it is reached per-name via `verify --name` instead -- so the match
    # here is the shared `prev` digest this story's two siblings both claim, which is
    # unique enough to identify THIS fork rather than any other.
    this_fork = next((f for f in forks_list if f.get("prev") == fork_prev), None)
    forks_found = bool(fork_prev) and this_fork is not None \
        and this_fork.get("STATUS") == "CONTESTED"
    intent_contest = run([PY, attest, "declare-intent", "--name", "fed-registrar",
                          "--key", str(root_keys["fed-registrar"]), "--for-kind",
                          "contest", "--task", t_second, "--for-ref",
                          "fed-codificador#99", "--declares",
                          "fed-registrar acusa a fed-codificador de una bifurcacion "
                          "en su cadena de actos (el acto simulado-forjado, seq 99)"])
    contest_attempt = run([PY, attest, "contest", "--by", "fed-registrar", "--key",
                            str(root_keys["fed-registrar"]), "--name",
                            "fed-codificador", "--seq", "99", "--reason",
                            "bifurcacion detectada por attest.py forks", "--task",
                            t_second])
    sc.record(
        "a fork under one name detected by attest.py forks and contested by a "
        "different name, with the contested act carrying no weight (PR-022 clause 4) "
        "-- " + root_note + "; the fork is produced by a SIMULATED FORGER (one "
        "sibling act file written directly to disk, outside attest.py sign, since "
        "the shipped verb appends at the tip by design); detection is the tool's own",
        "fired" if fork_first.returncode == 0 and forged_sig.returncode == 0
        and forks_found and contest_attempt.returncode == 0 else "blocked",
        evidence="fed-codificador's act #5 (honest, via attest.py sign) and one "
                  "sibling act file ({}, seq 99) written directly to disk, both "
                  "sharing the SAME prev {!r}, signed with fed-codificador's own "
                  "key -- simulating a forger who already holds it (D-17); "
                  "attest.py forks -> STATUS={!r} MEANS={!r} ; attest.py contest "
                  "--by fed-registrar (a DIFFERENT, warrant-enrolled name) --name "
                  "fed-codificador --seq 99 -> rc={}, filed on fed-registrar's OWN "
                  "chain (DIS-5); PR-022 clause 4 and attest.py's own "
                  "NO_CONSEQUENCE text say the contested act carries no weight "
                  "until adjudicated".format(
                      forged_path.name, fork_prev, this_fork.get("STATUS"),
                      this_fork.get("MEANS"), contest_attempt.returncode)
        if forks_found and contest_attempt.returncode == 0 else None,
        blocker=None if (forks_found and contest_attempt.returncode == 0) else
                "fork_first.rc={} forged_sig.rc={} forks_found={} intent_contest.rc={} "
                "contest_attempt.rc={}: {!r}".format(
                    fork_first.returncode, forged_sig.returncode, forks_found,
                    intent_contest.returncode, contest_attempt.returncode,
                    contest_attempt.stderr.strip()[:200]),
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
        "Run the Casona rehearsal story in a throwaway sandbox copy of .harness/, "
        "under its own throwaway root (decision 9). The sandbox is removed at the "
        "end by default."))
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
            root = mint_sandbox_root(bindir, harness_dir, keys_dir)
            run_story(bindir, harness_dir, keys_dir, root, sc)
        finally:
            after = integrity_snapshot()
            diffs = integrity_diff(before, after)

        scorecard = {
            "task": "T-440/T-444",
            "sandbox": str(tmp_root),
            "sandbox_root_fingerprint": root.get("fingerprint"),
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
