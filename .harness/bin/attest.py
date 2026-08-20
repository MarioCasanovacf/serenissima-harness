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

  DIS-1  FORK DETECTION IS MECHANICAL, NOT A JUDGEMENT -- AND IT CATCHES LESS THAN THE
         FIRST VERSION OF THIS PARAGRAPH CLAIMED. Every act by name N embeds the hash of
         N's previous act, so two acts sharing one predecessor is a FORK.

         RETRACTED. This paragraph once read "proof that two parties held the key".
         That proposition is FALSE and a second panel disproved it: one party signing
         twice from one predecessor produces an identical artefact, and the panel got
         exactly that from six ordinary `sign` calls with a single key. A fork is
         evidence of DIVERGENCE and nothing stronger. Where a branch does not verify it
         is weaker still, because a fork is fabricable with no key at all, for two
         write_text calls.

         WHAT IT DOES NOT CATCH, measured: a forger who uses the shipped `sign` verb
         appends at the current tip like everyone else and leaves NO fork. Four acts,
         one of them forged by a second party using the victim's key, verified clean
         with zero forks. So this detects CONCURRENT signing and RETROACTIVE insertion,
         not forgery in general. The refused PR-023 appeal's G2 promised a
         two-claimants detector; this is a narrower instrument than that promise, and
         the promise should not be re-made on its behalf.

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

THE THREE ANCHORING RECORDS (D3a, operator ruling 2026-08-17). A privileged act must
reconstruct back to the authorizing human. Two of the three records already existed and
were not rebuilt:

  INTENT DECLARED    `kind=intent`, filed by the actor, on THE ACTOR'S OWN CHAIN. New.
  PRIVILEGE GRANTED  the operator-signed warrant that issued the name. ALREADY EXISTED.
                     There is no second grant record and there must not be one: a name
                     exists only inside a warrant that verifies against `trust/root.pub`,
                     so the grant is the operator's signature and nothing else.
  PRIVILEGE EXERCISED  the signed act itself. ALREADY EXISTED.

`trace` walks act -> intent -> name -> warrant -> root fingerprint and prints which links
resolve and which do not. The last step in that walk is NOT self-authenticating: see
`warrant.py audit --expect`, which says so about itself.

WHY THE INTENT LIVES ON THE ACTOR'S OWN CHAIN, and what that does NOT buy. An earlier
version of this paragraph claimed chain-locality closes the framing surface -- an agent
filing an intent AS another name to manufacture evidence that the victim deliberated. A
NEGATIVE CONTROL REFUTED THAT: pooling every name's intents into one shared set passes the
entire test suite, so the directory an intent sits in is not what stops the attack. The
statement is corrected here rather than softened.

  WHAT CHAIN-LOCALITY ACTUALLY BUYS. DIS-2 applies to intents unchanged, because an intent
    IS an act: filing one as A credits A. The intent participates in fork detection like
    any other act. And there is no second registry to fall out of sync, which is the
    roster.py cache defect a panel exploited by hand-appending one entry (PR-010's
    computed-on-read doctrine).
  WHAT ACTUALLY CLOSES THE FRAMING SURFACE. The requirement that an intent VERIFY under
    the actor's own enrolled key. A party who cannot produce that signature cannot
    manufacture deliberation by the victim, wherever the file sits.
  AND WHAT THAT IS WORTH INSIDE THIS HARNESS: nothing, against an agent here. D-17 means
    every agent reads every private key, so every agent CAN produce that signature. The
    signature requirement bounds a party with no filesystem access, and this harness has
    no such party. Against an insider, the guarantee is DIS-2 and DIS-2 alone: the forgery
    credits the victim, so it can only destroy and never enrich.

WHAT D3a DOES NOT CLOSE, said plainly. D-17 IS UNTOUCHED. Every agent runs as the same OS
user and reads every private key, so an agent that can forge A's act can forge A's intent
in the same breath. This raises the cost of a forged privileged act from one signature to
TWO. That is the entire security gain and it is arithmetic, not prevention. Anyone reading
"the intent requirement authenticates the actor" has found a defect.

WHY A REFUSAL HERE IS NOT A PR-022 CLAUSE 4 CONSEQUENCE, flagged as an interpretive step
rather than buried. Clause 4 forbids attaching consequence to a Phase A reputation figure:
"no weighting, no gating, no privileges". The intent requirement reads no figure. It does
not vary by identity, standing, history, colegiado or any computed quantity -- it is the
same requirement for every name on its first act as on its thousandth, in the way that
`--kind` being mandatory is the same for everyone. A uniform well-formedness rule on the
act's own contents is not a weighting of the actor. IF A VERIFIER DISAGREES, the disposal
is to remove the refusal and keep `trace`, which reports the same facts and gates nothing;
that fallback is cheap and is why the reporting was built separately from the refusal.
This module does NOT rely on PR-060 for the argument: PR-060 is unconfirmed and does not
bind.

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

INTENT_KIND = "intent"

PRIVILEGED_KINDS = frozenset({"verdict", "contest", "distinguish", "grant"})
"""Acts that need a declared intent first (D3a, operator ruling 2026-08-17).

THE CRITERION, stated so the set is not arbitrary and can be argued with: an act is
privileged when its subject is a name OTHER than the signer, or a record that binds
others. `verdict` disposes of another name's work. `contest` accuses another name.
`distinguish` (T-402) disposes of a case for everyone afterwards. `grant` hands a
privilege on. `commit` and `filing` are a name doing its own work and are NOT privileged,
which is why they are absent.

DEFECT INTENT-BY-KIND-A, named here rather than found later. Enforcement reads the KIND
and never inspects the ref, so a signer who labels a disposal `commit` escapes the
requirement entirely. Inspecting the ref would not close it either, because `ref` is a
free string the signer also controls. What `trace` does instead is report intent coverage
for EVERY act regardless of kind, so the escape shows up as an act with no intent rather
than as a silence in the report. Visible, not prevented.

INTENT_KIND is deliberately absent. An intent requiring an intent is an infinite regress,
and the regress has to terminate at an act whose only backing is the signature and the
warrant behind it.
"""

INTENT_MAX_AGE_S = 24 * 3600
"""How long a declared intent stays usable.

An intent that never expires is a standing authorization, which is the opposite of
declaring intent BEFORE a specific act. This bound is a floor under that, not a solved
TTL problem: T-401 owns self-expiring credentials generally, and the number here is a
default this module chose. NO THRESHOLD RATIFIED by any record.
"""

PUBLIC_API = ("acts_dir", "chain", "sign_act", "verify_name", "verify_all",
              "forks", "contest", "declare_intent", "open_intents", "trace")


class AttestError(Exception):
    pass


def acts_dir(root, name=None) -> pathlib.Path:
    base = pathlib.Path(root) / "acts"
    return base / name if name else base


