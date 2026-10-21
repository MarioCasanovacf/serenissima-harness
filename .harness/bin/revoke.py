#!/usr/bin/env python3
"""revoke.py - option 6a of T-432's identity design, ratified 2026-10-21: revoke a name
by operator order.

RATIFIED TEXT (operator-rulings-2026-10-21.md, Decision 1, option 6a). "A verb that
revokes a name by operator order. A revocation is an operator-signed record, never an
agent act, so no agent can revoke another. From that moment every token for that name is
refused, expired or not."

SPLIT, MIRRORING warrant.py's draft/apply ON PURPOSE. A revocation is a consequence-
shaped action -- it takes a name's standing away -- so it gets the identical discipline
D-16/D-17 already enforce for warrants and dispatch tokens:

  - `draft` is a verb ANY agent may run. It writes an UNSIGNED revocation payload to disk
    and prints the exact `ssh-keygen -Y sign` command the OPERATOR runs, in this module's
    own signature namespace. No function in this module invokes `ssh-keygen -Y sign`;
    `test_revoke.py` asserts that, the same shape as `test_warrant.py`'s
    `TheHarnessCannotSign` and `test_dispatch_token.py`'s `TheModuleCannotSign`.
  - `apply` (and the read-path `revoked_names`/`is_revoked`) accept a revocation only if
    it verifies against the ENROLLED root (`trust/root.pub`, checked against
    `trust/root.fingerprint`, the same anchor warrant.py and dispatch_token.py already
    share) -- NEVER against a key the revocation file names about itself. That is the
    exact property `test_dispatch_token.py`'s
    `test_a_payload_that_names_its_own_signer_as_trusted_is_still_refused` pins for
    dispatch tokens, and this module reuses the identical signature-verification shape
    (`_verify_file_signature` below), not a shortcut version of it.

WHY A SEPARATE NAMESPACE, AND WHY NOT `trust/`. `harness-revocation` is distinct from
`warrant.NAMESPACE` ("harness-warrant"), `dispatch_token.NAMESPACE`
("harness-dispatch-token") and `attest.NAMESPACE` ("harness-act"), so a signature minted
for one surface can never be replayed as proof for another -- the same discipline
dispatch_token.py's own docstring states for itself. Revocations are stored under
`<root>/revocations/`, OUTSIDE `.harness/trust`: `trust/` holds the one thing every other
surface in this harness anchors against (the operator's public key and its fingerprint),
and a revocation is downstream of that anchor, not part of it. Keeping it in its own
directory also means nothing here can be confused with, or accidentally overwrite,
anything `warrant.py init`/`audit` reasons about.

COMPUTED ON READ, NO CACHE (PR-010, the same doctrine `warrant.enrolled_keys` already
states for itself). `revoked_names()` re-verifies every revocation file's signature
against the live anchor on every call rather than trusting a prior "this one was already
checked" marker. There is deliberately no second registry that could drift from the
signed files themselves -- precisely the shape of defect `warrant.py`'s own docstring
names for a cached `trust/agent_keys.json` that a panel defeated by appending one entry by
hand.

WHAT THIS DOES NOT DO (PR-022 clause 4, restated because a revocation is the one act in
this family that could plausibly be mistaken for a consequence). A revocation attaches NO
weight, burden, quorum or permission by itself. Its entire, sole effect is that
`dispatch_token.verify` refuses tokens naming a revoked agent, and `roster.py` reports
the name as revoked. Nothing is deleted, no warrant is voided, no plaza is freed, no
roll row is rewritten. It is a refusal at the presentation-time check, not a retroactive
rewrite of history (the revoked name's past acts and past verified tokens are untouched;
only a FUTURE presentation of a token naming it is refused).

THIS PROCESS CANNOT SIGN (D-16). Same discipline as warrant.py and dispatch_token.py:
`draft` writes an UNSIGNED payload and prints the exact command the operator runs. No
function in this module invokes `ssh-keygen -Y sign`; `test_revoke.py` asserts it.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness_common as hc  # noqa: E402
import warrant as w  # noqa: E402 -- local import, reuses the one operator trust anchor

NAMESPACE = "harness-revocation"   # distinct from warrant.NAMESPACE, dispatch_token.NAMESPACE, attest.NAMESPACE
SCHEMA_VERSION = 1

PUBLIC_API = ("resolve_root", "revocations_dir", "draft", "verify_revocation", "apply",
              "revoked_names", "is_revoked")

TrustError = w.TrustError           # same exception family as warrant.py/dispatch_token.py


class UnsignedRevocation(TrustError):
    """A revocation payload exists and carries NO signature file yet.

    A subclass, not a bare TrustError, for the same reason warrant.py's UnsignedWarrant
    and dispatch_token.py's UnsignedTokenSet are: a caller that only cares "is this
    revocation in force" keeps working unchanged (UnsignedRevocation IS a TrustError),
    while a caller that wants to tell "awaiting the operator" apart from "signature
    exists and fails" can catch this subclass instead.
    """


# ------------------------------------------------------------------ paths and roots

def resolve_root(flag=None) -> pathlib.Path:
    return w.resolve_root(flag)


def revocations_dir(root) -> pathlib.Path:
    return pathlib.Path(root) / "revocations"


RID_RE = re.compile(r"^REV-\d{3,}$")


def check_rid(rid) -> str:
    """A revocation id is a filename, never a path -- same discipline as warrant.py's
    check_wid and dispatch_token.py's check_dtid, and for the identical reason:
    `rid:../stash/REV-001` must not let drafting and verification read different
    documents."""
    rid = str(rid).strip()
    if not RID_RE.match(rid):
        raise TrustError(f"malformed revocation id {rid!r}; expected REV-NNN")
    return rid


def next_revocation_id(root) -> str:
    rd = revocations_dir(root)
    n = 0
    if rd.exists():
        for p in rd.glob("REV-*.json"):
            try:
                n = max(n, int(p.stem.split("-")[1]))
            except (IndexError, ValueError):
                continue
    return f"REV-{n + 1:03d}"


def _norm(name: str) -> str:
    """Same canonical form roster.norm applies, so a revocation written for `Worker-A`
    refuses tokens issued to `worker-a`."""
    return " ".join(str(name).split()).casefold()


# -------------------------------------------------------------------------- drafting

def draft(root, name, reason="") -> dict:
    """Write an UNSIGNED revocation payload for one name and return the exact command the
    operator runs. ANY agent may call this -- drafting commits nothing and authorizes
    nothing by itself; only the operator's signature does. No sibling function in this
    module can sign; see the module docstring.
    """
    root = pathlib.Path(root)
    name = str(name).strip()
    if not name:
        raise ValueError("revoke draft needs a non-empty name")
    rid = next_revocation_id(root)
    payload = {
        "revocation_id": rid,
        "schema_version": SCHEMA_VERSION,
        "name": _norm(name),
        "reason": str(reason).strip(),
        "issued_at": hc.now_iso(),
        "namespace": NAMESPACE,
        "NOT_A_CONSEQUENCE": "PR-022 clause 4 holds: this revocation only refuses a "
                             "future dispatch_token.verify presenting this name. It "
                             "voids no warrant, frees no plaza, and rewrites no past "
                             "act or past verified token.",
    }
    rd = revocations_dir(root)
    rd.mkdir(parents=True, exist_ok=True)
    path = rd / f"{rid}.json"
    # written once, verbatim, never re-serialised: the signature covers these exact bytes
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    _emit(root, "revocation_drafted", revocation=rid, name=payload["name"])
    return {
        "revocation_id": rid,
        "path": str(path),
        "digest": w.payload_digest(path),
        "sign_with": (f"{w.SIGN_ENV}ssh-keygen -Y sign -f {w.ROOT_KEY} "
                      f"-n {NAMESPACE} {path}"),
        "WHY_EVERY_PART_OF_THAT_COMMAND": w.SIGN_RATIONALE,
        "then": f"python3 .harness/bin/revoke.py apply --revocation {rid}",
        "note": "This process cannot sign. Run the command above; it will ask for the "
                "key's passphrase on the terminal. A revocation is an operator-signed "
                "record, never an agent act (ruling 2026-10-21, option 6a): no agent "
                "can revoke another by typing a name here, only by holding the key.",
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
    Deliberately NOT warrant.verify_signature (hardcoded to warrant.NAMESPACE) and NOT
    dispatch_token._verify_file_signature (hardcoded to dispatch_token.NAMESPACE): a
    signature minted under one namespace must never verify under another.

    The signer source is ALWAYS the enrolled `trust/root.pub`, never a key the payload
    names about itself -- there is no field read from `payload_path`'s own JSON before
    this check runs, by construction: this function never parses the payload at all.
    """
    import subprocess
    import tempfile

    fp = w.check_anchor(root)
    payload_path, sig_path = pathlib.Path(payload_path), pathlib.Path(sig_path)
    if not sig_path.exists():
        raise UnsignedRevocation(f"revocation is unsigned: {sig_path} does not exist")
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


