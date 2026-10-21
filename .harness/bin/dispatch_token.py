#!/usr/bin/env python3
"""dispatch_token.py - option 5 of T-432's identity design, ratified 2026-10-21 (decision
1): short-lived dispatch tokens, signed by the operator's root key, one signature per
epic ("1 firma tuya por proyecto, no 1 por tarea").

NAME, AND WHY IT IS NOT token.py. The task that specified this module (T-446) asked for
`.harness/bin/token.py` unless that name collides, and it does, measurably: the Python
standard library ships a module literally named `token` (imported by `tokenize`, which
`inspect`/`unittest` paths touch), and several test files in this repository do
`sys.path.insert(0, str(BIN_DIR))` before importing anything, which puts `.harness/bin`
ahead of the stdlib on `sys.path`. A file at `.harness/bin/token.py` would shadow the
real `token` module for every one of those test processes. Measured directly: a stub
`token.py` placed on `sys.path` ahead of the stdlib makes `import tokenize` raise
`ImportError: cannot import name 'EXACT_TOKEN_TYPES' from 'token'` immediately, which
would break any test file that imports `tokenize`/`inspect` transitively AFTER this
module's test file runs first in the same process. `dispatch_token.py` has no such
collision.

FIELDS (ratified). One token: `(agent_name, task_id, role, issued_at, expiry, nonce)`.
GRAIN (ratified). One signed file per epic, carrying that epic's whole set of tokens --
not one signature per dispatch, so the operator's attention cost stays O(1) per epic
rather than O(1) per task claim (design doc, option 5, "What the operator must run by
hand").

SIGNING KEY (ratified, and the point the card made a hard condition). The signature is
an SSH signature by the OPERATOR'S ROOT key (`~/.ssh/harness_root`), through the exact
same out-of-band `ssh-keygen -Y sign` gate `warrant.py` already uses -- never an HMAC,
never any key this module could hold or generate, because under D-17 every agent runs as
the same OS user on the same filesystem and a shared MAC key is a key every agent can
read, which would let any agent mint its own tokens. The verifier of T-433 did not catch
that gap; the operator's 2026-10-21 card made it a condition and ratified it. This module
reuses `warrant.py`'s trust anchor directly (`trust/root.pub`, `trust/root.fingerprint`):
there is exactly one operator root in this harness, used for both warrants and dispatch
tokens, per the ruling's own words ("signed with the operator's root key through the same
out-of-band gate that signs warrants").

NAMESPACE. `harness-dispatch-token`, distinct from both `warrant.NAMESPACE`
("harness-warrant") and `attest.NAMESPACE` ("harness-act"), so a signature minted for one
surface can never be replayed as proof for another.

THIS PROCESS CANNOT SIGN (D-16, same discipline as `warrant.py`). `draft` writes an
UNSIGNED payload and prints the exact command the operator runs. No function in this
module invokes `ssh-keygen -Y sign`; `test_dispatch_token.py` asserts that, the same
shape as `test_warrant.py`'s `TheHarnessCannotSign`.

NONCES ARE NOT SINGLE-USE HERE, AND THAT IS STATED RATHER THAN HIDDEN. `verify()` is a
pure, stateless check over a signed file on disk: it has nowhere to record "this nonce
was already consumed" without a second piece of mutable state. A valid, unexpired token
therefore verifies successfully every time it is presented within its window, including a
second time; `test_dispatch_token.py` pins that. T-454 (below) puts single-use
consumption where it belongs instead: `blackboard.py claim`'s own mutation of
blackboard.json, which is the one call site with a place to keep "seen nonces" state
that this module does not. `lock.py acquire` deliberately does NOT consume nonces, even
after T-454: re-acquiring/refreshing a lock you already hold is the ordinary heartbeat
pattern, and making the token single-use there would break the first refresh under a
still-valid, still-correct token.

WHAT THIS DOES NOT DO (unchanged from the design doc and the ruling). A token proves the
operator authorized this `(agent_name, task_id, role)` tuple before the act existed. It
does not prove any specific act performed under it is the act the operator meant --
identical to W-002's own stated limit on plazas ("signed plazas bound HOW MANY seats
exist. They do not bound WHO occupies them"). Impersonation inside a token's validity
window stays open (D-17). PR-022 clause 4 holds: nothing here attaches a consequence.

WIRING (T-454). `blackboard.py claim` and `lock.py acquire` now import this module and
call `epic_requires_token()` / `verify()` as an OPTIONAL, ADDITIVE check: unchanged
behaviour unless the epic in question carries a signed requirement. The requirement
itself lives INSIDE the epic's own signed token-set payload (`"required": true`, part of
the same signed bytes as the tokens -- see `draft()`'s `required` parameter and
`epic_requires_token()` below), not as a second, separately-signed record: one signed
artifact per epic stays the only thing the operator mints for this whole mechanism, and a
second record would need its own reconciliation against whichever token set it modifies.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import secrets
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness_common as hc  # noqa: E402
import warrant as w  # noqa: E402 -- local import, reuses the one operator trust anchor

NAMESPACE = "harness-dispatch-token"   # distinct from warrant.NAMESPACE and attest.NAMESPACE
SCHEMA_VERSION = 1
DEFAULT_TTL_SECONDS = 24 * 3600        # one dispatch window; overridable per draft or per token

PUBLIC_API = ("resolve_root", "token_sets_dir", "draft", "verify_token_set",
             "epic_requires_token", "verify")

TrustError = w.TrustError              # same exception family as warrant.py; no new vocabulary


class UnsignedTokenSet(TrustError):
    """A token-set payload exists and carries NO signature file yet.

    A subclass, not a bare TrustError, for the same reason warrant.py's UnsignedWarrant
    is one: a caller that only cares "is this authorized" keeps working unchanged
    (UnsignedTokenSet IS a TrustError), while a caller that wants to tell "awaiting the
    operator" apart from "signature exists and fails" can catch this subclass instead.
    """


# ------------------------------------------------------------------ paths and roots

def resolve_root(flag=None) -> pathlib.Path:
    return w.resolve_root(flag)


def token_sets_dir(root) -> pathlib.Path:
    return pathlib.Path(root) / "dispatch_tokens"


def next_token_set_id(root) -> str:
    td = token_sets_dir(root)
    n = 0
    if td.exists():
        for p in td.glob("DT-*.json"):
            try:
                n = max(n, int(p.stem.split("-")[1]))
            except (IndexError, ValueError):
                continue
    return f"DT-{n + 1:03d}"


import re  # noqa: E402

DTID_RE = re.compile(r"^DT-\d{3,}$")


def check_dtid(dtid) -> str:
    """A token-set id is a filename, never a path -- same discipline as warrant.py's
    check_wid, and for the identical reason: `dtid:../stash/DT-001` must not let
    verification and any future reconciliation read different sets of documents."""
    dtid = str(dtid).strip()
    if not DTID_RE.match(dtid):
        raise TrustError(f"malformed token-set id {dtid!r}; expected DT-NNN")
    return dtid


# -------------------------------------------------------------------------- drafting

def _parse_dispatch(spec: str):
    """'worker-a:T-432:worker' or 'worker-a:T-432:worker:1800' (per-token TTL override,
    seconds) -> (agent_name, task_id, role, ttl_override_or_None)."""
    parts = spec.split(":")
    if len(parts) < 3:
        raise ValueError(
            f"dispatch must look like agent_name:task_id:role[:ttl_seconds], got {spec!r}")
    agent_name, task_id, role = parts[0].strip(), parts[1].strip(), parts[2].strip()
    if not agent_name or not task_id or not role:
        raise ValueError(f"agent_name, task_id and role must all be non-empty: {spec!r}")
    ttl_override = None
    if len(parts) > 3 and parts[3] != "":
        try:
            ttl_override = int(parts[3])
        except ValueError:
            raise ValueError(f"ttl_seconds must be an integer, got {parts[3]!r}")
        if ttl_override <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_override}")
    return agent_name, task_id, role, ttl_override


def draft(root, epic, dispatch_specs, ttl_seconds=DEFAULT_TTL_SECONDS, required=False) -> dict:
    """Write an UNSIGNED dispatch-token-set payload for one epic and return the exact
    command the operator runs. No sibling function in this module can sign; see the
    module docstring. Mirrors warrant.py's draft() in shape on purpose.

    `required` (T-454): True means the operator is drafting this set as the epic's own
    requirement -- once SIGNED, `epic_requires_token()` reports this epic needs a token
    for every claim/lock-acquire. False (default) drafts an ordinary, non-mandatory set:
    tokens still verify normally if presented, but nothing is refused for lacking one.
    The flag is part of the signed payload, so an agent cannot flip it after the fact.
    """
    if not dispatch_specs:
        raise ValueError("draft needs at least one agent_name:task_id:role dispatch spec")
    root = pathlib.Path(root)
    issued_at = hc.now_iso()
    tokens = []
    seen = set()
    for spec in dispatch_specs:
        agent_name, task_id, role, ttl_override = _parse_dispatch(spec)
        ttl = ttl_override if ttl_override is not None else ttl_seconds
        tup = (agent_name, task_id, role)
        if tup in seen:
            raise ValueError(f"duplicate dispatch in one draft: {tup}; mint one token "
                             "per (agent_name, task_id, role) per epic")
        seen.add(tup)
        tokens.append({
            "agent_name": agent_name,
            "task_id": task_id,
            "role": role,
            "issued_at": issued_at,
            "expiry": hc.iso_in(ttl),
            "nonce": secrets.token_hex(16),
        })

    dtid = next_token_set_id(root)
    payload = {
        "token_set_id": dtid,
        "schema_version": SCHEMA_VERSION,
        "epic": epic,
        "required": bool(required),
        "issued_at": issued_at,
        "tokens": tokens,
        "namespace": NAMESPACE,
        "NOT_A_CONSEQUENCE": "PR-022 clause 4 holds: a dispatch token authorizes a claim "
                             "attempt for one (agent_name, task_id, role), never a "
                             "weight, a burden, a quorum or a permission",
        "NOT_PROOF_OF_THE_ACT": "This proves the operator authorized this tuple before "
                                "the act existed. It does not prove a specific act under "
                                "it is the act the operator meant (same limit as W-002's "
                                "plazas: bounds how many, not who).",
    }
    td = token_sets_dir(root)
    td.mkdir(parents=True, exist_ok=True)
    path = td / f"{dtid}.json"
    # written once, verbatim, never re-serialised: the signature covers these exact bytes
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    _emit(root, "dispatch_token_set_drafted", token_set=dtid, epic=epic,
          tokens=len(tokens))
    return {
        "token_set_id": dtid,
        "path": str(path),
        "digest": w.payload_digest(path),
        "sign_with": (f"{w.SIGN_ENV}ssh-keygen -Y sign -f {w.ROOT_KEY} "
                      f"-n {NAMESPACE} {path}"),
        "WHY_EVERY_PART_OF_THAT_COMMAND": w.SIGN_RATIONALE,
        "note": "This process cannot sign. Run the command above; it will ask for the "
                "key's passphrase on the terminal. One signature covers every token in "
                "this epic's set.",
    }


def _emit(root, kind, **fields) -> None:
    if w.is_live(root):
        hc.log_event(kind, **fields)
        return
    rec = {"ts": hc.now_iso(), "event": kind, "agent": hc.agent_id()}
    rec.update(fields)
    hc.append_jsonl(pathlib.Path(root) / "events.jsonl", rec)


# ------------------------------------------------------------------------- verification

def _verify_file_signature(root, payload_path, sig_path) -> str:
    """Verify `sig_path` over the exact bytes of `payload_path`, in THIS module's own
    namespace, against the one enrolled operator root `warrant.py` already anchors.
    Deliberately NOT warrant.verify_signature: that function is hardcoded to
    warrant.NAMESPACE, and a signature minted under one namespace must never verify
    under another (the whole point of giving this surface its own namespace).
    """
    import subprocess
    import tempfile

    fp = w.check_anchor(root)
    payload_path, sig_path = pathlib.Path(payload_path), pathlib.Path(sig_path)
    if not sig_path.exists():
        raise UnsignedTokenSet(f"token set is unsigned: {sig_path} does not exist")
    with tempfile.TemporaryDirectory() as tmp:
        allowed = pathlib.Path(tmp) / "allowed_signers"
        pub = (w.trust_dir(root) / "root.pub").read_text(encoding="utf-8").strip()
        allowed.write_text(f"operator {pub}\n", encoding="utf-8")
        with payload_path.open("rb") as fh:
            r = subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I", "operator",
                 "-n", NAMESPACE, "-s", str(sig_path)],
                stdin=fh, text=True, capture_output=True)
    if r.returncode != 0:
        raise TrustError(f"SIGNATURE DOES NOT VERIFY for {payload_path.name}: "
                         f"{(r.stderr or r.stdout).strip()}")
    seen = w.FINGERPRINT_RE.search(r.stdout or "")
    if not seen:
        raise TrustError(
            "ssh-keygen reported success without naming a signing key; refusing rather "
            f"than assuming it was the anchored root. stdout={r.stdout!r}")
    if seen.group(0) != fp:
        raise TrustError(
            f"SIGNED BY THE WRONG KEY: {seen.group(0)} is not the anchored root {fp}.")
    return seen.group(0)


def verify_token_set(root, dtid) -> dict:
    """Verify one epic's signed token-set file against the enrolled root. Returns the
    verified payload and signer fingerprint. Raises TrustError (or UnsignedTokenSet)
    otherwise. Mirrors warrant.verify_warrant in shape.
    """
    dtid = check_dtid(dtid)
    path = token_sets_dir(root) / f"{dtid}.json"
    if not path.exists():
        raise TrustError(f"no token set {dtid}")
    fp = _verify_file_signature(root, path, path.with_suffix(".json.sig"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("namespace") != NAMESPACE:
        raise TrustError(f"{dtid} declares namespace {payload.get('namespace')!r}; "
                         f"dispatch-token signatures are only accepted in {NAMESPACE!r}")
    return {"token_set_id": dtid, "signed_by": fp, "digest": w.payload_digest(path),
            "payload": payload}


def epic_requires_token(root, epic) -> bool:
    """T-454: the single gate `blackboard.py claim` and `lock.py acquire` consult before
    ever asking a caller for a token. True iff some SIGNED, VERIFIED token set for `epic`
    carries `"required": true`. An unsigned draft, a set for a different epic, a set
    signed by the wrong key, or (the common case today) an un-enrolled harness with no
    `dispatch_tokens/` directory at all never makes an epic requirement true -- each of
    those fails the verification below and is skipped rather than raised, so a caller
    with no token sets on disk gets a fast `False` with no subprocess call at all (the
    "no flag day" property T-454's acceptance criteria name).
    """
    td = token_sets_dir(root)
    if not td.exists():
        return False
    for path in sorted(td.glob("DT-*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if raw.get("epic") != epic or not raw.get("required"):
            continue
        dtid = raw.get("token_set_id") or path.stem
        try:
            verify_token_set(root, dtid)
        except TrustError:
            continue
        return True
    return False


def verify(root, presented, claim_agent=None, claim_task=None, claim_role=None) -> dict:
    """Verify one PRESENTED token against the enrolled root, its own expiry, and
    (optionally) that it was presented under the (agent_name, task_id, role) it actually
    names rather than a different one.

    `presented` is the dict the caller is holding: at minimum
    `{"token_set_id", "nonce", "agent_name", "task_id", "role", "issued_at", "expiry"}`.
    Every field is checked against the CANONICAL token of the same nonce inside the
    signed, on-disk epic file -- not against each other -- so a presented copy that
    diverges from what the operator actually signed is refused as tampered, regardless
    of which field was changed.

    If `claim_agent`/`claim_task`/`claim_role` are supplied, they are checked against the
    canonical token's own fields: this is the check that refuses a token minted for
    (worker-a, T-999, worker) when it is PRESENTED AS worker-b. When omitted, this
    function checks only that the token itself is genuine, unexpired and unmodified --
    the caller bears the obligation to compare the canonical identity returned here
    against whatever it actually needs authorized.
    """
    if not isinstance(presented, dict):
        raise TrustError("a presented token must be a mapping with its own fields")
    dtid = presented.get("token_set_id")
    if not dtid:
        raise TrustError("presented token carries no token_set_id; nothing to verify it against")
    v = verify_token_set(root, dtid)
    payload = v["payload"]

    nonce = presented.get("nonce")
    canonical = next((t for t in payload.get("tokens", []) if t.get("nonce") == nonce), None)
    if canonical is None:
        raise TrustError(
            f"no token with nonce {nonce!r} inside the signed set {dtid}; refusing "
            "rather than guessing which signed token this claims to be")

    for field in ("agent_name", "task_id", "role", "issued_at", "expiry"):
        if presented.get(field) != canonical.get(field):
            raise TrustError(
                f"TAMPERED TOKEN: presented {field}={presented.get(field)!r} does not "
                f"match the signed set's {field}={canonical.get(field)!r} for this "
                "nonce. The signature covers the whole epic file; a presented token that "
                "diverges from it was altered after minting.")

    # Option 6a (ruling 2026-10-21): "From that moment every token for that name is
    # refused, expired or not." Checked BEFORE the expiry check below so a revoked name
    # is always refused as REVOKED, never incidentally masked by an expiry message --
    # and checked regardless of whether the token has expired, which is the whole point.
    # revoke.py is imported locally: it has no reason to be on this module's import
    # path for callers who never revoke anything, and it keeps this file's shared
    # import block untouched while T-454 wires this same module elsewhere.
    import revoke as rv
    revoked = rv.is_revoked(root, canonical["agent_name"])
    if revoked is not None:
        reason_suffix = f" reason={revoked['reason']!r}" if revoked.get("reason") else ""
        raise TrustError(
            f"REVOKED NAME: {canonical['agent_name']} was revoked by operator order "
            f"({revoked['revocation_id']}, {revoked['issued_at']}); every token for "
            "this name is refused from that moment, expired or not (ruling "
            f"2026-10-21, option 6a).{reason_suffix}")

    expired = hc.now_iso() > canonical["expiry"]
    if expired:
        raise TrustError(f"token expired at {canonical['expiry']} "
                         f"(agent_name={canonical['agent_name']}, "
                         f"task_id={canonical['task_id']}, role={canonical['role']})")

    if claim_agent is not None or claim_task is not None or claim_role is not None:
        claimed = (claim_agent, claim_task, claim_role)
        actual = (canonical["agent_name"], canonical["task_id"], canonical["role"])
        if claimed != actual:
            raise TrustError(
                f"IDENTITY MISMATCH: this token authorizes {actual}, not {claimed}. A "
                "token minted for one (agent, task, role) does not authorize any other, "
                "even presented with an otherwise-genuine, unexpired signature.")

    return {"token_set_id": dtid, "signed_by": v["signed_by"], "expired": False,
            "agent_name": canonical["agent_name"], "task_id": canonical["task_id"],
            "role": canonical["role"], "issued_at": canonical["issued_at"],
            "expiry": canonical["expiry"]}


# ----------------------------------------------------------------------------- cli

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="dispatch_token.py - operator-signed, epic-grain dispatch tokens "
                    "(T-432 option 5). Mints nothing, signs nothing: it can only draft "
                    "an unsigned set and verify what the operator signed.")
    ap.add_argument("--root", help="harness root (else WARRANT_ROOT/ROSTER_ROOT env)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("draft", help="write an UNSIGNED dispatch-token set for one epic")
    d.add_argument("--epic", required=True)
    d.add_argument("--dispatch", action="append", default=[],
                   metavar="AGENT:TASK:ROLE[:TTL_SECONDS]", help="repeatable")
    d.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS,
                   help=f"default per-token TTL if not overridden in --dispatch "
                        f"(default {DEFAULT_TTL_SECONDS})")
    d.add_argument("--required", action="store_true", default=False,
                   help="T-454: once this set is SIGNED, claim/lock-acquire for this "
                        "epic refuse without a verifying token. Omit for an ordinary, "
                        "non-mandatory set.")

    v = sub.add_parser("verify", help="verify one presented token against the signed set")
    v.add_argument("--token-file", required=True,
                   help="path to a JSON file holding the presented token's fields "
                        "(token_set_id, nonce, agent_name, task_id, role, issued_at, "
                        "expiry)")
    v.add_argument("--claim-agent", help="refuse unless the token actually names this agent")
    v.add_argument("--claim-task", help="refuse unless the token actually names this task")
    v.add_argument("--claim-role", help="refuse unless the token actually names this role")

    args = ap.parse_args(argv)
    root = resolve_root(args.root)
    try:
        if args.cmd == "draft":
            out = draft(root, args.epic, args.dispatch, args.ttl_seconds, args.required)
            print(json.dumps(out, indent=2, ensure_ascii=False))
        elif args.cmd == "verify":
            presented = json.loads(
                pathlib.Path(args.token_file).read_text(encoding="utf-8"))
            out = verify(root, presented, args.claim_agent, args.claim_task,
                        args.claim_role)
            print(json.dumps(out, indent=2, ensure_ascii=False))
    except (TrustError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:                      # a detector must never die silently
        print(f"DETECTOR FAILED, treat as unverified: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