def enrolled_keys(root) -> dict:
    """Delegates to warrant.enrolled_keys, which DERIVES the set from verified warrants.
    This module used to read a cache file a panel simply appended to."""
    return w.enrolled_keys(root)


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

    With a fork present there is no single head. This walks from GENESIS taking the
    FIRST child in filename order at each step, which is arbitrary but deterministic --
    an earlier docstring called it the longest branch, which a panel disproved and which
    was never true. `verify` reports the ambiguity; refusing to append during a contest
    would freeze the epic, which DIS-3 forbids. It deliberately ignores signatures, so
    an unsigned act CAN steer a name's future `prev` values; that is a known weakness
    with no in-process fix (D-17) and is why `verify` reports unverified branches
    separately rather than treating them as evidence.
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


# --------------------------------------------------------------------- delegation

def _grant_body(to_name, pubkey, kinds, expires, note):
    return {"to": to_name, "pubkey": pubkey, "kinds": sorted(set(kinds)),
            "expires": expires, "note": note,
            "NO_SEAT": "a delegated identity holds NO plaza, NO seat and NO standing. "
                       "roster.py is untouched by this act and reconcile does not and must "
                       "not list this name in the roll.",
            "CEILING": "the kinds above are a SUBSET of what the grantor held at the moment "
                       "of signing, and the expiry is not later than the grantor's own.",
            }


def delegated_keys(root) -> dict:
    """Signing identities created by `grant` acts, DERIVED on read. Never a cache file.

    RETURNS name -> {pubkey, kinds, expires, grantor, depth, path}. A delegated name is not
    a warranted name and the difference is load-bearing:

      warrant.enrolled_keys IS NOT TOUCHED BY THIS FUNCTION, and must never be. `reconcile`
      requires every ROLL row to trace to a verified warrant, and that property is what lets
      warrant.py say minting is closed (conditionally). A delegated name holds no plaza and
      appears in no roll, so reconcile stays exactly as strong as it was.

      Nothing is minted outside the warrant tree either. The tree got DEEPER, not wider: a
      grant act lives on a warranted name's chain, which traces to a warrant, which traces
      to the operator's key. `trace` walks that.

    DEFECT DELEGATION-OUTSIDE-RECONCILE-A, named here rather than found later. `reconcile` is
    the detector for identities that exist without a warrant, and it does not look at grants,
    because grants are not roll rows. So a delegated signing identity is real and reconcile
    will not mention it. `attest.py delegations` is the corresponding report and it is the
    ONLY place these identities are enumerated. Anyone auditing who can sign in this harness
    must run BOTH verbs; either one alone is an incomplete answer.

    The ceiling is applied TRANSITIVELY here, so a grant can never widen what its grantor
    held even if the grantor's own privileges were narrowed after the fact -- the recomputation
    on every read is what makes that true, and is the second reason there is no cache.

    THE COST, stated rather than discovered later. This verifies every grant act's signature
    on every call, and one `sign_act` reaches it several times (via signing_keys, held_kinds
    and effective_expiry). At the current scale -- 9 warranted names, single-digit acts -- that
    is milliseconds and the correctness is worth it. It is O(acts x depth) per call and will
    need a per-call memo, NOT a persisted cache, if the chains grow. The distinction matters:
    a memo inside one call cannot go stale; a file can, and that is the roster.py defect.
    """
    warranted = w.enrolled_keys(root)
    out, frontier, depth = {}, dict(warranted), 0
    seen_names = set(warranted)
    # Breadth-first over grant acts, one hop per pass, so a cycle cannot loop forever and a
    # name already established at a shallower depth is never re-established deeper.
    while frontier and depth < 16:
        depth += 1
        nxt = {}
        for grantor in sorted(frontier):
            gk = warranted.get(grantor) or out.get(grantor)
            if gk is None:
                continue
            gpub = gk["pubkey"]
            g_kinds = (set(PRIVILEGED_KINDS) if grantor in warranted
                       else set(out[grantor]["kinds"]))
            g_exp = (warranted[grantor].get("valid_until") if grantor in warranted
                     else out[grantor]["expires"])
            for a in chain(root, grantor):
                if a.get("_unparseable") or a.get("kind") != "grant":
                    continue
                ok, _ = _verify_sig(root, grantor, a["_path"], gpub)
                if not ok:
                    continue
                b = a.get("body") or {}
                to, pub = b.get("to"), b.get("pubkey")
                if not to or not pub or to in seen_names:
                    # A name established once is never re-established: a second grant to the
                    # same name cannot raise its ceiling, and a grant naming a WARRANTED name
                    # cannot touch it at all. Both are refusals at sign time too; this is the
                    # read-side backstop, because sign-time checks bound only the shipped verb.
                    continue
                kinds = set(b.get("kinds") or []) & g_kinds
                exp = b.get("expires") or ""
                if g_exp and exp and exp > g_exp:
                    exp = g_exp          # clamp on READ; sign-time REFUSES rather than clamps
                if not exp or hc.now_iso() > exp:
                    continue             # expired credentials simply do not exist
                if not kinds:
                    continue
                out[to] = {"pubkey": pub, "kinds": sorted(kinds), "expires": exp,
                           "grantor": grantor, "depth": depth, "path": a["_path"]}
                seen_names.add(to)
                nxt[to] = out[to]
        frontier = nxt
    return out


def signing_keys(root) -> dict:
    """Every identity that can sign an act: warranted names plus live delegated ones.

    `enrolled_keys` deliberately still means WARRANTED ONLY, because warrant.py's guarantees
    are stated in those terms and a silent widening of that word would break them.
    """
    out = dict(w.enrolled_keys(root))
    for n, d in delegated_keys(root).items():
        out.setdefault(n, {"pubkey": d["pubkey"], "warrant": None,
                           "epic": None, "colegiado": None, "role": None,
                           "delegated": True, "grantor": d["grantor"],
                           "kinds": d["kinds"], "expires": d["expires"],
                           "depth": d["depth"]})
    return out


def held_kinds(root, name) -> set:
    """The privileged kinds `name` may sign. THE CEILING IS COMPUTED FROM THIS.

    A warranted name holds ALL of them, because nothing in this harness yet restricts a
    warranted name by role -- and saying so plainly matters: THE CEILING IS THEREFORE
    VACUOUS AT THE FIRST HOP. It binds from the second hop on, where a delegated identity
    holds only what it was granted and can pass on no more. Anyone who reads this as
    constraining a warranted name has read it wrong.
    """
    if name in w.enrolled_keys(root):
        return set(PRIVILEGED_KINDS)
    d = delegated_keys(root).get(name)
    return set(d["kinds"]) if d else set()


def effective_expiry(root, name):
    """When `name` stops being able to sign, or None for a warranted name with no expiry.

    A subagent CANNOT EXTEND THIS, and two independent barriers say so rather than one:
      1. a name cannot grant to itself (refused at sign time), so "extend myself" has no verb;
      2. even a grant from elsewhere is clamped to the grantor's own expiry on every read,
         so no path through the graph produces a later date than the warrant at its root.
    """
    ws = w.enrolled_keys(root)
    if name in ws:
        return ws[name].get("valid_until")
    d = delegated_keys(root).get(name)
    return d["expires"] if d else None


