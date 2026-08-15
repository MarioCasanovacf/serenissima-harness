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

THE TRUST ROOT, AND THE ONE THING A HUMAN MUST DO. This paragraph is the second draft;
the first described a closure a blind panel then walked straight through, and the
corrections are load-bearing rather than cosmetic.

No `allowed_signers` file is stored. One is rebuilt in a temp dir at every verification
from `trust/root.pub`, after THREE checks, each of which exists because the panel
defeated the build that lacked it:

  1. root.pub must hold EXACTLY ONE key. The panel appended a second line whose
     principal was also `operator`; `ssh-keygen -lf` reports only the FIRST key, so the
     anchored fingerprint still matched and warrants signed by the attacker verified.
  2. root.pub's fingerprint must equal `trust/root.fingerprint`.
  3. The fingerprint ssh-keygen NAMES as the actual signer must equal the anchor, and a
     verification that names no signer is refused. This check existed but was
     conditional (`if seen and ...`), undocumented, and covered by no test; deleting it
     left all 36 tests passing while a 20-name forged warrant applied cleanly.

WHAT THE ANCHOR STILL CANNOT DO, and the detector that answers it. Any agent can move
`trust/root.pub` aside, mint freely through roster.py, and move it back; D-17 says so and
no in-process check can prevent it. `reconcile` is the answer: every colegiado, plaza and
name on the roll must trace to a VERIFIED warrant, or it is reported as an orphan, and
`audit` now runs it and raises an ALARM. The panel ran the un-enroll/mint/re-enroll
sequence against the previous build and `audit` called it clean, because audit verified
warrants and never looked at the roll.

The irreducible human step remains one fingerprint, verified OUT OF BAND. That string is
the entire external trust root and there is no cheaper way to buy one.

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
              "draft", "verify_warrant", "apply_warrant", "audit", "payload_digest",
              "authorizes", "reconcile", "enrolled_keys")


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
    lines = [ln for ln in pub.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) != 1:
        raise TrustError(
            f"TRUST ROOT TAMPERED: trust/root.pub holds {len(lines)} keys, not 1. "
            "A blind panel appended a second line whose principal was also `operator`, "
            "left the anchor's fingerprint untouched (ssh-keygen -lf reports the FIRST "
            "key) and had its own warrants verify. One anchor, one key, or nothing.")
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
    # Guard on EITHER file. A panel renamed root.fingerprint aside, re-ran init, and
    # re-anchored the harness to its own key while is_enrolled() still said True,
    # because the two functions guarded different files.
    if (td / "root.fingerprint").exists() or (td / "root.pub").exists():
        prior = None
        if (td / "root.fingerprint").exists():
            prior = (td / "root.fingerprint").read_text(encoding="utf-8").strip()
        elif (td / "root.pub").exists():
            prior = key_fingerprint(td / "root.pub")
        if prior != fp:
            raise TrustError(
                f"ALREADY ENROLLED to {prior}. Re-anchoring to {fp} would silently "
                "replace the trust root, which is how an attacker becomes the operator. "
                "If this is deliberate, remove trust/ by hand after verifying the new "
                "fingerprint out of band, and re-apply every warrant.")
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
    if not seen:
        raise TrustError(
            "ssh-keygen reported success without naming a signing key; refusing rather "
            f"than assuming it was the anchored root. stdout={r.stdout!r}")
    if seen.group(0) != fp:
        raise TrustError(
            f"SIGNED BY THE WRONG KEY: {seen.group(0)} is not the anchored root {fp}. "
            "This is the append-a-second-operator-line attack; see check_anchor.")
    return seen.group(0)


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
        "sign_with": (f"ssh-keygen -Y sign -f ~/.ssh/harness_root.pub -U "
                      f"-n {NAMESPACE} {path}"),
        "WHY_-U_AND_.pub": (
            "-U signs THROUGH ssh-agent using only the public key, so `ssh-add -c` "
            "confirm-on-use actually applies. Pointing -f at the PRIVATE key file "
            "instead reads it directly and bypasses the agent entirely, which makes "
            "confirm-on-use decorative. An earlier version of this string got that "
            "wrong."),
        "then": f"python3 .harness/bin/warrant.py apply --warrant {wid}",
        "note": "This process cannot sign. Run the command above; ssh-agent will ask "
                "you to confirm (ssh-add -c).",
    }



# ------------------------------------------------------- authorization and reconcile

def _norm(token):
    """Same canonical form roster.norm applies, so a warrant written with `Judge`
    authorizes a roll row normalised to `judge`."""
    return " ".join(str(token).split()).casefold()


