#!/usr/bin/env python3
"""warrant.py - the identity gate PR-023 asks for, supplied rather than argued.

POSTURE (operator decision D-16). PR-023 clause 1 states a PREREQUISITE, not a
prohibition: Phase B is gated on cryptographic identity with an external trust root. A
gate opens when its condition is met. This module supplies the condition. Nothing is
appealed, narrowed or amended; `scope_conditions` stay immutable per SDR-01 and PR-007,
and the coordinator ends in compliance with PR-023 rather than in opposition to it.

Clause 2 places the prerequisite in the Westphalian layer. The OPERATOR is that layer.
The harness does not grant itself the key. It receives one, and this file is written so
that it is mechanically incapable of minting the key it depends on: `draft` produces an
UNSIGNED payload and prints the command the operator runs. No code path here can sign a
warrant. That is the point, and `test_warrant.py` asserts it.

THE ARCHITECTURAL LAW (D-17). Every agent runs as the same OS user on the same
filesystem, so no agent can hold a secret another agent cannot read, and therefore no
agent can have an unforgeable identity. This, not the absence of a crypto library, is
what PR-023 meant by structurally impossible. It follows that:

    the only unstealable key in this system is the operator's, so the unforgeable
    boundary goes exactly at MINTING and nowhere else

A name exists only inside a root-signed warrant. Sybil minting is closed -- an agent may
generate a thousand keypairs and enroll none. Everything downstream of minting is
forgeable-but-detectable, which `attest.py` handles. PR-022 clause 5's verbatim caveat
("identities are self-asserted") stays TRUE for impersonation and stays unmodified.

THE TRUST ROOT, AND THE ONE THING A HUMAN MUST DO. A probe of `ssh-keygen -Y verify`
found the real hole: an attacker who can append to an `allowed_signers` file enrolls
itself and its signature verifies cleanly. So this module keeps NO allowed_signers file.
It rebuilds one in a temp dir at every verification, from `trust/root.pub`, and only
after checking that root.pub's fingerprint equals the string anchored in
`trust/root.fingerprint`. An attacker who swaps root.pub breaks the anchor. An attacker
who swaps both has changed the one string the operator verifies OUT OF BAND. That string
is the entire external trust root, and there is no cheaper way to buy one.

INERT ON PURPOSE (D-21). Nothing here varies a burden, a weight, a quorum or a
permission. PR-022 clause 4 ("NO CONSEQUENCE ATTACHES. NONE") holds, and PR-017 requires
the amending record BEFORE anything keys a consequence to a warrant. This module writes
the roll and nothing else. That discipline is exactly what failed in roster.py, where a
docstring claimed constitutional work the code had not earned.

BACKWARD COMPATIBLE BY CONSTRUCTION. Until `trust/root.pub` exists, the harness is
un-enrolled and roster.py behaves as the accident-only bookkeeping roll it has always
been. Once the root is enrolled, roster.py refuses every unwarranted mutation. There is
no flag day and no migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness_common as hc  # noqa: E402

DEFAULT_ROOT = hc.HARNESS
NAMESPACE = "harness-warrant"          # ssh signature namespace; never reused elsewhere
SCHEMA_VERSION = 1
MAX_PLAZA = 64                          # mirrors roster.PLAZA_MAX
FINGERPRINT_RE = re.compile(r"SHA256:[A-Za-z0-9+/=]{43}")

PUBLIC_API = ("resolve_root", "trust_dir", "anchored_fingerprint", "verify_signature",
              "draft", "verify_warrant", "apply_warrant", "audit", "payload_digest")


class TrustError(Exception):
    """Raised when the trust root is absent, tampered with, or unverifiable."""


# ------------------------------------------------------------------ paths and roots

def resolve_root(flag=None) -> pathlib.Path:
    if flag:
        return pathlib.Path(flag).expanduser().resolve()
    env = os.environ.get("WARRANT_ROOT") or os.environ.get("ROSTER_ROOT")
    if env:
        return pathlib.Path(env).expanduser().resolve()
    return DEFAULT_ROOT


def trust_dir(root) -> pathlib.Path:
    return pathlib.Path(root) / "trust"


def warrants_dir(root) -> pathlib.Path:
    return pathlib.Path(root) / "warrants"


def is_enrolled(root) -> bool:
    """True once an operator root key has been enrolled. Until then the harness is
    un-enrolled and roster.py keeps its pre-warrant behaviour."""
    return (trust_dir(root) / "root.pub").exists()


# ---------------------------------------------------------------------- the anchor

def key_fingerprint(pubkey_path) -> str:
    r = subprocess.run(["ssh-keygen", "-lf", str(pubkey_path)],
                       text=True, capture_output=True)
    if r.returncode != 0:
        raise TrustError(f"ssh-keygen could not read {pubkey_path}: {r.stderr.strip()}")
    m = FINGERPRINT_RE.search(r.stdout)
    if not m:
        raise TrustError(f"no SHA256 fingerprint in ssh-keygen output: {r.stdout!r}")
    return m.group(0)


def anchored_fingerprint(root) -> str:
    path = trust_dir(root) / "root.fingerprint"
    if not path.exists():
        raise TrustError(
            "no trust anchor: run `warrant.py init --root-pub <your key.pub>` first")
    return path.read_text(encoding="utf-8").strip()


def check_anchor(root) -> str:
    """Verify trust/root.pub against the anchored fingerprint, and return it.

    This is the check that closes probe attack 7. An attacker who appends its own key to
    a stored allowed_signers file gets a clean verification -- so no allowed_signers file
    is stored. The signing key must be THE anchored key, or nothing verifies.
    """
    pub = trust_dir(root) / "root.pub"
    if not pub.exists():
        raise TrustError("no trust root enrolled; the harness is un-enrolled")
    actual = key_fingerprint(pub)
    expected = anchored_fingerprint(root)
    if actual != expected:
        raise TrustError(
            f"TRUST ROOT TAMPERED: trust/root.pub is {actual} but the anchor says "
            f"{expected}. Do not proceed. Verify the anchor with the operator "
            f"out of band.")
    return actual


def init(root, root_pub_path) -> dict:
    """Enroll the operator's PUBLIC key. Never touches, requests or generates a private
    key: the whole design rests on this process being unable to sign."""
    src = pathlib.Path(root_pub_path).expanduser()
    if not src.exists():
        raise TrustError(f"no such public key: {src}")
    fp = key_fingerprint(src)
    body = src.read_text(encoding="utf-8").strip()
    if "PRIVATE KEY" in body:
        raise TrustError("that is a PRIVATE key. Enroll the .pub file, never the key "
                         "itself; this process must remain unable to sign.")
    td = trust_dir(root)
    td.mkdir(parents=True, exist_ok=True)
    (td / "root.pub").write_text(body + "\n", encoding="utf-8")
    (td / "root.fingerprint").write_text(fp + "\n", encoding="utf-8")
    hc.log_event("warrant_trust_enrolled", fingerprint=fp) if is_live(root) else None
    return {"fingerprint": fp, "trust_dir": str(td),
            "verify_out_of_band": "Verify this fingerprint OUT OF BAND against the "
                                  "operator's own record. It is the entire external "
                                  "trust root; nothing else here substitutes for it."}


def is_live(root) -> bool:
    try:
        return pathlib.Path(root).resolve() == DEFAULT_ROOT.resolve()
    except OSError:
        return False


def _emit(root, kind, **fields) -> None:
    if is_live(root):
        hc.log_event(kind, **fields)
        return
    rec = {"ts": hc.now_iso(), "event": kind, "agent": hc.agent_id()}
    rec.update(fields)
    hc.append_jsonl(pathlib.Path(root) / "events.jsonl", rec)


# ------------------------------------------------------------------- verification

def verify_signature(root, payload_path, sig_path) -> str:
    """Verify `sig_path` over the EXACT bytes of `payload_path` against the anchored
    root. Returns the verified fingerprint. Raises TrustError otherwise.

    The payload is never re-serialised before verification. A signature covers bytes,
    and a JSON round-trip that reorders a key or changes whitespace silently invalidates
    it -- or worse, silently validates a different document than the one that was read.
    """
    fp = check_anchor(root)
    payload_path, sig_path = pathlib.Path(payload_path), pathlib.Path(sig_path)
    if not sig_path.exists():
        raise TrustError(f"warrant is unsigned: {sig_path} does not exist")
    with tempfile.TemporaryDirectory() as tmp:
        allowed = pathlib.Path(tmp) / "allowed_signers"
        pub = (trust_dir(root) / "root.pub").read_text(encoding="utf-8").strip()
        allowed.write_text(f"operator {pub}\n", encoding="utf-8")
        with payload_path.open("rb") as fh:
            r = subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I", "operator",
                 "-n", NAMESPACE, "-s", str(sig_path)],
                stdin=fh, text=True, capture_output=True)
    if r.returncode != 0:
        raise TrustError(f"SIGNATURE DOES NOT VERIFY for {payload_path.name}: "
                         f"{(r.stderr or r.stdout).strip()}")
    seen = FINGERPRINT_RE.search(r.stdout or "")
    if seen and seen.group(0) != fp:
        raise TrustError(f"signed by {seen.group(0)}, which is not the anchored root {fp}")
    return fp


def payload_digest(payload_path) -> str:
    return "sha256:" + hashlib.sha256(
        pathlib.Path(payload_path).read_bytes()).hexdigest()


# ------------------------------------------------------------------------- drafting

def _parse_plaza(spec: str):
    """'banco/judge=3' -> ('banco', 'judge', 3)"""
    if "=" not in spec or "/" not in spec.split("=")[0]:
        raise ValueError(f"plaza must look like colegiado/role=N, got {spec!r}")
    key, _, count = spec.partition("=")
    colegiado, _, role = key.partition("/")
    try:
        n = int(count)
    except ValueError:
        raise ValueError(f"plaza count must be an integer, got {count!r}")
    if not 1 <= n <= MAX_PLAZA:
        raise ValueError(f"plaza count must be between 1 and {MAX_PLAZA}, got {n}")
    return colegiado.strip(), role.strip(), n


def _parse_name(spec: str):
    """'aurelia:banco/judge:/path/to/key.pub[:persona]' -> dict"""
    parts = spec.split(":", 3)
    if len(parts) < 3:
        raise ValueError(
            f"name must look like name:colegiado/role:pubkey[:persona], got {spec!r}")
    name, seat, pubkey = parts[0], parts[1], parts[2]
    persona = parts[3] if len(parts) > 3 else ""
    if "/" not in seat:
        raise ValueError(f"seat must look like colegiado/role, got {seat!r}")
    colegiado, _, role = seat.partition("/")
    pub = pathlib.Path(pubkey).expanduser()
    if not pub.exists():
        raise ValueError(f"no such public key for {name}: {pub}")
    return {"name": name.strip(), "colegiado": colegiado.strip(), "role": role.strip(),
            "pubkey": pub.read_text(encoding="utf-8").strip(), "persona": persona}


def next_warrant_id(root) -> str:
    wd = warrants_dir(root)
    n = 0
    if wd.exists():
        for p in wd.glob("W-*.json"):
            try:
                n = max(n, int(p.stem.split("-")[1]))
            except (IndexError, ValueError):
                continue
    return f"W-{n + 1:03d}"


def draft(root, epic, colegiados, plaza_specs, name_specs, valid_until=None) -> dict:
    """Write an UNSIGNED warrant payload and return the exact command the operator runs.

    This function cannot sign and there is no sibling that can. The separation is the
    mechanism: a process that could produce both the document and its signature would be
    a trust root, and D-17 says no process on this filesystem may be one.
    """
    root = pathlib.Path(root)
    plazas = {}
    for spec in plaza_specs:
        c, r, n = _parse_plaza(spec)
        plazas[f"{c}/{r}"] = n
    names = [_parse_name(s) for s in name_specs]

    seats_needed = {}
    for entry in names:
        seats_needed[f"{entry['colegiado']}/{entry['role']}"] = \
            seats_needed.get(f"{entry['colegiado']}/{entry['role']}", 0) + 1
    for key, needed in seats_needed.items():
        if key not in plazas:
            raise ValueError(f"names claim seat {key}, which the warrant does not publish")
        if needed > plazas[key]:
            raise ValueError(f"{needed} names claim {key}, which publishes {plazas[key]}")

    declared = {c.split("=", 1)[0].strip(): c.split("=", 1)[1].strip()
                for c in colegiados if "=" in c}
    for key in plazas:
        col = key.split("/")[0]
        if col not in declared:
            raise ValueError(f"plaza {key} names colegiado {col!r}, which the warrant "
                             "does not charter; add --colegiado {col}=<incentive>")

    wid = next_warrant_id(root)
    payload = {
        "warrant_id": wid,
        "schema_version": SCHEMA_VERSION,
        "epic": epic,
        "issued_at": hc.now_iso(),
        "valid_until": valid_until,
        "colegiados": declared,
        "plazas": plazas,
        "names": names,
        "namespace": NAMESPACE,
        "NOT_A_CONSEQUENCE": "PR-022 clause 4 holds: this warrant confers a seat and a "
                             "name, never a weight, a burden, a quorum or a permission",
    }
    wd = warrants_dir(root)
    wd.mkdir(parents=True, exist_ok=True)
    path = wd / f"{wid}.json"
    # written once, verbatim, and never re-serialised: the signature covers these bytes
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    _emit(root, "warrant_drafted", warrant=wid, epic=epic,
          plazas=sum(plazas.values()), names=len(names))
    return {
        "warrant_id": wid,
        "path": str(path),
        "digest": payload_digest(path),
        "sign_with": f"ssh-keygen -Y sign -f ~/.ssh/harness_root -n {NAMESPACE} {path}",
        "then": f"python3 .harness/bin/warrant.py apply --warrant {wid}",
        "note": "This process cannot sign. Run the command above; ssh-agent will ask "
                "you to confirm (ssh-add -c).",
    }


# --------------------------------------------------------------------------- apply

def load_payload(root, wid) -> dict:
    path = warrants_dir(root) / f"{wid}.json"
    if not path.exists():
        raise TrustError(f"no warrant {wid}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_warrant(root, wid) -> dict:
    path = warrants_dir(root) / f"{wid}.json"
    fp = verify_signature(root, path, path.with_suffix(".json.sig"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("namespace") != NAMESPACE:
        raise TrustError(f"{wid} declares namespace {payload.get('namespace')!r}; "
                         f"signatures are only accepted in {NAMESPACE!r}")
    expired = False
    if payload.get("valid_until"):
        expired = hc.now_iso() > payload["valid_until"]
    return {"warrant_id": wid, "signed_by": fp, "digest": payload_digest(path),
            "expired": expired, "payload": payload}


def apply_warrant(root, wid) -> dict:
    """Verify, then write the warrant's contents into the roll via roster.py.

    roster.py keeps its own guards and refusals; this adds authority on top of them
    rather than replacing them, so a warrant cannot over-fill a plaza or reuse a name
    either.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import roster  # local import: roster imports nothing from here, no cycle

    v = verify_warrant(root, wid)
    if v["expired"]:
        raise TrustError(f"{wid} expired at {v['payload']['valid_until']}")
    p = v["payload"]
    by = f"warrant:{wid}"
    applied = {"colegiados": [], "plazas": [], "names": [], "already": []}

    for colegiado, incentive in p["colegiados"].items():
        try:
            roster.charter(colegiado, incentive, by, root)
            applied["colegiados"].append(colegiado)
        except KeyError as exc:
            applied["already"].append(f"charter {colegiado}: {exc}")
    for key, count in p["plazas"].items():
        colegiado, _, role = key.partition("/")
        try:
            roster.plazas(p["epic"], colegiado, role, count, by, root)
            applied["plazas"].append(f"{key}={count}")
        except KeyError as exc:
            applied["already"].append(f"plazas {key}: {exc}")
    for entry in p["names"]:
        try:
            roster.issue(entry["name"], entry["colegiado"], entry["role"], p["epic"],
                         by, entry.get("persona", ""), root)
            applied["names"].append(entry["name"])
        except KeyError as exc:
            applied["already"].append(f"issue {entry['name']}: {exc}")

    _register_keys(root, p)
    _emit(root, "warrant_applied", warrant=wid, epic=p["epic"],
          names=len(applied["names"]), signed_by=v["signed_by"])
    return {"warrant_id": wid, "signed_by": v["signed_by"], **applied}