def grant_privilege(root, grantor, key_path, to_name, pubkey, kinds, expires, task,
                    note="") -> dict:
    """Delegate a SUBSET of the grantor's privileges, for a bounded time, as a signed act.

    `grant` is itself a privileged kind (D3a), so this composes: delegating requires a
    declared intent first. That was not arranged for elegance -- delegation is precisely the
    act whose deliberation should be on the record before it happens.

    WHAT THIS BOUNDS, stated before what it does not. Accident and drift: a coordinator
    cannot hand a subagent something it does not hold, cannot hand it something forever, and
    cannot hand it something the grantor's own warrant will outlive. Every hop is a signed
    act on the grantor's own chain, so overreach is ATTRIBUTABLE to whoever signed it.

    WHAT IT DOES NOT BOUND: an adversary. D-17 -- every agent runs as the same OS user and
    reads every private key, including the grantor's. An attacker does not need a grant; it
    signs as the grantor directly. This mechanism therefore raises no wall against a hostile
    agent inside this harness, and a test below demonstrates exactly that rather than
    asserting it.
    """
    if to_name == grantor:
        raise AttestError(
            "a name cannot grant to itself. This is the first of the two barriers against a "
            "credential extending its own life; the second is that every expiry is clamped "
            "to the grantor's on read, so even a grant from elsewhere cannot outlive its "
            "root warrant.")
    if to_name in w.enrolled_keys(root):
        raise AttestError(
            f"{to_name!r} is a WARRANTED name. A grant must not touch one: its privileges "
            f"come from an operator signature, and letting an agent's act modify them would "
            f"put agent-writable state on the authorization path.")
    if to_name in delegated_keys(root):
        raise AttestError(
            f"{to_name!r} already holds a delegated credential. A second grant is refused "
            f"rather than merged, because merging is how a ceiling gets raised one act at a "
            f"time. To change what it holds, let the credential expire.")
    want = set(kinds or [])
    if not want:
        raise AttestError("--kinds is required; a grant of nothing is not a grant")
    held = held_kinds(root, grantor)
    # Holding `grant` is itself required to grant, and a test found this missing: without it
    # any delegate could re-delegate forever, so the ceiling would bound WHAT is passed on
    # while leaving WHETHER it can be passed on unbounded -- half a ceiling. A warranted name
    # holds `grant` like everything else, so this binds only delegates, which is the point:
    # a subagent is re-delegable only if someone decided so explicitly.
    if "grant" not in held:
        raise AttestError(
            f"{grantor!r} holds {sorted(held) or 'nothing'} and NOT 'grant', so it cannot "
            f"delegate at all. Re-delegation is a privilege like any other and has to be "
            f"handed over on purpose; a credential is not re-delegable by default.")
    excess = want - held
    if excess:
        raise AttestError(
            f"DELEGATION CEILING: {grantor!r} holds {sorted(held) or 'nothing'} and cannot "
            f"grant {sorted(excess)}. No identity delegates more privilege than it holds "
            f"(D3b). Grant a subset, or obtain the privilege first.")
    if not str(expires or "").strip():
        raise AttestError("--expires is required; a credential with no expiry is a standing "
                          "privilege, which is what D3b exists to prevent")
    if hc.now_iso() > expires:
        raise AttestError(f"--expires {expires!r} is already in the past")
    ceiling = effective_expiry(root, grantor)
    if ceiling and expires > ceiling:
        # REFUSED, not clamped. Silently keeping a smaller value than the operator typed is
        # the exact shape of T-376, where `--voids A --voids B` kept B and exited 0.
        raise AttestError(
            f"--expires {expires!r} is later than {grantor!r}'s own expiry {ceiling!r}. "
            f"Refused rather than clamped: silently substituting a value the caller did not "
            f"ask for is defect T-376's shape, and this one would be substituting a "
            f"SECURITY parameter. Pass {ceiling!r} or earlier.")
    return sign_act(root, grantor, key_path, "grant", ref=to_name, task=task,
                    body=_grant_body(to_name, pubkey, want, expires, note))


def delegations(root) -> dict:
    """The report DELEGATION-OUTSIDE-RECONCILE-A makes necessary. Read-only.

    Counts raw AND distinct, both, never one alone (TELEMETRY-PROVENANCE-A).
    """
    d = delegated_keys(root)
    ws = w.enrolled_keys(root)
    rows = [dict(v, name=k) for k, v in sorted(d.items())]
    return {
        "warranted_raw": len(ws), "warranted_distinct": len(set(ws)),
        "delegated_raw": len(rows),
        "delegated_distinct": len({r["name"] for r in rows}),
        "can_sign_raw": len(ws) + len(rows),
        "can_sign_distinct": len(set(ws) | {r["name"] for r in rows}),
        "max_depth": max([r["depth"] for r in rows], default=0),
        "rows": rows,
        "RECONCILE_DOES_NOT_SEE_THESE": (
            "DEFECT DELEGATION-OUTSIDE-RECONCILE-A. warrant.py reconcile checks that every "
            "ROLL row traces to a verified warrant. A delegated identity holds no plaza and "
            "is in no roll, so reconcile will report clean while the names above can sign. "
            "That is not reconcile being broken -- it is answering a narrower question than "
            "'who can sign here'. Run both verbs. Neither alone is the answer."),
        "CEILING_IS_VACUOUS_AT_THE_FIRST_HOP": (
            "THE CEILING IS VACUOUS AT THE FIRST HOP. A warranted name holds every privileged "
            "kind, because nothing in this harness restricts a warranted name by role yet. So "
            "it constrains re-delegation and not the first grant. Stated because a reader "
            "could otherwise take it for a restraint on the coordinator, which it is not."),
        "D_17_UNCHANGED": (
            "This bounds ACCIDENT and makes overreach ATTRIBUTABLE. It does not bound an "
            "adversary: an attacker reads the grantor's private key and signs as the grantor "
            "directly, needing no grant at all."),
    }


# ------------------------------------------------------------------------- intent