def authorizes(payload, verb, subject) -> bool:
    """Does this warrant's CONTENT authorize this specific mutation?

    A verified signature says the operator signed SOMETHING. It does not say the
    operator signed THIS -- and "this" means the VALUES too, not only the keys. A second
    panel signed `banco/judge=2` and wrote 64; signed aurelia into `corte/judge` and
    seated her in `banco/notary`; signed one incentive and rewrote it afterwards. All
    three reconciled clean, because this function compared names and ignored numbers. The previous build conflated the two: any string beginning
    `warrant:` passed, so a panel typed `warrant:ME-LO-INVENTE` and minted five names
    against a harness with a genuine enrolled root. A signed document authorizes what it
    says and nothing else.
    """
    if subject is None:
        return False
    subject = _norm(subject)
    epic = _norm(payload.get("epic", ""))
    if verb == "charter":
        colegiado, _, incentive = subject.partition("|")
        signed = {_norm(c): _norm(v) for c, v in payload.get("colegiados", {}).items()}
        return colegiado in signed and signed[colegiado] == incentive
    if verb == "plazas":
        want_epic, _, rest = subject.partition("|")
        key, _, count = rest.rpartition("=")
        signed = {_norm(k): str(v) for k, v in payload.get("plazas", {}).items()}
        return want_epic == epic and key in signed and signed[key] == count
    if verb == "issue":
        want_epic, _, rest = subject.partition("|")
        name, _, seat = rest.partition("@")
        signed = {_norm(n["name"]): f"{_norm(n['colegiado'])}/{_norm(n['role'])}"
                  for n in payload.get("names", [])}
        return want_epic == epic and name in signed and signed[name] == seat
    return False