def _register_keys(root, payload) -> None:
    """Record each issued name's PUBLIC key so attest.py can verify that name's acts.

    These keys live on the shared filesystem and any agent can read the private halves
    wherever they are kept, so possession proves nothing (D-17). They are here so a
    forged act is DETECTABLE, not prevented -- see attest.py and DIS-1.
    """
    path = trust_dir(root) / "agent_keys.json"
    with hc.guarded() if is_live(root) else _NullGuard():
        data = hc.read_json(path, default={}) or {}
        for entry in payload["names"]:
            data[entry["name"]] = {
                "pubkey": entry["pubkey"],
                "warrant": payload["warrant_id"],
                "epic": payload["epic"],
                "colegiado": entry["colegiado"],
                "role": entry["role"],
            }
        hc.atomic_write_json(path, data)


class _NullGuard:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --------------------------------------------------------------------------- audit

def audit(root) -> dict:
    """Verify every warrant on disk. Reports, never repairs."""
    out = {"enrolled": is_enrolled(root), "anchor": None, "warrants": [],
           "unsigned": [], "invalid": [], "ok": 0}
    if not out["enrolled"]:
        out["note"] = ("un-enrolled: the harness has no trust root, so roster.py is "
                       "bookkeeping only and PR-023's gate remains closed")
        return out
    out["anchor"] = check_anchor(root)
    wd = warrants_dir(root)
    for path in sorted(wd.glob("W-*.json")) if wd.exists() else []:
        wid = path.stem
        try:
            v = verify_warrant(root, wid)
            out["warrants"].append({"id": wid, "epic": v["payload"]["epic"],
                                    "expired": v["expired"], "digest": v["digest"]})
            out["ok"] += 1
        except TrustError as exc:
            (out["unsigned"] if "unsigned" in str(exc) else out["invalid"]).append(
                {"id": wid, "reason": str(exc)})
    return out