def open_intents(root, name) -> list:
    """This name's intents that are SIGNED, VERIFIED, unexpired, and not yet consumed.

    Every one of those four adjectives is load-bearing and each one is a bypass that was
    considered and closed:

      SIGNED + VERIFIED against the name's enrolled key. Without this the requirement is
        satisfiable with no key at all, for one `write_text` -- DIS-1 measured exactly that
        cost when a panel fabricated a fork. An unsigned intent file would then "authorize"
        a forged act, which makes the feature worse than its absence.
      UNEXPIRED, per INTENT_MAX_AGE_S. An immortal intent is a standing authorization.
      UNCONSUMED. One intent authorizes ONE act. Consumption is DERIVED, by looking for an
        act on this chain whose `intent` field holds the intent's digest -- there is no
        consumption ledger. That is deliberate: a mutable side file is the roster.py cache
        defect (a second registry nothing reconciles), and warrant.enrolled_keys already
        had to be rewritten to compute-on-read for that reason. PR-010's doctrine.

    Read-only. Never repairs, never writes.
    """
    # signing_keys, not enrolled_keys: a delegated identity files intents too, or `grant`
    # would hand out a privilege its holder could never exercise.
    keys = signing_keys(root)
    if name not in keys:
        return []
    pub = keys[name]["pubkey"]
    acts = [a for a in chain(root, name) if "_unparseable" not in a]
    consumed = {a.get("intent") for a in acts if a.get("intent")}
    out = []
    for a in acts:
        if a.get("kind") != INTENT_KIND or a["_digest"] in consumed:
            continue
        ok, why = _verify_sig(root, name, a["_path"], pub)
        if not ok:
            continue
        age = _age_seconds(a.get("ts"))
        if age is None or age > INTENT_MAX_AGE_S:
            continue
        b = a.get("body") or {}
        out.append({"digest": a["_digest"], "seq": a.get("seq"),
                    "for_kind": b.get("for_kind"), "for_ref": b.get("for_ref"),
                    "task": b.get("task"), "declares": b.get("declares"),
                    "ts": a.get("ts"), "age_s": int(age)})
    return out


def _age_seconds(ts):
    """Seconds since an ISO timestamp, or None when it cannot be read.

    None is treated as EXPIRED by the caller, not as fresh. An unparseable timestamp must
    never buy an unbounded intent: the failure has to fall closed, because the field is
    written by the same party the bound is meant to constrain.
    """
    if not ts:
        return None
    import datetime as _dt
    try:
        t = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    return (_dt.datetime.now(_dt.timezone.utc) - t).total_seconds()


def declare_intent(root, name, key_path, for_kind, task, declares, for_ref="") -> dict:
    """File an intent to perform a privileged act, as a signed act on this name's chain.

    `task` is required and is the link D3 asks for: agent identity plus task id, so an
    exercised privilege reconstructs to the board task that authorized the work. It is not
    validated against the blackboard here -- attest.py must not import the board, and a
    task id that does not exist is a finding for `trace` to report, not a refusal that
    couples the evidentiary layer to task bookkeeping.
    """
    if for_kind == INTENT_KIND:
        raise AttestError("an intent cannot declare an intent; the regress has to stop")
    if not str(task).strip():
        raise AttestError("--task is required: D3a links intent to identity AND task id, "
                          "and an intent with no task cannot be reconstructed to the work "
                          "that authorized it")
    if not str(declares).strip():
        raise AttestError("--declares is required: an intent that says nothing is a "
                          "checkbox, and a checkbox anchors nothing")
    return sign_act(root, name, key_path, INTENT_KIND, ref=for_ref,
                    body={"for_kind": for_kind, "for_ref": for_ref, "task": task,
                          "declares": declares,
                          "NOT_AN_AUTHORIZATION": "this declares what this name intends. "
                                                  "The authorization is the warrant that "
                                                  "issued the name (D3a: privilege "
                                                  "granted), and it already existed."})


def intent_binds_ref(intent, ref) -> bool:
    """Does this intent's declared target permit an act against `ref`?

    T-408, and the rule is BIND WHEN DECLARED. An intent that names a target is bound to
    that target; an intent that leaves `for_ref` empty constrains kind and task only, which
    is what every intent did before this function existed.

    THE DEFECT IT CLOSES, found by the verifier revision-ataque while accepting T-400: an
    intent reading "I am going to issue a verdict on aurelia#1" authorized a verdict on
    orso#7 just as well, because matching compared (for_kind, task) and never looked at
    for_ref. That was not a false statement -- the docstring only ever promised kind plus
    task -- it was a gap between what an intent SAID and what it BOUND.

    WHY BIND-WHEN-DECLARED RATHER THAN BIND-ALWAYS. Always-binding would force one intent
    per target, and the task asked for that cost to be measured before deciding. THE
    MEASUREMENT IS DEGENERATE AND IS REPORTED AS SUCH: the live chain holds exactly ONE
    privileged act, in one (name, kind, task) group, against one target. A population of
    one settles nothing about a typical session, so the decision cannot rest on it and does
    not. It rests on this instead: bind-when-declared costs ZERO additional intents for
    anyone who leaves the field empty, and narrows only the signer who chose to name a
    target. Nothing permitted today becomes forbidden except the mismatch itself.

    IT AUTHENTICATES NOTHING, and the same warning belongs here as on the act's own `ref`.
    `for_ref` is written by the signer, exactly like `ref`. Binding one self-asserted field
    to another self-asserted field does not stop a signer who intends to deviate -- it makes
    the deviation WRITTEN DOWN, on that name's own chain, credited to that name. D-17 is
    untouched: an agent holding another agent's key files the matching intent too.
    """
    declared = str(intent.get("for_ref") or "")
    return not declared or declared == str(ref or "")


def _match_intent(root, name, kind, task, ref=""):
    """The intent that authorizes this act, or a refusal explaining exactly what is
    missing. Returns (intent_or_None, message_or_None)."""
    avail = open_intents(root, name)
    same_kind_task = [i for i in avail
                      if i["for_kind"] == kind and str(i["task"]) == str(task)]
    for i in same_kind_task:
        if intent_binds_ref(i, ref):
            return i, None
    how = (f"python3 .harness/bin/attest.py declare-intent --name {name} --key <key> "
           f"--for-kind {kind} --task {task} --for-ref {ref or '<target>'} "
           f"--declares \"<what and why>\"")
    if same_kind_task:
        # The narrow miss T-408 exists for, and it gets its own message. Folding it into the
        # generic "none for this kind and task" refusal would report the one case where the
        # signer DID declare a target as though they had declared nothing.
        named = ", ".join(repr(i["for_ref"]) for i in same_kind_task)
        return None, (
            f"{name!r} has {len(same_kind_task)} open intent(s) for a {kind!r} act on task "
            f"{task!r}, but each one NAMES A DIFFERENT TARGET: {named}. This act targets "
            f"{str(ref)!r}. An intent that names a target is bound to it (T-408); an intent "
            f"that leaves --for-ref empty is not. File one for this target:\n  {how}\n"
            f"Binding these two fields authenticates nothing -- the signer writes both -- it "
            f"only makes a deviation written down on this name's own chain.")
    if not avail:
        return None, (
            f"{name!r} has no open intent for a {kind!r} act on task {task!r}, and "
            f"{kind!r} is privileged (D3a: intent declared BEFORE the act). File one "
            f"first:\n  {how}\n"
            f"An intent must be signed by this name's enrolled key, no older than "
            f"{INTENT_MAX_AGE_S}s, and unconsumed. If you filed one and it is not being "
            f"seen, run `attest.py intents --name {name}` -- an unsigned or expired "
            f"intent is invisible here BY DESIGN, because an unsigned one costs no key.")
    have = ", ".join(f"{i['for_kind']}/task={i['task']}" for i in avail)
    return None, (
        f"{name!r} has {len(avail)} open intent(s) but none for a {kind!r} act on task "
        f"{task!r}. Open: {have}. An intent authorizes ONE act of ONE kind on ONE task, "
        f"so a near miss is a refusal and not a warning. File the right one:\n  {how}")