def reconcile(root) -> dict:
    """Can EVERY row on the roll be traced to a verified warrant? Reports, never repairs.

    This is the detector for the attacks no in-process check can stop (D-17): an agent
    that moves `trust/root.pub` aside, mints freely and moves it back; an agent that
    edits `roster.json` directly; an agent that rewrites roster.py. None of those is
    prevented. All of them leave a row the warrants cannot explain, and this finds it.

    A blind panel ran exactly the un-enroll/mint/re-enroll sequence and `audit` reported
    everything clean, because audit only verified warrants and never looked at the roll.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import roster

    out = {"enrolled": is_enrolled(root), "orphans": [], "checked": 0,
           "warrants_verified": [], "warrants_invalid": []}
    if not out["enrolled"]:
        out["note"] = "un-enrolled: every row is bookkeeping and nothing is claimed"
        return out

    authorized = {"charter": set(), "plazas": set(), "issue": set()}
    wd = warrants_dir(root)
    for path in sorted(wd.glob("W-*.json")) if wd.exists() else []:
        try:
            payload = verify_warrant(root, path.stem)["payload"]
        except TrustError as exc:
            out["warrants_invalid"].append({"id": path.stem, "reason": str(exc)})
            continue
        out["warrants_verified"].append(path.stem)
        epic = _norm(payload.get("epic", ""))
        for c in payload.get("colegiados", {}):
            authorized["charter"].add(_norm(c))
        for k in payload.get("plazas", {}):
            authorized["plazas"].add(f"{epic}|{_norm(k)}")
        for n in payload.get("names", []):
            authorized["issue"].add(f"{epic}|{_norm(n['name'])}")

    data = roster.load(root)
    raw = pathlib.Path(root) / "roster.json"
    if raw.exists():
        try:
            json.loads(raw.read_text(encoding="utf-8"))
        except Exception as exc:
            out["orphans"].append({"kind": "roll", "id": "roster.json",
                                   "reason": f"unreadable: {exc}"})
            out["clean"] = False
            return out
    for key in ("colegiados", "plazas", "names"):
        if not isinstance(data.get(key, {}), dict):
            out["orphans"].append({"kind": "roll", "id": key,
                                   "reason": f"malformed: {type(data[key]).__name__}, "
                                             "expected object"})
            out["clean"] = False
            return out
    for c in data.get("colegiados", {}):
        out["checked"] += 1
        if _norm(c) not in authorized["charter"]:
            out["orphans"].append({"kind": "colegiado", "id": c,
                                   "reason": "no verified warrant charters it"})
    for epic, bucket in data.get("plazas", {}).items():
        for key in bucket:
            out["checked"] += 1
            if f"{_norm(epic)}|{_norm(key)}" not in authorized["plazas"]:
                out["orphans"].append({"kind": "plaza", "id": f"{epic}/{key}",
                                       "reason": "no verified warrant publishes it"})
    for name, entry in data.get("names", {}).items():
        out["checked"] += 1
        if f"{_norm(entry.get('epic',''))}|{_norm(name)}" not in authorized["issue"]:
            out["orphans"].append({"kind": "name", "id": name,
                                   "issued_by": entry.get("issued_by"),
                                   "reason": "no verified warrant issues it"})
    out["clean"] = not out["orphans"] and not out["warrants_invalid"]
    return out


# --------------------------------------------------------------------------- apply

WID_RE = re.compile(r"^W-\d{3,}$")


def check_wid(wid) -> str:
    """A warrant id is a filename, never a path. `warrant:../stash/W-001` used to
    verify a warrant stored outside warrants/, so authorization and reconciliation read
    different sets of documents."""
    wid = str(wid).strip()
    if not WID_RE.match(wid):
        raise TrustError(f"malformed warrant id {wid!r}; expected W-NNN")
    return wid


def load_payload(root, wid) -> dict:
    path = warrants_dir(root) / f"{wid}.json"
    if not path.exists():
        raise TrustError(f"no warrant {wid}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_warrant(root, wid) -> dict:
    wid = check_wid(wid)
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

    _emit(root, "warrant_applied", warrant=wid, epic=p["epic"],
          names=len(applied["names"]), signed_by=v["signed_by"])
    return {"warrant_id": wid, "signed_by": v["signed_by"], **applied}


def enrolled_keys(root) -> dict:
    """Every issued name's PUBLIC key, DERIVED on read from the verified warrants.

    This used to be a cache file, `trust/agent_keys.json`, which attest.sign_act trusted
    and `reconcile` never read. A panel appended one entry by hand and its sybil signed
    acts while reconcile reported clean -- a second registry, unreconciled, behind the
    module whose whole job is evidence. There is no cache now: the warrants ARE the
    registry, following PR-010's computed-on-read doctrine, so there is nothing to
    forge that is not already a forged signature.

    Keys still prove nothing about possession (D-17): any agent reads any private half.
    They are here so a forged act is DETECTABLE, not prevented.
    """
    out = {}
    wd = warrants_dir(root)
    for path in sorted(wd.glob("W-*.json")) if wd.exists() else []:
        try:
            v = verify_warrant(root, path.stem)
        except TrustError:
            continue
        if v["expired"]:
            continue
        p = v["payload"]
        for entry in p["names"]:
            out[_norm(entry["name"])] = {
                "pubkey": entry["pubkey"], "warrant": p["warrant_id"],
                "epic": p["epic"], "colegiado": entry["colegiado"],
                "role": entry["role"],
            }
    return out


class _NullGuard:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --------------------------------------------------------------------------- audit

def audit(root, expect=None) -> dict:
    """Verify every warrant on disk and reconcile the roll. Reports, never repairs.

    `expect` is the fingerprint the OPERATOR holds, out of band. Without it this
    function cannot tell a genuine anchor from one an attacker rewrote: a panel replaced
    both files in `trust/` with its own key, minted three names and got a clean audit,
    because every check inside this module is consistent with whatever `trust/` says.
    `trust/` is writable by every agent and is not tracked by git. THE ANCHOR IS
    SELF-REFERENTIAL UNLESS A HUMAN SUPPLIES THE FINGERPRINT, so without `expect` this
    report is explicitly marked unverified rather than clean.
    """
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
    rec = reconcile(root)
    out["roll_orphans"] = rec["orphans"]
    out["roll_clean"] = rec.get("clean", False)
    if rec["orphans"]:
        out["ALARM"] = (f"{len(rec['orphans'])} row(s) on the roll trace to no verified "
                        "warrant. Something wrote the roll outside the gate.")
    if expect:
        expect = str(expect).strip()
        out["anchor_matches_operator"] = (expect == out["anchor"])
        if not out["anchor_matches_operator"]:
            out["ALARM"] = (f"TRUST ROOT REPLACED: this harness is anchored to "
                            f"{out['anchor']}, the operator expects {expect}. Every "
                            "warrant below verifies against the WRONG key. Treat the "
                            "whole roll as forged.")
    else:
        out["anchor_matches_operator"] = None
        out["UNVERIFIED"] = (
            "No --expect fingerprint supplied, so this report cannot distinguish the "
            "operator's anchor from one an attacker wrote. trust/ is writable by every "
            "agent and untracked by git. Re-run with --expect SHA256:... to make this "
            "an audit rather than a self-consistency check.")
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

    au = sub.add_parser("audit", help="verify every warrant AND reconcile the roll")
    au.add_argument("--expect", help="the fingerprint YOU hold, out of band; "
                                     "without it this is only a self-consistency check")
    sub.add_parser("reconcile", help="can every roll row be traced to a warrant?")
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
            out = audit(root, args.expect)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            if out.get("ALARM"):
                return 3
        elif args.cmd == "reconcile":
            out = reconcile(root)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            if out.get("orphans"):
                return 3
        elif args.cmd == "anchor":
            print(check_anchor(root))
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
