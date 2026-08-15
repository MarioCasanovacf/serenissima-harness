#!/usr/bin/env python3
"""attest.py - signed acts, per-name hash chains, and mechanical fork detection.

WHAT THIS CANNOT DO, SAID FIRST. Agent private keys live on the same filesystem every
agent can read (D-17), so an agent CAN sign as another and this module cannot stop it.
Anyone who reads a claim here that it prevents impersonation has found a defect; the
previous generation of this harness shipped exactly that kind of claim in roster.py and
an adversarial panel took it apart. PR-022 clause 5's verbatim caveat, "identities are
self-asserted", remains true at the point of use and remains unmodified.

WHAT IT DOES INSTEAD (operator decision D-20). Prevention is unavailable, so forgery is
made unprofitable, self-evident and adjudicable:

  DIS-1  FORK DETECTION IS MECHANICAL, NOT A JUDGEMENT. Every act by name N embeds the
         hash of N's previous act. Two acts sharing one predecessor is a FORK, and a
         fork is unforgeable proof that two parties held the key. Nobody has to believe
         anybody, and no verifier has to be trusted: `verify` computes it. This is the
         two-claimants detector the refused PR-023 appeal promised in its G2 and never
         built. It is now cryptographic rather than procedural.

  DIS-2  CREDIT FOLLOWS THE SIGNATURE, ALWAYS. Every effect this module reports accrues
         to the SIGNING name. Forging as A therefore credits A. Forgery cannot enrich
         the forger, only damage the victim, which deletes the economic motive and
         leaves only sabotage. This is the cheapest and strongest disincentive here, and
         it costs one design rule rather than one line of code.

  DIS-3  A FORK NEVER FREEZES THE EPIC. Both branches survive, marked CONTESTED, and
         nothing stalls waiting for a re-anchor. AF-5 is explicit that a mechanism must
         not wait on an operator who may be asleep, and a saboteur must not be able to
         halt a rival by forging.

  DIS-4  A CONTESTED ACT CARRIES NO WEIGHT UNTIL ADJUDICATED, INCLUDING THE FORGER'S.
         Sabotage costs the saboteur the act it spent and, by DIS-2, gains it nothing.

  DIS-5  FILING IS ITSELF A SIGNED ACT ON THE ACCUSER'S OWN CHAIN. "Someone forged as
         me" is, from outside, indistinguishable from "I leaked my own key". So a
         contest is not free speech: it is an act, permanently attributable to the name
         that filed it, sitting in that name's chain forever. AF-3 says the delay costs
         the delayer; here the accusation costs the accuser its own evidentiary record,
         with no punitive consequence attached and none needed.

INERT (D-21). Nothing here varies a burden, a weight, a quorum or a permission. PR-022
clause 4 holds: NO CONSEQUENCE ATTACHES. NONE. `verify` reports CONTESTED and stops;
what follows is an agentic court on the record, which is the operator's stated success
condition reached by mechanism rather than by decree. PR-017 requires the amending
record before anything keys a consequence to a chain or a fork.

LAYOUT. `.harness/acts/<name>/NNN.json` plus `NNN.json.sig`, one directory per name, so
a fork is two files in one directory sharing a `prev` -- visible to `ls`, not only to
this tool.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness_common as hc  # noqa: E402
import warrant as w  # noqa: E402

NAMESPACE = "harness-act"      # distinct from warrant.NAMESPACE; a warrant signature
                               # must never verify as an act, or the root could be
                               # replayed into an agent's chain
SCHEMA_VERSION = 1
GENESIS = "genesis"

PUBLIC_API = ("acts_dir", "chain", "sign_act", "verify_name", "verify_all",
              "forks", "contest")


class AttestError(Exception):
    pass


def acts_dir(root, name=None) -> pathlib.Path:
    base = pathlib.Path(root) / "acts"
    return base / name if name else base


def enrolled_keys(root) -> dict:
    return hc.read_json(w.trust_dir(root) / "agent_keys.json", default={}) or {}


def digest(path) -> str:
    return "sha256:" + hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------------- chains

def chain(root, name) -> list:
    """Every act by `name`, in file order. Not necessarily a line: that is the point."""
    d = acts_dir(root, name)
    if not d.exists():
        return []
    out = []
    for path in sorted(d.glob("*.json")):
        try:
            act = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out.append({"_unparseable": str(path)})
            continue
        act["_path"] = str(path)
        act["_digest"] = digest(path)
        act["_signed"] = path.with_suffix(".json.sig").exists()
        out.append(act)
    return out


def head(root, name) -> str:
    """The digest the next act must point at. GENESIS when the chain is empty.

    With a fork present there is no single head, so this returns the LONGEST branch's
    tip and `verify` reports the ambiguity. Refusing to append during a contest would
    freeze the epic, which DIS-3 forbids.
    """
    acts = [a for a in chain(root, name) if "_unparseable" not in a]
    if not acts:
        return GENESIS
    by_prev = collections.defaultdict(list)
    for a in acts:
        by_prev[a.get("prev")].append(a)
    node, seen = GENESIS, set()
    while True:
        nxt = by_prev.get(node)
        if not nxt:
            return node
        chosen = nxt[0]["_digest"]
        if chosen in seen:
            return node
        seen.add(chosen)
        node = chosen


# --------------------------------------------------------------------------- sign

def sign_act(root, name, key_path, kind, ref="", body=None) -> dict:
    """Write an act onto `name`'s chain and sign it with `name`'s key.

    This process signs with a key it can read, which is exactly the limitation D-17
    names. The value is not that the signature is unforgeable -- it is not -- but that
    the act is CHAINED, so a second party signing as `name` produces a fork.
    """
    root = pathlib.Path(root)
    keys = enrolled_keys(root)
    if name not in keys:
        raise AttestError(
            f"{name!r} is not an issued name; a name exists only inside a root-signed "
            f"warrant (warrant.py). This is the one thing that IS closed.")
    key = pathlib.Path(key_path).expanduser()
    if not key.exists():
        raise AttestError(f"no such private key: {key}")

    d = acts_dir(root, name)
    d.mkdir(parents=True, exist_ok=True)
    seq = len(list(d.glob("*.json")))
    act = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "seq": seq,
        "kind": kind,
        "ref": ref,
        "body": body if body is not None else {},
        "prev": head(root, name),
        "ts": hc.now_iso(),
        "namespace": NAMESPACE,
        "CREDIT_FOLLOWS_THE_SIGNATURE": "DIS-2: every effect of this act accrues to "
                                        "the signing name, never to the process",
    }
    path = d / f"{seq:03d}.json"
    path.write_text(json.dumps(act, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    r = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE,
                        str(path)], text=True, capture_output=True)
    if r.returncode != 0:
        path.unlink(missing_ok=True)
        raise AttestError(f"could not sign: {(r.stderr or r.stdout).strip()}")
    _emit(root, "act_signed", name=name, seq=seq, act_kind=kind,
          prev=act["prev"])
    return {"name": name, "seq": seq, "path": str(path), "digest": digest(path),
            "prev": act["prev"]}


def _emit(root, kind, **fields):
    if w.is_live(root):
        hc.log_event(kind, **fields)
        return
    rec = {"ts": hc.now_iso(), "event": kind, "agent": hc.agent_id()}
    rec.update(fields)
    hc.append_jsonl(pathlib.Path(root) / "events.jsonl", rec)


# ------------------------------------------------------------------------- verify

def _verify_sig(root, name, path, pubkey) -> tuple:
    path = pathlib.Path(path)
    sig = path.with_suffix(".json.sig")
    if not sig.exists():
        return False, "unsigned"
    with tempfile.TemporaryDirectory() as tmp:
        allowed = pathlib.Path(tmp) / "allowed_signers"
        allowed.write_text(f"{name} {pubkey}\n", encoding="utf-8")
        with path.open("rb") as fh:
            r = subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I", name,
                 "-n", NAMESPACE, "-s", str(sig)],
                stdin=fh, text=True, capture_output=True)
    return (r.returncode == 0,
            "ok" if r.returncode == 0 else (r.stderr or r.stdout).strip())


def verify_name(root, name) -> dict:
    """Verify every act by `name`, and report forks. Reports; never repairs, never
    refuses, never freezes (DIS-3)."""
    keys = enrolled_keys(root)
    if name not in keys:
        return {"name": name, "enrolled": False,
                "note": "no warrant issued this name; its acts carry no standing"}
    pub = keys[name]["pubkey"]
    acts, bad, by_prev = chain(root, name), [], collections.defaultdict(list)
    for a in acts:
        if "_unparseable" in a:
            bad.append({"path": a["_unparseable"], "reason": "unparseable"})
            continue
        ok, why = _verify_sig(root, name, a["_path"], pub)
        if not ok:
            bad.append({"path": a["_path"], "seq": a.get("seq"), "reason": why})
        by_prev[a.get("prev")].append(a)

    forks_found = []
    for prev, siblings in by_prev.items():
        if len(siblings) > 1:
            forks_found.append({
                "prev": prev,
                "branches": [{"seq": s.get("seq"), "kind": s.get("kind"),
                              "ts": s.get("ts"), "digest": s["_digest"]}
                             for s in siblings],
                "PROOF": "two acts share one predecessor, so two parties held this "
                         "key. DIS-1: mechanical, not a judgement.",
                "STATUS": "CONTESTED",
                "NO_CONSEQUENCE": "DIS-4 and PR-022 clause 4: contested acts carry no "
                                  "weight until adjudicated, including the forger's. "
                                  "Nothing is frozen (DIS-3).",
            })
    return {"name": name, "enrolled": True, "acts": len(acts),
            "signature_failures": bad, "forks": forks_found,
            "contested": bool(forks_found)}


def verify_all(root) -> dict:
    keys = enrolled_keys(root)
    names = sorted(set(keys) | {p.name for p in acts_dir(root).iterdir()
                                if p.is_dir()} if acts_dir(root).exists() else set(keys))
    reports = [verify_name(root, n) for n in names]
    return {
        "enrolled_names": len(keys),
        "names_with_acts": sum(1 for r in reports if r.get("acts")),
        "contested": [r["name"] for r in reports if r.get("contested")],
        "signature_failures": sum(len(r.get("signature_failures", [])) for r in reports),
        "reports": reports,
        "CAVEAT": "identities are self-asserted at the point of use (PR-022 clause 5, "
                  "FORCE-IDENTITY-A open for impersonation). What IS closed is minting: "
                  "a name exists only inside a root-signed warrant.",
    }


def forks(root) -> list:
    return [f for r in verify_all(root)["reports"] for f in r.get("forks", [])]


# ------------------------------------------------------------------------ contest

def contest(root, accuser, key_path, target_name, target_seq, reason) -> dict:
    """File a forgery claim. DIS-5: the claim is an ACT on the accuser's own chain.

    Filing is not free and is not anonymous. It costs the accuser a permanent, signed
    position in its own record, which is what makes AF-3 ("the delay costs the delayer")
    bite without attaching a punitive consequence PR-022 clause 4 would forbid.
    """
    if accuser == target_name:
        raise AttestError("a name cannot contest its own act; that is a retraction, "
                          "which is a different verb and does not exist yet")
    return sign_act(root, accuser, key_path, "contest",
                    ref=f"{target_name}#{target_seq}",
                    body={"reason": reason,
                          "AF_3": "this claim is permanently attributable to the "
                                  "filing name, whether or not it is upheld",
                          "AF_4": "standing requires a live binding, not an opinion"})


# ----------------------------------------------------------------------------- cli

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="attest.py - signed acts, per-name chains, mechanical fork "
                    "detection. Detects forgery; cannot prevent it (D-17).")
    ap.add_argument("--root", help="harness root (else WARRANT_ROOT/ROSTER_ROOT env)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sign", help="append a signed act to a name's chain")
    s.add_argument("--name", required=True)
    s.add_argument("--key", required=True, help="that name's private key")
    s.add_argument("--kind", required=True, help="e.g. commit, filing, verdict, offer")
    s.add_argument("--ref", default="", help="what the act points at")
    s.add_argument("--body", help="JSON object")

    v = sub.add_parser("verify", help="verify signatures and detect forks")
    v.add_argument("--name", help="one name (default: every name)")
    v.add_argument("--json", action="store_true")

    sub.add_parser("forks", help="only the forks")

    c = sub.add_parser("chain", help="print one name's chain")
    c.add_argument("--name", required=True)

    k = sub.add_parser("contest", help="file a forgery claim as a signed act (DIS-5)")
    k.add_argument("--by", required=True, help="the accusing name")
    k.add_argument("--key", required=True)
    k.add_argument("--name", required=True, help="the name whose act is contested")
    k.add_argument("--seq", required=True, type=int)
    k.add_argument("--reason", required=True)

    args = ap.parse_args(argv)
    root = w.resolve_root(args.root)
    try:
        if args.cmd == "sign":
            body = json.loads(args.body) if args.body else None
            print(json.dumps(sign_act(root, args.name, args.key, args.kind, args.ref,
                                      body), indent=2, ensure_ascii=False))
        elif args.cmd == "verify":
            out = verify_name(root, args.name) if args.name else verify_all(root)
            if args.json or args.name:
                print(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                _render(out)
        elif args.cmd == "forks":
            print(json.dumps(forks(root), indent=2, ensure_ascii=False))
        elif args.cmd == "chain":
            for a in chain(root, args.name):
                print(f"  {a.get('seq'):>3} {a.get('kind','?'):12s} "
                      f"prev={str(a.get('prev'))[:20]:22s} "
                      f"{'signed' if a.get('_signed') else 'UNSIGNED'}")
        elif args.cmd == "contest":
            print(json.dumps(contest(root, args.by, args.key, args.name, args.seq,
                                     args.reason), indent=2, ensure_ascii=False))
    except (AttestError, ValueError, json.JSONDecodeError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


def _render(out) -> None:
    print(f"nombres inscritos      {out['enrolled_names']}")
    print(f"nombres con actos      {out['names_with_acts']}")
    print(f"fallas de firma        {out['signature_failures']}")
    print(f"cadenas en disputa     {len(out['contested'])} "
          f"{', '.join(out['contested']) or ''}")
    for r in out["reports"]:
        for f in r.get("forks", []):
            print(f"\nFORK en {r['name']}, prev={f['prev'][:24]}")
            for b in f["branches"]:
                print(f"    seq {b['seq']:>3}  {b['kind']:12s} {b['ts']}")
            print(f"    {f['PROOF']}")
    print(f"\n{out['CAVEAT']}")


if __name__ == "__main__":
    sys.exit(main())