# --------------------------------------------------------------------------- sign

def sign_act(root, name, key_path, kind, ref="", body=None, task=None) -> dict:
    """Write an act onto `name`'s chain and sign it with `name`'s key.

    This process signs with a key it can read, which is exactly the limitation D-17
    names. The value is not that the signature is unforgeable -- it is not -- but that
    the act is CHAINED, so a second party signing as `name` produces a fork.
    """
    root = pathlib.Path(root)
    keys = signing_keys(root)
    if name not in keys:
        raise AttestError(
            f"{name!r} can sign nothing. A name is either issued inside a root-signed "
            f"warrant (warrant.py) or holds a live delegated credential from one "
            f"(`attest.py delegations`). Minting the first kind is closed, conditionally; "
            f"the second kind expires and cannot extend itself (D3b).")
    # D3b. A delegated identity signs only the kinds it was granted, and only until its
    # credential expires. Both are recomputed here rather than trusted from anywhere.
    if kind in PRIVILEGED_KINDS:
        held = held_kinds(root, name)
        if kind not in held:
            raise AttestError(
                f"DELEGATION CEILING: {name!r} holds {sorted(held) or 'nothing'} and cannot "
                f"sign a {kind!r} act. A delegated identity signs no more than it was "
                f"granted (D3b), and it cannot widen that by asking.")
    exp = effective_expiry(root, name)
    if exp and hc.now_iso() > exp:
        raise AttestError(
            f"{name!r}'s authority expired at {exp}. A credential cannot extend itself: a "
            f"name cannot grant to itself, and every grant is clamped to its grantor's own "
            f"expiry on read, so no path produces a later date than the root warrant.")
    key = pathlib.Path(key_path).expanduser()
    if not key.exists():
        raise AttestError(f"no such private key: {key}")

    # D3a: what can be refused without reading the chain is refused here, before the guard
    # is even taken, so the cheap failure stays cheap.
    if kind in PRIVILEGED_KINDS and not str(task or "").strip():
        raise AttestError(
            f"--task is required for a {kind!r} act: {kind!r} is privileged, and D3a links "
            f"the exercised privilege to the intent by identity AND task id. Without a "
            f"task there is nothing to match an intent against.")

    import roster  # lazy, for the guard; roster imports warrant lazily too, no cycle

    d = acts_dir(root, name)
    d.mkdir(parents=True, exist_ok=True)
    # The whole read-decide-create runs under the same guard roster.issue uses. The
    # first build of this module had none, and a blind panel measured 75 of 100
    # concurrent acts silently lost -- verbatim the defect roster.py had just repaired,
    # reintroduced in the module that is supposed to BE the evidentiary record. Worse,
    # the collisions overwrote each other's files, so the forks DIS-1 exists to catch
    # were destroyed by the same bug: 0 detections in 20 trials.
    # THE WHOLE read-decide-create-WRITE runs under the same guard roster.issue uses.
    # Two panels found two different defects here. The first build had no guard at all
    # and silently lost 75 of 100 concurrent acts, destroying the very forks DIS-1
    # exists to detect. The second build guarded the seq computation and the O_EXCL
    # create but released the guard BEFORE writing the JSON body, so a concurrent
    # signer read a zero-byte file, chain() filed it unparseable, head() skipped it and
    # returned a stale prev -- manufacturing a FORK from a single party signing twice,
    # which the tool then printed as proof that two parties held the key.
    with roster._guard(root):
        # D3a, AND IT IS IN HERE FOR A REASON. Matching an intent is a read-decide-write:
        # read the open intents, decide which one authorizes this act, write the act that
        # consumes it. Outside the guard, two concurrent privileged acts both see the same
        # open intent and both consume it, which turns "one intent authorizes ONE act" into
        # a suggestion. That is the identical shape as the two defects this function was
        # already repaired for, so it is not a hypothetical race -- it is this module's
        # established failure mode, in a third place.
        # It still refuses before any file is created, so a refusal writes nothing.
        used_intent = None
        if kind in PRIVILEGED_KINDS:
            used_intent, why = _match_intent(root, name, kind, task, ref)
            if used_intent is None:
                raise AttestError(why)
        seq = 1 + max((int(q.stem) for q in d.glob("*.json") if q.stem.isdigit()),
                      default=-1)
        prev = head(root, name)
        while True:
            path = d / f"{seq:03d}.json"
            try:
                # O_EXCL: never silently overwrite an existing act, even after a
                # deletion renumbers the directory
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                seq += 1
                continue
            break
        act = {
            "schema_version": SCHEMA_VERSION,
            "name": name,
            "seq": seq,
            "kind": kind,
            "ref": ref,
            "body": body if body is not None else {},
            "prev": prev,
            "ts": hc.now_iso(),
            "namespace": NAMESPACE,
            "task": str(task) if task else "",
            # D3a. The digest of the intent this act exercises, or "" when the kind is not
            # privileged. Consumption is derived from this field alone -- there is no
            # ledger, so there is no second registry to fall out of sync (PR-010).
            "intent": used_intent["digest"] if used_intent else "",
            "CREDIT_FOLLOWS_THE_SIGNATURE": "DIS-2: every effect of this act accrues to "
                                            "the signing name, never to the process",
        }
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(act, indent=2, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    r = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", NAMESPACE,
                        str(path)], text=True, capture_output=True)
    if r.returncode != 0:
        path.unlink(missing_ok=True)
        raise AttestError(f"could not sign: {(r.stderr or r.stdout).strip()}")
    _emit(root, "act_signed", name=name, seq=seq, act_kind=kind,
          prev=act["prev"], task=act["task"], intent=act["intent"])
    return {"name": name, "seq": seq, "path": str(path), "digest": digest(path),
            "prev": act["prev"], "task": act["task"], "intent": act["intent"],
            "privileged": kind in PRIVILEGED_KINDS}


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
    keys = signing_keys(root)
    if name not in keys:
        return {"name": name, "enrolled": False,
                "note": "no warrant issued this name and it holds no live delegated "
                        "credential; its acts carry no standing. A credential that has "
                        "EXPIRED lands here too, which is the intended reading: the acts it "
                        "signed while live remain on the chain and verifiable, but the name "
                        "can no longer be resolved to a key, so this report cannot speak "
                        "for them."}
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

    unverified = {b["path"] for b in bad}
    forks_found = []
    for prev, siblings in by_prev.items():
        if len(siblings) <= 1:
            continue
        all_verified = all(s["_path"] not in unverified for s in siblings)
        forks_found.append({
            "prev": prev,
            "branches": [{"seq": s.get("seq"), "kind": s.get("kind"),
                          "ts": s.get("ts"), "digest": s["_digest"],
                          "verified": s["_path"] not in unverified}
                         for s in siblings],
            "all_branches_verified": all_verified,
            "MEANS": (
                "DIVERGENCE, signed. Every branch carries a valid signature by this "
                "name's enrolled key, so the branches were produced by whoever held it "
                "-- which may be ONE party signing twice from one predecessor, and is "
                "indistinguishable from two. An earlier version called this proof that "
                "two parties held the key; that proposition is false and is retracted."
                if all_verified else
                "DIVERGENCE ONLY, NOT PROOF: at least one branch does not verify, and "
                "anyone can write an unsigned file with no key at all. A blind panel "
                "fabricated a fork for the cost of two write_text calls, so an "
                "unverified branch establishes nothing about who held a key."),
            "STATUS": "CONTESTED" if all_verified else "UNVERIFIED-DIVERGENCE",
            "NO_CONSEQUENCE": "DIS-4 and PR-022 clause 4: contested acts carry no "
                              "weight until adjudicated, including the forger's. "
                              "Nothing is frozen (DIS-3).",
        })
    return {"name": name, "enrolled": True, "acts": len(acts),
            "signature_failures": bad, "forks": forks_found,
            "contested": bool(forks_found)}