# ----------------------------------------------------------------------------- cli

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="warrant.py - operator-signed warrants. Mints nothing, signs "
                    "nothing: it can only verify and apply what the operator signed.")
    ap.add_argument("--root", help="harness root (else WARRANT_ROOT/ROSTER_ROOT env)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="enroll the operator's PUBLIC key as the trust root")
    i.add_argument("--root-pub", required=True, help="path to the .pub file")

    d = sub.add_parser("draft", help="write an UNSIGNED warrant for the operator to sign")
    d.add_argument("--epic", required=True)
    d.add_argument("--colegiado", action="append", default=[],
                   metavar="NAME=INCENTIVE", help="repeatable")
    d.add_argument("--plaza", action="append", default=[],
                   metavar="COLEGIADO/ROLE=N", help="repeatable")
    d.add_argument("--name", action="append", default=[],
                   metavar="NAME:COLEGIADO/ROLE:PUBKEY[:PERSONA]", help="repeatable")
    d.add_argument("--valid-until", help="ISO timestamp; bounds a stolen key's blast "
                                         "radius (D-20 DIS-4)")

    v = sub.add_parser("verify", help="verify one warrant's signature against the anchor")
    v.add_argument("--warrant", required=True)

    a = sub.add_parser("apply", help="verify then write the warrant into the roll")
    a.add_argument("--warrant", required=True)

    sub.add_parser("audit", help="verify every warrant; report, never repair")
    sub.add_parser("anchor", help="print the fingerprint to verify out of band")

    args = ap.parse_args(argv)
    root = resolve_root(args.root)
    try:
        if args.cmd == "init":
            out = init(root, args.root_pub)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            print("\nVERIFY THIS FINGERPRINT OUT OF BAND. It is the whole trust root:")
            print(f"  {out['fingerprint']}")
        elif args.cmd == "draft":
            out = draft(root, args.epic, args.colegiado, args.plaza, args.name,
                        args.valid_until)
            print(json.dumps(out, indent=2, ensure_ascii=False))
        elif args.cmd == "verify":
            out = verify_warrant(root, args.warrant)
            out.pop("payload", None)
            print(json.dumps(out, indent=2, ensure_ascii=False))
        elif args.cmd == "apply":
            print(json.dumps(apply_warrant(root, args.warrant), indent=2,
                             ensure_ascii=False))
        elif args.cmd == "audit":
            print(json.dumps(audit(root), indent=2, ensure_ascii=False))
        elif args.cmd == "anchor":
            print(check_anchor(root))
    except (TrustError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