def verify_revocation(root, rid) -> dict:
    """Verify one revocation file against the enrolled root. Returns the verified
    payload and signer fingerprint. Raises TrustError (or UnsignedRevocation) otherwise.
    Mirrors warrant.verify_warrant / dispatch_token.verify_token_set in shape.
    """
    rid = check_rid(rid)
    path = revocations_dir(root) / f"{rid}.json"
    if not path.exists():
        raise TrustError(f"no revocation {rid}")
    fp = _verify_file_signature(root, path, path.with_suffix(".json.sig"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("namespace") != NAMESPACE:
        raise TrustError(f"{rid} declares namespace {payload.get('namespace')!r}; "
                         f"revocation signatures are only accepted in {NAMESPACE!r}")
    return {"revocation_id": rid, "signed_by": fp, "digest": w.payload_digest(path),
            "payload": payload}


def apply(root, rid) -> dict:
    """Accept a drafted revocation as effective: verify it against the enrolled root
    and nothing else, never against a key the revocation file names about itself.

    There is no second store to write into. A revocation is effective the moment it
    verifies (PR-010, computed on read, same doctrine as `warrant.enrolled_keys`):
    `revoked_names`/`is_revoked` re-run this identical check on every call, so there is
    no cached "applied" flag that could drift from the signed file on disk. `apply`
    exists as its own verb so a caller gets the same draft -> operator signs -> apply
    shape warrant.py already uses, and so a failed verification is reported here,
    immediately, rather than silently discovered later at a token's presentation time.
    """
    v = verify_revocation(root, rid)
    _emit(root, "revocation_applied", revocation=rid, name=v["payload"]["name"],
          signed_by=v["signed_by"])
    return {"revocation_id": rid, "name": v["payload"]["name"],
            "signed_by": v["signed_by"], "applied": True}


def revoked_names(root) -> dict:
    """Every name under a VERIFIED revocation, derived on read. name (normalised) ->
    {"revocation_id", "reason", "issued_at", "signed_by"}. Unsigned or invalid
    revocation files are silently excluded -- they authorize nothing (same discipline as
    warrant.reconcile's treatment of unsigned/invalid warrants).
    """
    out = {}
    rd = revocations_dir(root)
    for path in sorted(rd.glob("REV-*.json")) if rd.exists() else []:
        try:
            v = verify_revocation(root, path.stem)
        except TrustError:
            continue
        p = v["payload"]
        name = _norm(p["name"])
        # First verified revocation for a name wins; a name revoked twice stays revoked,
        # it does not become "more" or "less" revoked, and PR-022 clause 4 bars this
        # module from treating a second revocation as a heavier consequence.
        if name not in out:
            out[name] = {"revocation_id": p["revocation_id"], "reason": p.get("reason", ""),
                         "issued_at": p["issued_at"], "signed_by": v["signed_by"]}
    return out


def is_revoked(root, name) -> dict | None:
    """None if `name` carries no verified revocation; else the revocation's own record."""
    return revoked_names(root).get(_norm(name))


# ----------------------------------------------------------------------------- cli

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="revoke.py - revoke a name by operator order (T-432 option 6a). "
                    "Mints nothing, signs nothing: it can only draft an unsigned "
                    "revocation and accept what the operator signed.")
    ap.add_argument("--root", help="harness root (else WARRANT_ROOT/ROSTER_ROOT env)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("draft", help="write an UNSIGNED revocation for one name")
    d.add_argument("--name", required=True)
    d.add_argument("--reason", default="")

    a = sub.add_parser("apply", help="accept a revocation iff it verifies against the enrolled root")
    a.add_argument("--revocation", required=True)

    v = sub.add_parser("verify", help="verify one revocation's signature against the anchor")
    v.add_argument("--revocation", required=True)

    sub.add_parser("list", help="list every name currently under a verified revocation")

    c = sub.add_parser("check", help="is this one name currently revoked?")
    c.add_argument("--name", required=True)

    args = ap.parse_args(argv)
    root = resolve_root(args.root)
    try:
        if args.cmd == "draft":
            out = draft(root, args.name, args.reason)
            print(json.dumps(out, indent=2, ensure_ascii=False))
        elif args.cmd == "apply":
            out = apply(root, args.revocation)
            print(json.dumps(out, indent=2, ensure_ascii=False))
        elif args.cmd == "verify":
            out = verify_revocation(root, args.revocation)
            out.pop("payload", None)
            print(json.dumps(out, indent=2, ensure_ascii=False))
        elif args.cmd == "list":
            print(json.dumps(revoked_names(root), indent=2, ensure_ascii=False))
        elif args.cmd == "check":
            rec = is_revoked(root, args.name)
            print(json.dumps({"name": _norm(args.name), "revoked": rec is not None,
                             "revocation": rec}, indent=2, ensure_ascii=False))
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