def verify_all(root) -> dict:
    keys = signing_keys(root)
    names = sorted(set(keys) | {p.name for p in acts_dir(root).iterdir()
                                if p.is_dir()} if acts_dir(root).exists() else set(keys))
    reports = [verify_name(root, n) for n in names]
    return {
        "enrolled_names": len(keys),
        "names_with_acts": sum(1 for r in reports if r.get("acts")),
        "contested": [r["name"] for r in reports if r.get("contested")],
        "signature_failures": sum(len(r.get("signature_failures", [])) for r in reports),
        "reports": reports,
        "NOTE": "This is attest.py's own note, NOT a quotation of PR-022 clause 5's "
                "canonical caveat -- a panel caught the previous version paraphrasing "
                "that string and appending a claim to it. Read the canonical text via "
                "reputation.py. On the merits: identities remain self-asserted at the "
                "point of use, FORCE-IDENTITY-A stays open for impersonation, and what "
                "the warrant layer closes is MINTING, subject to warrant.py reconcile "
                "coming back clean.",
    }


def forks(root) -> list:
    return [f for r in verify_all(root)["reports"] for f in r.get("forks", [])]


# -------------------------------------------------------------------------- trace

def trace(root, name=None) -> dict:
    """Walk every act back through its three anchoring records to the operator (D3a).

    act (privilege exercised) -> intent (intent declared) -> name -> warrant (privilege
    granted) -> root fingerprint -> the human who holds the private half.

    IT REPORTS AND NEVER REFUSES. This is the half of D3a that survives even if a verifier
    rules the `sign` refusal out of order under PR-022 clause 4, which is why it is a
    separate function with no shared state.

    Counts come out RAW AND DISTINCT, both, never one alone (TELEMETRY-PROVENANCE-A).

    THE WALK'S LAST STEP IS NOT SELF-AUTHENTICATING and the report says so. Every check in
    this process reads `trust/root.pub` from a filesystem every agent can write. A trace
    that ends "authorized by SHA256:..." is consistent with an attacker having written that
    fingerprint there. `warrant.py audit --expect <fingerprint held off this machine>` is
    the only thing that breaks the circle, and the report carries that instruction rather
    than implying it was already done.
    """
    keys = signing_keys(root)
    names = [name] if name else sorted(
        set(keys) | ({p.name for p in acts_dir(root).iterdir() if p.is_dir()}
                     if acts_dir(root).exists() else set()))
    anchor = None
    try:
        fp = pathlib.Path(root) / "trust" / "root.fingerprint"
        anchor = fp.read_text(encoding="utf-8").strip() if fp.is_file() else None
    except OSError:
        anchor = None

    rows, gaps, unpriv, ref_open = [], [], [], []
    for n in names:
        issued = keys.get(n)
        pub = issued["pubkey"] if issued else None
        by_digest = {}
        acts = [a for a in chain(root, n) if "_unparseable" not in a]
        for a in acts:
            by_digest[a["_digest"]] = a
        for a in acts:
            kind = a.get("kind", "?")
            privileged = kind in PRIVILEGED_KINDS
            sig_ok = False
            if pub:
                sig_ok, _ = _verify_sig(root, n, a["_path"], pub)
            idig = a.get("intent") or ""
            intent_act = by_digest.get(idig) if idig else None
            intent_ok = False
            if intent_act is not None and pub:
                intent_ok, _ = _verify_sig(root, n, intent_act["_path"], pub)
            ibody = (intent_act.get("body") or {}) if intent_act is not None else {}
            intent_names_a_target = bool(str(ibody.get("for_ref") or ""))
            ref_agrees = (not intent_names_a_target
                          or str(ibody.get("for_ref")) == str(a.get("ref") or ""))
            row = {
                "name": n, "seq": a.get("seq"), "kind": kind,
                "privileged": privileged,
                "task": a.get("task") or "",
                "exercised_verified": sig_ok,
                "intent_digest": idig,
                "intent_present": intent_act is not None,
                "intent_verified": intent_ok,
                "intent_same_chain": intent_act is not None,
                "intent_names_a_target": intent_names_a_target,
                "intent_ref_agrees": ref_agrees,
                "granted_by_warrant": issued["warrant"] if issued else None,
                "colegiado": issued["colegiado"] if issued else None,
                "role": issued["role"] if issued else None,
                "anchor": anchor,
            }
            row["complete"] = bool(
                sig_ok and issued and anchor
                and (not privileged or (intent_act is not None and intent_ok
                                        and ref_agrees
                                        and str((intent_act.get("body") or {}).get("task"))
                                        == str(a.get("task") or ""))))
            if privileged and intent_act is not None and not intent_names_a_target:
                # T-408's residue, and it is a POPULATION rather than a gap. These acts were
                # authorized by an intent that named no target, which is permitted and is
                # what every intent did before T-408. It is reported because the looseness is
                # otherwise invisible: a row saying `complete` looks identical whether the
                # intent bound the target or bound nothing about it.
                ref_open.append({"name": n, "seq": a.get("seq"), "kind": kind,
                                 "ref": a.get("ref", ""), "task": a.get("task") or ""})
            rows.append(row)
            # INTENT-BY-KIND-A's mitigation, and it CANNOT live in `gaps`. A test caught
            # that: an act labelled `commit` with a good signature, a warrant and an anchor
            # is `complete` -- correctly, because no intent is required of it -- so it never
            # reaches the gap branch and the mislabelled-disposal surface was reported
            # nowhere at all. These are not gaps. They are the population an auditor has to
            # read, because a disposal hidden under an unprivileged label looks exactly like
            # an honest unprivileged act and no mechanism here can tell them apart.
            if not privileged and not idig:
                unpriv.append({"name": n, "seq": a.get("seq"), "kind": kind,
                               "ref": a.get("ref", ""), "task": a.get("task") or ""})
            if not row["complete"]:
                missing = []
                if not sig_ok:
                    missing.append("exercised act does not verify")
                if not issued:
                    missing.append("no warrant issued this name, so nothing granted it")
                if not anchor:
                    missing.append("no trust/root.fingerprint to end the walk at")
                if privileged and intent_act is None:
                    missing.append("no intent record" if not idig else
                                   "intent digest names an act not on this chain")
                elif privileged and not intent_ok:
                    missing.append("intent record does not verify")
                elif privileged and str((intent_act.get("body") or {}).get("task")) \
                        != str(a.get("task") or ""):
                    missing.append("intent task and act task disagree")
                elif privileged and not ref_agrees:
                    missing.append(
                        "intent names target %r and the act targets %r (T-408)"
                        % (ibody.get("for_ref"), a.get("ref", "")))
                gaps.append({"name": n, "seq": a.get("seq"), "kind": kind,
                             "missing": missing})

    priv = [r for r in rows if r["privileged"]]
    return {
        "acts_raw": len(rows),
        "acts_distinct": len({(r["name"], r["seq"]) for r in rows}),
        "privileged_raw": len(priv),
        "privileged_distinct": len({(r["name"], r["seq"]) for r in priv}),
        "complete_raw": sum(1 for r in rows if r["complete"]),
        "complete_distinct": len({(r["name"], r["seq"]) for r in rows if r["complete"]}),
        "names_raw": len(names),
        "names_distinct": len(set(names)),
        "ref_open_intent_raw": len(ref_open),
        "ref_open_intent_distinct": len({(r["name"], r["seq"]) for r in ref_open}),
        "unprivileged_no_intent_raw": len(unpriv),
        "unprivileged_no_intent_distinct": len({(u["name"], u["seq"]) for u in unpriv}),
        "anchor": anchor,
        "rows": rows,
        "gaps": gaps,
        "unprivileged_no_intent": unpriv,
        "ref_open_intent": ref_open,
        "T_408_REF_BINDS_WHEN_DECLARED": (
            "An intent that names a target binds to it; an intent that leaves for_ref empty "
            "constrains kind and task only. The acts listed under ref_open_intent took the "
            "second path, which is permitted. THE BINDING AUTHENTICATES NOTHING: for_ref and "
            "ref are both written by the signer, so tying them together cannot stop a signer "
            "who intends to deviate -- it makes the deviation written down, on that name's "
            "own chain, credited to that name. D-17 is untouched."),
        "INTENT_BY_KIND_A": (
            "DEFECT INTENT-BY-KIND-A. "
            "The acts listed under unprivileged_no_intent required no intent because of "
            "their KIND. A signer who labels a disposal `commit` lands in that list and "
            "escapes the requirement. Inspecting `ref` would not help: the signer writes "
            "that too. So this list is the audit surface, and it is a list a human reads "
            "rather than a check a machine passes. Intent acts appear in it as well. They "
            "are NOT filtered out even though they can never require an intent themselves, "
            "because a disposal labelled `intent` would hide in exactly the gap that filter "
            "would open."),
        "COUNTS_ARE_REPORTED_TWICE": "raw and distinct, per TELEMETRY-PROVENANCE-A. Acts "
                                     "are files on disk, so raw and distinct agree unless "
                                     "a directory was renumbered; when they diverge the "
                                     "chain has been edited and that is the finding.",
        # The obvious way to write this note is to interpolate the on-disk fingerprint into
        # the --expect command so the operator can copy-paste it. THAT IS THE BUG, and the
        # first version of this string had it: pasting back a value read from the file under
        # suspicion turns an audit into a self-consistency check while looking like an
        # audit. Same family as AUDIT-EXPECT-DISCARDED. The value on disk is shown, clearly
        # labelled as the untrusted side of the comparison, and never inside the command.
        "ANCHOR_IS_UNVERIFIED": (
            "The last step of every walk above reads trust/root.pub from a filesystem every "
            "agent can write (D-17). This report cannot tell the operator's anchor from one "
            "an attacker wrote, so read every 'complete' above as "
            "complete-IF-the-anchor-is-genuine. To settle it, run\n"
            "    python3 .harness/bin/warrant.py audit --expect \"SHA256:<the fingerprint "
            "you hold OFF this machine>\"\n"
            "typing the value from your password manager, phone note or paper. Do NOT copy "
            "it from this report: the fingerprint this process can see is "
            + (anchor or "(absent)") + ", and that string is the thing being checked, not "
            "the thing to check it against."),
        "D_17_UNCHANGED": "An agent that can read a name's private key can file its intent "
                          "AND its act. D3a raises a forged privileged act from one "
                          "signature to two. It authenticates nobody.",
    }


# ------------------------------------------------------------------------ contest

def contest(root, accuser, key_path, target_name, target_seq, reason, task=None) -> dict:
    """File a forgery claim. DIS-5: the claim is an ACT on the accuser's own chain.

    Filing is not free and is not anonymous. It costs the accuser a permanent, signed
    position in its own record, which is what makes AF-3 ("the delay costs the delayer")
    bite without attaching a punitive consequence PR-022 clause 4 would forbid.

    `contest` IS a privileged kind (D3a), so as of 2026-08-17 an accuser must declare the
    intent to accuse before accusing. That was checked against AF-5 before it was allowed:
    a mechanism must not let one party stall another. It does not, because an intent is
    SELF-SERVICE -- the accuser files its own, on its own chain, with its own key, and no
    third party is in the path. The cost is one extra signature by the accuser, which is
    the direction AF-3 already points.
    """
    if accuser == target_name:
        raise AttestError("a name cannot contest its own act; that is a retraction, "
                          "which is a different verb and does not exist yet")
    return sign_act(root, accuser, key_path, "contest",
                    ref=f"{target_name}#{target_seq}", task=task,
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
    s.add_argument("--task", help="board task id; REQUIRED for a privileged kind (%s)"
                                 % ", ".join(sorted(PRIVILEGED_KINDS)))

    di = sub.add_parser("declare-intent",
                        help="declare intent to perform a privileged act, BEFORE it (D3a)")
    di.add_argument("--name", required=True)
    di.add_argument("--key", required=True)
    di.add_argument("--for-kind", required=True, dest="for_kind",
                    help="the privileged kind this intent authorizes, one act of it")
    di.add_argument("--task", required=True, help="board task id (D3a linkage)")
    di.add_argument("--declares", required=True, help="what this name intends, and why")
    di.add_argument("--for-ref", default="", dest="for_ref")

    ints = sub.add_parser("intents", help="open, signed, unexpired, unconsumed intents")
    ints.add_argument("--name", required=True)

    tr = sub.add_parser("trace", help="walk acts back through the three anchoring "
                                      "records to the operator (D3a)")
    tr.add_argument("--name", help="one name (default: every name)")
    tr.add_argument("--json", action="store_true")

    g = sub.add_parser("grant", help="delegate a SUBSET of your privileges, with an "
                                     "expiry you cannot outlive (D3b)")
    g.add_argument("--by", required=True, help="the granting name")
    g.add_argument("--key", required=True, help="the granting name's private key")
    g.add_argument("--to", required=True, dest="to", help="the delegated identity")
    g.add_argument("--pubkey", required=True, help="the delegate's PUBLIC key, verbatim")
    g.add_argument("--kinds", required=True, nargs="+",
                   help="privileged kinds to delegate; must be a subset of what you hold")
    g.add_argument("--expires", required=True,
                   help="ISO instant; refused, never clamped, if later than your own")
    g.add_argument("--task", required=True, help="board task id (D3a linkage)")
    g.add_argument("--note", default="")

    dg = sub.add_parser("delegations", help="every live delegated credential; the report "
                                           "reconcile does NOT cover (D3b)")
    dg.add_argument("--json", action="store_true")

    hk = sub.add_parser("holds", help="what a name may sign, and until when")
    hk.add_argument("--name", required=True)

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
    k.add_argument("--task", help="board task id; contest is privileged, so this is "
                                 "required and an intent must be on file first (D3a)")

    args = ap.parse_args(argv)
    root = w.resolve_root(args.root)
    try:
        if args.cmd == "sign":
            body = json.loads(args.body) if args.body else None
            print(json.dumps(sign_act(root, args.name, args.key, args.kind, args.ref,
                                      body, task=args.task),
                             indent=2, ensure_ascii=False))
        elif args.cmd == "declare-intent":
            print(json.dumps(declare_intent(root, args.name, args.key, args.for_kind,
                                            args.task, args.declares, args.for_ref),
                             indent=2, ensure_ascii=False))
        elif args.cmd == "intents":
            out = open_intents(root, args.name)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            if not out:
                print(f"\nno OPEN intents for {args.name!r}. An intent is invisible here "
                      f"unless it is signed by that name's enrolled key, under "
                      f"{INTENT_MAX_AGE_S}s old, and not yet consumed by an act.",
                      file=sys.stderr)
        elif args.cmd == "trace":
            out = trace(root, args.name)
            if args.json:
                print(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                _render_trace(out)
        elif args.cmd == "grant":
            print(json.dumps(grant_privilege(root, args.by, args.key, args.to,
                                             args.pubkey, args.kinds, args.expires,
                                             args.task, args.note),
                             indent=2, ensure_ascii=False))
        elif args.cmd == "delegations":
            out = delegations(root)
            if args.json:
                print(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                _render_delegations(out)
        elif args.cmd == "holds":
            held = sorted(held_kinds(root, args.name))
            print(json.dumps({
                "name": args.name,
                "privileged_kinds": held,
                "expires": effective_expiry(root, args.name),
                "warranted": args.name in w.enrolled_keys(root),
                "NOTE": ("A warranted name holds every privileged kind, because nothing here "
                         "restricts a warranted name by role yet. The ceiling binds on "
                         "re-delegation, not on the first grant."),
            }, indent=2, ensure_ascii=False))
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
                                     args.reason, task=args.task),
                             indent=2, ensure_ascii=False))
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
                print(f"    seq {b['seq']:>3}  {b['kind']:12s} {b['ts']}"
                      f"  {'verificado' if b.get('verified') else 'SIN VERIFICAR'}")
            # `PROOF` until 2026-08-17. When DIS-1's proof claim was retracted the key was
            # renamed to MEANS and this line was not updated, so `verify` with a fork
            # present raised KeyError -- the human-readable renderer crashed on the ONE
            # case it exists to report, and nothing caught it because no test rendered a
            # fork. Found while building D3a. Defect RENDER-FORK-KEYERROR.
            print(f"    {f['STATUS']}: {f['MEANS']}")
            print(f"    {f['NO_CONSEQUENCE']}")
    print(f"\n{out['NOTE']}")


def _render_delegations(out) -> None:
    print(f"nombres con warrant    {out['warranted_raw']} crudos / "
          f"{out['warranted_distinct']} distintos")
    print(f"credenciales delegadas {out['delegated_raw']} crudas / "
          f"{out['delegated_distinct']} distintas")
    print(f"pueden firmar          {out['can_sign_raw']} crudos / "
          f"{out['can_sign_distinct']} distintos")
    print(f"profundidad maxima     {out['max_depth']}")
    for r in out["rows"]:
        print(f"  {r['name']:20s} d{r['depth']} de {r['grantor']:18s} "
              f"vence {r['expires']}  {','.join(r['kinds'])}")
    print(f"\n{out['RECONCILE_DOES_NOT_SEE_THESE']}")
    print(f"\n{out['CEILING_IS_VACUOUS_AT_THE_FIRST_HOP']}")
    print(f"\n{out['D_17_UNCHANGED']}")


def _render_trace(out) -> None:
    print(f"actos                  {out['acts_raw']} crudos / "
          f"{out['acts_distinct']} distintos")
    print(f"actos privilegiados    {out['privileged_raw']} crudos / "
          f"{out['privileged_distinct']} distintos")
    print(f"cadena completa        {out['complete_raw']} crudos / "
          f"{out['complete_distinct']} distintos")
    print(f"nombres                {out['names_raw']} crudos / "
          f"{out['names_distinct']} distintos")
    print(f"sin intencion exigida  {out['unprivileged_no_intent_raw']} crudos / "
          f"{out['unprivileged_no_intent_distinct']} distintos")
    print(f"ancla                  {out['anchor'] or 'NINGUNA'}")
    for r in out["rows"]:
        mark = "ok " if r["complete"] else "INC"
        print(f"  {mark} {r['name']:20s} seq {str(r['seq']):>3} {r['kind']:12s} "
              f"{'PRIV' if r['privileged'] else '    '} "
              f"tarea={r['task'] or '-':8s} "
              f"warrant={r['granted_by_warrant'] or 'NINGUNO'}")
    for g in out["gaps"]:
        print(f"\nHUECO {g['name']} seq {g['seq']} ({g['kind']})")
        for m in g["missing"]:
            print(f"    {m}")
    if out["unprivileged_no_intent"]:
        print(f"\n{out['INTENT_BY_KIND_A']}")
        for u in out["unprivileged_no_intent"]:
            print(f"    {u['name']:20s} seq {str(u['seq']):>3} {u['kind']:12s} "
                  f"ref={u['ref'] or '-'}")
    print(f"\n{out['ANCHOR_IS_UNVERIFIED']}")
    print(f"\n{out['D_17_UNCHANGED']}")


if __name__ == "__main__":
    sys.exit(main())
