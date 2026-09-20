#!/usr/bin/env python3
"""deliberate.py -- Multi-agent assembly deliberation protocol with anti-capture devices.

Implements the assembly deliberation protocol (A-3) with four core anti-sycophancy
and anti-capture correctives:
  1. 3-Sponsor Quorum Floor: Prevents nuisance proposals (requires >= 3 distinct sponsors).
  2. Evidence Anchoring: Requires verifiable evidence references before deliberation convenes.
  3. Pre-Deliberation Straw Poll: Records pre-registered Bayesian priors before group discussion.
  4. Deterministic Seeded Speaker Shuffle: Neutralizes primacy/recency order effects via
     cryptographically seeded pseudo-random speaker scheduling.
  5. Condorcet Resolution: Final aggregation via Schulze/Copeland voting engine.

Storage:
  Dossiers are saved under `.harness/deliberations/D-NNN.json`.
"""
import argparse
import hashlib
import json
import os
import pathlib
import random
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import condorcet  # noqa: E402
import harness_common as hc  # noqa: E402
import precedent  # noqa: E402 -- T-428 item 4: conclude re-validates dossier.case
# against precedent.py's live case register (cases_dir/load_case), never trusting
# the value stamped at propose time.

DELIBERATIONS_DIR = ROOT / ".harness" / "deliberations"
DOSSIER_RE = re.compile(r"^D-(\d+)$")
MIN_SPONSORS = 3


class DeliberationError(Exception):
    """Domain error in deliberation protocol."""
    pass


def resolve_delib_dir(harness_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    if harness_root:
        d = pathlib.Path(harness_root) / "deliberations"
    else:
        d = hc.HARNESS / "deliberations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def allocate_dossier_id(delib_dir: pathlib.Path) -> str:
    existing = [
        int(m.group(1))
        for p in delib_dir.glob("D-*.json")
        if (m := DOSSIER_RE.match(p.stem))
    ]
    next_num = max(existing) + 1 if existing else 1
    return f"D-{next_num:03d}"


def load_dossier(delib_dir: pathlib.Path, dossier_id: str) -> Dict[str, Any]:
    if not DOSSIER_RE.match(dossier_id):
        raise DeliberationError(f"Invalid dossier ID format: {dossier_id!r} (expected D-NNN)")
    path = delib_dir / f"{dossier_id}.json"
    if not path.exists():
        raise DeliberationError(f"Dossier {dossier_id} not found under {delib_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_dossier(delib_dir: pathlib.Path, dossier: Dict[str, Any]) -> None:
    dossier_id = dossier["id"]
    path = delib_dir / f"{dossier_id}.json"
    hc.atomic_write_json(path, dossier)


def compute_deterministic_speaker_order(speakers: List[str], seed_str: str) -> List[str]:
    """Compute a deterministic permutation of speakers given a seed string.

    Uses SHA-256 hash chaining to derive a reproducible, tamper-proof shuffle.
    """
    sorted_speakers = sorted(set(s.strip() for s in speakers if s.strip()))
    if not sorted_speakers:
        return []

    # Derive integer seed from SHA-256 of seed_str
    seed_hash = hashlib.sha256(seed_str.encode("utf-8")).digest()
    seed_int = int.from_bytes(seed_hash[:8], byteorder="big")

    rng = random.Random(seed_int)
    shuffled = list(sorted_speakers)
    rng.shuffle(shuffled)
    return shuffled


# ---------------------------------------------------------------------------
# CLI Command Implementations
# ---------------------------------------------------------------------------

CLERK_MARKERS = ("NO legisla", "NO vota")


def assembly_eligibility(hroot: pathlib.Path, name: str) -> Optional[str]:
    """The refusal reason for `name` acting in an assembly, or None if eligible.

    LIVE-FIRE FINDING, D-001 (T-417): the W-002 charter line for the clerk college reads
    "NO legisla, NO vota, NO tiene stake (AgentCity clerk constraint)" and NOTHING enforced
    it -- a proposer, three sponsors and three ballots came from clerk-named identities and
    the dossier concluded in 71 seconds. A charter constraint nobody enforces mechanically
    is prose. Two rules, both keyed to the roster the warrant actually populated:

      UNISSUED NAMES DO NOT ACT. D-001's voters (`clerk-relator` and friends) were not even
      issued names -- the real clerk seats are `fed-*`. A name that holds no seat has no
      standing to propose, sponsor, or vote (W-002; PR-023: a name exists only inside a
      warrant).

      CLERK SEATS DO NOT LEGISLATE. A name seated in a colegiado whose DECLARED charter
      carries the clerk markers is refused. The markers are read from the roster's own
      charter text rather than from a hardcoded college name, so a future clerk college
      under another name is caught the day it is declared, and a college that drops the
      constraint from its charter stops being treated as one.

    BOOTSTRAP: a harness root with no roster.json has no seats to check against, so there
    is no gate -- the same no-flag-day posture as warrant.py enrollment. Every existing
    deliberation test runs in such a root and keeps running.
    """
    roster_path = hroot / "roster.json"
    if not roster_path.exists():
        return None
    try:
        data = json.loads(roster_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return "roster unreadable (%s): refusing every assembly act rather than guessing" % exc
    names = data.get("names", {}) or {}
    if name not in names:
        return ("unissued name: %r holds no seat in the roster; assembly acts are reserved "
                "to issued names (W-002)" % name)
    colegiado = (names[name] or {}).get("colegiado", "")
    colegiados = data.get("colegiados", {}) or {}
    # FAIL CLOSED on a charter that cannot be resolved (T-417 verifier
    # rejection, round 1): the first cut defaulted a missing colegiado to
    # charter="", the clerk markers never matched, and an orphan seat was
    # waved through with no message at all. A name whose declared colegiado
    # is absent from the roster's colegiados dict -- or whose colegiado
    # declares no charter text -- is a roster inconsistency, and an
    # inconsistent roster gets the same posture as an unreadable one:
    # refuse rather than guess.
    if colegiado not in colegiados:
        return ("roster inconsistent: %r declares colegiado %r which does not exist in "
                "the roster; refusing rather than resolving its charter to nothing"
                % (name, colegiado))
    entry = colegiados[colegiado] or {}
    if not isinstance(entry, dict):
        # T-417 verifier round 2, non-blocking finding 2, converted to mechanism:
        # a bare string/list here crashed with AttributeError before. The action
        # still failed (nothing was written), but a crash is not a refusal --
        # same fail-closed posture, now with the reason named.
        return ("roster inconsistent: colegiado %r is not an object; a charter that "
                "cannot be read cannot be checked -- refusing rather than crashing"
                % colegiado)
    charter = entry.get("incentive", "")
    if not charter:
        return ("roster inconsistent: colegiado %r declares no charter text (incentive); "
                "a charter that cannot be read cannot be checked for the clerk "
                "constraint -- refusing rather than guessing" % colegiado)
    if any(marker in charter for marker in CLERK_MARKERS):
        return ("clerk seat: %r sits in colegiado %r whose charter reads %r -- clerks do "
                "not propose, sponsor, or vote (AgentCity constraint, W-002)"
                % (name, colegiado, charter))
    return None


def refuse_ineligible(hroot: pathlib.Path, name: str) -> bool:
    reason = assembly_eligibility(hroot, name)
    if reason:
        print("refused: " + reason, file=sys.stderr)
        return True
    return False


# ---------------------------------------------------------------------------
# T-418: deliberation-integrity guards. D-001 went from open to publish in 71
# seconds with zero recorded discussion, four ballots identical to four
# identical priors, and stamps three days in the FUTURE of the wall clock --
# and none of that was illegal. Three guards, each with the D-001 defect it
# answers:
#
#   1. DISCUSSION EVIDENCE (defect: no deliberation observable). A dossier
#      cannot conclude unless every alternative carries at least one recorded
#      discussion round with non-empty text. Re-validated AT conclude, so a
#      hand-edited empty entry does not count. NOTE on the task title's
#      "duration floor": deliberately NOT a wall-clock threshold -- no such
#      threshold is ratified (the currency.py doctrine), and speed is not the
#      defect; absence of discussion is. 71 fast seconds WITH real discussion
#      per alternative is legal. Zero discussion is not, however slow.
#   2. UNANIMITY FLAG (defect: priors == ballots, four names one mind).
#      Every final ballot identical to its voter's own prior is flagged
#      NO-DELIBERATION-OBSERVED on the record. Flag, not block: unanimity can
#      be honest, and D-17 predicts this pattern rather than proving it.
#   3. FUTURE-STAMP REFUSAL (defect: stamps from 3 days ahead). Any recorded
#      stamp in the dossier beyond the machine clock plus a small skew
#      allowance refuses every WRITE verb. Reads stay open: evidence of a
#      tampered dossier must remain readable. The skew constant absorbs NTP
#      step-backs between same-machine writes; it is an engineering
#      tolerance, not a ratified constitutional threshold -- the boundary it
#      serves ("not from the future") is binary.
# ---------------------------------------------------------------------------

FUTURE_STAMP_SKEW_SECONDS = 300

ISO_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _stamp_leaves(value: Any, path: str = "$") -> List[Tuple[str, str]]:
    """Every (json_path, leaf) in the dossier whose string LOOKS like an ISO
    stamp. Exhaustive recursive walk on purpose: a stamp added by future
    schema growth is scanned the day it appears, not the day someone
    remembers to enroll it in an allow-list."""
    found: List[Tuple[str, str]] = []
    if isinstance(value, str):
        if ISO_STAMP_RE.match(value):
            found.append((path, value))
    elif isinstance(value, dict):
        for k, v in value.items():
            # Scan KEYS as well as values (T-418 verifier finding): a
            # dossier hand-edited to carry a future ISO string as a key --
            # {"2026-09-02T...": "note"} -- would otherwise slip the scan and
            # make the "exhaustive over every leaf" claim false. No legitimate
            # write emits a stamp as a key, so this only ever closes forgery.
            if isinstance(k, str) and ISO_STAMP_RE.match(k):
                found.append(("%s.<key>%s" % (path, k), k))
            found.extend(_stamp_leaves(v, "%s.%s" % (path, k)))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            found.extend(_stamp_leaves(v, "%s[%d]" % (path, i)))
    return found


def future_stamp(dossier: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
    """The first (json_path, stamp, now) recorded beyond the machine clock
    plus skew, or None. An unparseable stamp-looking string is treated as
    future (fail closed): a stamp that cannot be ordered cannot be trusted."""
    now_dt = hc.now_utc()
    now_iso = hc.now_iso()
    for path, leaf in _stamp_leaves(dossier):
        parsed = hc.parse_iso(leaf)
        if parsed is None:
            return (path, leaf, now_iso)
        if (parsed - now_dt).total_seconds() > FUTURE_STAMP_SKEW_SECONDS:
            return (path, leaf, now_iso)
    return None


def refuse_future_stamps(dossier: Dict[str, Any]) -> bool:
    hit = future_stamp(dossier)
    if hit:
        path, leaf, now_iso = hit
        print("refused: future-dated stamp: %s = %r is beyond the machine clock %s "
              "(+%ds skew). A record from the future refuses every write and stays "
              "on disk for audit (T-418; D-001 defect 3)."
              % (path, leaf, now_iso, FUTURE_STAMP_SKEW_SECONDS), file=sys.stderr)
        return True
    return False


def effective_alternatives(dossier: Dict[str, Any]) -> Set[str]:
    """The candidates a conclusion actually decides among: the DECLARED
    alternatives UNION every candidate that appears in a ballot or a prior.

    T-419 round-2 escape: keying the discussion requirement on the mutable
    `alternatives` field alone let an attacker hand-edit it to `[]` after
    voting, so `undiscussed_alternatives` came back vacuously empty and
    conclude waved a zero-discussion docket through. The candidates are ALSO
    written into the ballots the tally runs on, so deriving the set from the
    ballots too means emptying `alternatives` removes nothing that has to be
    discussed. A conclusion with no candidate at all anywhere is malformed and
    refused separately (see cmd_conclude)."""
    alts: Set[str] = set(str(a) for a in (dossier.get("alternatives", []) or []))
    for b in (dossier.get("final_ballots", {}) or {}).values():
        alts.update(str(c) for c in (b or {}).get("ranking", []) or [])
    for p in (dossier.get("priors", {}) or {}).values():
        alts.update(str(c) for c in (p or {}).get("ranking", []) or [])
    return alts


def undiscussed_alternatives(dossier: Dict[str, Any]) -> List[str]:
    """Effective alternatives (see effective_alternatives) with no discussion
    round carrying non-empty text. Membership and text are re-validated here,
    not trusted from write time: a hand-edited empty round, a round re-pointed
    at a nonexistent alternative, or an emptied `alternatives` field counts for
    nothing."""
    alternatives = effective_alternatives(dossier)
    discussed = set()
    for entry in dossier.get("discussion", []) or []:
        if not isinstance(entry, dict):
            continue
        alt = str(entry.get("re", "")).strip()
        text = str(entry.get("text", "")).strip()
        if alt in alternatives and text:
            discussed.add(alt)
    return sorted(a for a in alternatives if a not in discussed)


def unanimity_flag(dossier: Dict[str, Any]) -> bool:
    """True when EVERY final ballot is identical to its voter's own recorded
    prior. A voter with no prior breaks the comparison and the flag does not
    fire: the flag marks 'the discussion changed nothing and nobody arrived
    without a position', which is exactly D-001's shape."""
    ballots = dossier.get("final_ballots", {}) or {}
    priors = dossier.get("priors", {}) or {}
    if not ballots:
        return False
    for voter, ballot in ballots.items():
        prior = priors.get(voter)
        if not isinstance(prior, dict):
            return False
        if list((ballot or {}).get("ranking", [])) != list(prior.get("ranking", [])):
            return False
    return True


def cmd_propose(args) -> int:
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    title = (args.title or "").strip()
    if not title:
        print("refused: --title must be non-empty", file=sys.stderr)
        return 1

    evidence = list(args.evidence or [])
    if not evidence:
        print("refused: --evidence must contain at least one verifiable evidence reference", file=sys.stderr)
        return 1

    proposer = (args.proposer or hc.agent_id()).strip()
    if not proposer:
        print("refused: --proposer must be non-empty", file=sys.stderr)
        return 1
    if refuse_ineligible(hroot, proposer):
        return 1

    task = (args.task or "").strip()
    if not task:
        print("refused: --task must be non-empty", file=sys.stderr)
        return 1

    alternatives = list(args.alternatives or [])
    if len(alternatives) < 2:
        # Default binary proposal alternatives if none specified
        alternatives = ["adopt", "reject"]

    # T-428 item 4: --case links this dossier to a precedent.py case register
    # entry (C-NNN). Only the SHAPE is checked here -- whether the case is
    # actually registered and still open is re-validated at conclude, never
    # trusted from propose time (same posture as every other guard in this
    # module: write-time checks are cheap and shallow, conclude-time checks
    # are authoritative).
    case_id = (args.case or "").strip() or None
    if case_id and not precedent.CASE_ID_RE.match(case_id):
        print(f"refused: --case {case_id!r} is not a valid case id format "
              f"(must match ^C-\\d+$)", file=sys.stderr)
        return 1

    with hc.guarded():
        dossier_id = allocate_dossier_id(delib_dir)
        dossier = {
            "id": dossier_id,
            "title": title,
            "proposer": proposer,
            "issuing_task": task,
            "created_at": hc.now_iso(),
            "status": "proposed",  # proposed -> sponsored -> deliberating -> concluded
            "evidence": evidence,
            "alternatives": alternatives,
            "case": case_id,        # T-428: registered case this dossier decides, or None
            "sponsors": [proposer],  # Proposer is initial sponsor
            "priors": {},            # voter -> ranking
            "speaker_order": [],
            "speaker_seed": None,
            "scheduled_by": None,    # T-428: eligibility-checked --by of `schedule`
            "final_ballots": {},     # voter -> ranking
            "tally_result": None,
            "concluded_by": None,    # T-428: eligibility-checked --by of `conclude`
            "concluded_at": None,
        }
        save_dossier(delib_dir, dossier)

    if args.json:
        print(json.dumps(dossier, indent=2, ensure_ascii=False))
    else:
        print(f"proposed deliberation dossier {dossier_id}: {title}")
        print(f"  Proposer: {proposer}")
        print(f"  Task:     {task}")
        print(f"  Evidence: {', '.join(evidence)}")
        print(f"  Sponsors: 1/{MIN_SPONSORS} (need {MIN_SPONSORS - 1} more sponsors to convene)")
    return 0


def cmd_sponsor(args) -> int:
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    sponsor = (args.by or hc.agent_id()).strip()
    if not sponsor:
        print("refused: --by must specify a valid sponsor name", file=sys.stderr)
        return 1
    if refuse_ineligible(hroot, sponsor):
        return 1

    with hc.guarded():
        try:
            dossier = load_dossier(delib_dir, args.dossier_id)
        except DeliberationError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1

        if refuse_future_stamps(dossier):
            return 1

        if dossier["status"] in ("concluded", "rejected"):
            print(f"refused: dossier {args.dossier_id} is already {dossier['status']}", file=sys.stderr)
            return 1

        sponsors = set(dossier.get("sponsors", []))
        if sponsor in sponsors:
            print(f"refused: {sponsor!r} has already sponsored {args.dossier_id}", file=sys.stderr)
            return 1

        sponsors.add(sponsor)
        dossier["sponsors"] = sorted(sponsors)
        if len(dossier["sponsors"]) >= MIN_SPONSORS and dossier["status"] == "proposed":
            dossier["status"] = "sponsored"

        save_dossier(delib_dir, dossier)

    count = len(dossier["sponsors"])
    status = dossier["status"]
    if args.json:
        print(json.dumps({"dossier": args.dossier_id, "sponsors": dossier["sponsors"], "status": status}, indent=2))
    else:
        print(f"sponsored {args.dossier_id} by {sponsor} (sponsors: {count}/{MIN_SPONSORS}, status={status})")
    return 0


def cmd_prior(args) -> int:
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    voter = (args.voter or hc.agent_id()).strip()
    if not voter:
        print("refused: --voter must be non-empty", file=sys.stderr)
        return 1
    if refuse_ineligible(hroot, voter):
        return 1

    ranking_str = (args.ranking or "").strip()
    if not ranking_str:
        print("refused: --ranking must be non-empty (comma-separated candidate list)", file=sys.stderr)
        return 1
    ranking = [r.strip() for r in ranking_str.split(",") if r.strip()]

    with hc.guarded():
        try:
            dossier = load_dossier(delib_dir, args.dossier_id)
        except DeliberationError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1

        if refuse_future_stamps(dossier):
            return 1

        if dossier["status"] == "concluded":
            print(f"refused: dossier {args.dossier_id} is already concluded", file=sys.stderr)
            return 1

        dossier["priors"][voter] = {
            "ranking": ranking,
            "weight": float(args.weight or 1.0),
            "recorded_at": hc.now_iso()
        }
        save_dossier(delib_dir, dossier)

    print(f"recorded pre-deliberation prior for {voter} on {args.dossier_id}: {'>'.join(ranking)}")
    return 0


def cmd_schedule(args) -> int:
    """T-428 item 1: the gen-8 survey found that `--speakers` was never run
    through `assembly_eligibility` -- a clerk seat or an unissued name could
    be scheduled to speak (and, since `vote` used to accept status
    'sponsored', to vote) even though the same names are refused at
    propose/sponsor/prior/vote/discuss. Every entry of the EFFECTIVE speaker
    list (whether given via --speakers or defaulted from sponsors+priors) is
    now checked, fail closed with the SAME 'roster inconsistent'/'clerk
    seat'/'unissued name' posture as a ballot. Who convened the deliberation
    is also recorded (--by, itself eligibility-checked)."""
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    scheduler = (args.by or hc.agent_id()).strip()
    if not scheduler:
        print("refused: --by must be non-empty", file=sys.stderr)
        return 1
    if refuse_ineligible(hroot, scheduler):
        return 1

    with hc.guarded():
        try:
            dossier = load_dossier(delib_dir, args.dossier_id)
        except DeliberationError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        if refuse_future_stamps(dossier):
            return 1

        # Check 3-sponsor quorum floor
        sponsors = dossier.get("sponsors", [])
        if len(sponsors) < MIN_SPONSORS:
            print(f"refused: 3-sponsor quorum floor not met for {args.dossier_id} "
                  f"(has {len(sponsors)}/{MIN_SPONSORS} sponsors). "
                  f"Nuisance proposals are blocked before scheduling discussion.", file=sys.stderr)
            return 1

        # Determine participant speaker list
        speakers_arg = args.speakers
        if speakers_arg:
            speaker_list = [s.strip() for s in speakers_arg.split(",") if s.strip()]
        else:
            # Default to all sponsors + all prior submitters
            all_participants = set(sponsors)
            all_participants.update(dossier.get("priors", {}).keys())
            speaker_list = sorted(all_participants)

        # T-428 item 1: every scheduled speaker must be eligible to act in
        # the assembly -- same posture as a ballot. Refuse the WHOLE call on
        # the first ineligible entry rather than silently dropping it: a
        # silently-shrunk speaker list is exactly the kind of unobserved
        # change this guard exists to prevent.
        for sp in speaker_list:
            reason = assembly_eligibility(hroot, sp)
            if reason:
                print(f"refused: speaker {sp!r} is not eligible to be scheduled on "
                      f"{args.dossier_id}: {reason}", file=sys.stderr)
                return 1

        if len(speaker_list) < 2:
            print("refused: deliberation requires at least 2 distinct speakers", file=sys.stderr)
            return 1

        seed = (args.seed or f"{dossier['id']}:{dossier['created_at']}:{len(sponsors)}").strip()
        shuffled = compute_deterministic_speaker_order(speaker_list, seed)

        dossier["speaker_order"] = shuffled
        dossier["speaker_seed"] = seed
        dossier["status"] = "deliberating"
        dossier["scheduled_by"] = scheduler
        save_dossier(delib_dir, dossier)

    if args.json:
        print(json.dumps({
            "dossier": args.dossier_id,
            "speaker_order": shuffled,
            "seed": seed,
            "scheduled_by": scheduler,
            "status": "deliberating"
        }, indent=2))
    else:
        print("=" * 60)
        print(f"DELIBERATION SPEAKER SCHEDULE: {args.dossier_id}")
        print("=" * 60)
        print(f"Seed:       {seed}")
        print(f"Scheduled by: {scheduler}")
        print("-" * 60)
        for idx, speaker in enumerate(shuffled, start=1):
            print(f"  Speaker {idx}: {speaker}")
        print("=" * 60)
    return 0


def cmd_discuss(args) -> int:
    """T-418 guard 1's write side: record one discussion round, attributed and
    non-empty, against a named alternative of a CONVENED deliberation."""
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    by = (args.by or hc.agent_id()).strip()
    if not by:
        print("refused: --by must be non-empty", file=sys.stderr)
        return 1
    if refuse_ineligible(hroot, by):
        return 1

    alt = (args.re_alternative or "").strip()
    if not alt:
        print("refused: --re must name the alternative under discussion", file=sys.stderr)
        return 1
    text = (args.text or "").strip()
    if not text:
        print("refused: --text must carry non-empty discussion content; an empty "
              "round is not deliberation (T-418)", file=sys.stderr)
        return 1

    with hc.guarded():
        try:
            dossier = load_dossier(delib_dir, args.dossier_id)
        except DeliberationError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        if refuse_future_stamps(dossier):
            return 1

        if dossier["status"] != "deliberating":
            print(f"refused: dossier {args.dossier_id} is in status '{dossier['status']}'; "
                  "discussion happens inside a convened deliberation (schedule first)",
                  file=sys.stderr)
            return 1
        # Accept any EFFECTIVE alternative (declared or named in a prior), so a
        # candidate that will require discussion at conclude can always be
        # discussed -- no deadlock -- while a genuinely unrelated string is
        # still refused.
        eff = effective_alternatives(dossier)
        if alt not in eff:
            print(f"refused: {alt!r} is not an alternative of {args.dossier_id} "
                  f"(alternatives: {', '.join(sorted(eff))})",
                  file=sys.stderr)
            return 1

        rounds = dossier.setdefault("discussion", [])
        rounds.append({"by": by, "re": alt, "text": text, "at": hc.now_iso()})
        save_dossier(delib_dir, dossier)

    print(f"recorded discussion round {len(rounds)} by {by} re {alt!r} on {args.dossier_id}")
    return 0


def cmd_vote(args) -> int:
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    voter = (args.voter or hc.agent_id()).strip()
    if not voter:
        print("refused: --voter must be non-empty", file=sys.stderr)
        return 1
    if refuse_ineligible(hroot, voter):
        return 1

    ranking_str = (args.ranking or "").strip()
    if not ranking_str:
        print("refused: --ranking must be non-empty", file=sys.stderr)
        return 1
    ranking = [r.strip() for r in ranking_str.split(",") if r.strip()]

    with hc.guarded():
        try:
            dossier = load_dossier(delib_dir, args.dossier_id)
        except DeliberationError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1

        if refuse_future_stamps(dossier):
            return 1

        # T-428 item 2: a ballot is only legal inside a CONVENED deliberation.
        # The prior code also accepted status 'sponsored' -- a ballot cast
        # before `schedule` ever ran, with no speaker order and no
        # opportunity to discuss. That is D-001's shape (vote before
        # convene), so it is refused with a named reason, not silently
        # accepted.
        if dossier["status"] != "deliberating":
            print(f"refused: dossier {args.dossier_id} is in status '{dossier['status']}', "
                  f"not open for voting; a ballot is only accepted inside a convened "
                  f"deliberation (run `schedule` first) (T-428)", file=sys.stderr)
            return 1

        dossier["final_ballots"][voter] = {
            "ranking": ranking,
            "weight": float(args.weight or 1.0),
            "voted_at": hc.now_iso()
        }
        save_dossier(delib_dir, dossier)

    print(f"recorded final ballot for {voter} on {args.dossier_id}: {'>'.join(ranking)}")
    return 0


def cmd_conclude(args) -> int:
    """T-428 item 3: `conclude` now takes --by (eligibility-checked,
    non-clerk -- same `assembly_eligibility` gate as every other assembly
    act) and records `concluded_by`. Item 4: if the dossier carries a `case`
    (set at propose via --case), conclude re-validates it against
    precedent.py's live case register -- not registered, or registered but
    no longer 'open', both refuse. Re-validated here rather than trusted
    from propose time: the case could be disposed by another act, or never
    registered at all, in the interval between propose and conclude."""
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    concluder = (args.by or hc.agent_id()).strip()
    if not concluder:
        print("refused: --by must be non-empty", file=sys.stderr)
        return 1
    if refuse_ineligible(hroot, concluder):
        return 1

    with hc.guarded():
        try:
            dossier = load_dossier(delib_dir, args.dossier_id)
        except DeliberationError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1
        if refuse_future_stamps(dossier):
            return 1

        # T-428 item 4: case linkage, re-validated against the live register.
        case_id = dossier.get("case")
        if case_id:
            case_rec = precedent.load_case(hroot, case_id)
            if case_rec is None:
                print(f"refused: {args.dossier_id} names case {case_id!r} which is not "
                      f"registered in {precedent.cases_dir(hroot)}; a docket cannot "
                      f"conclude against an unregistered case (T-428; call "
                      f"'precedent.py case open' first)", file=sys.stderr)
                return 1
            if case_rec.get("status") != "open":
                disp = case_rec.get("disposal") or {}
                print(f"refused: {args.dossier_id} names case {case_id!r} which is not open "
                      f"(status={case_rec.get('status')!r}, disposed by "
                      f"{disp.get('verb', 'unknown')}); a docket cannot conclude against a "
                      f"case that is no longer open (T-428)", file=sys.stderr)
                return 1

        ballots_dict = dossier.get("final_ballots", {})
        if not ballots_dict:
            print(f"refused: no final ballots recorded for {args.dossier_id}", file=sys.stderr)
            return 1

        # Guard 1: discussion evidence, re-validated here (never trusted from
        # write time). Every alternative needs at least one non-empty round.
        # Defense in depth (T-419 round 2): a conclusion that decides among no
        # candidate at all -- alternatives emptied AND no ballot names one --
        # is malformed, not a pass. Refuse rather than conclude on nothing.
        if not effective_alternatives(dossier):
            print(f"refused: {args.dossier_id} has no alternatives to decide among "
                  f"(the alternatives field is empty and no ballot names a candidate); "
                  f"a conclusion on nothing is malformed (T-418)", file=sys.stderr)
            return 1
        missing = undiscussed_alternatives(dossier)
        if missing:
            print(f"refused: no discussion recorded for alternative(s) "
                  f"{', '.join(repr(a) for a in missing)} on {args.dossier_id}; a "
                  f"deliberation concludes only after each alternative is discussed "
                  f"(T-418; use `discuss --re <alt> --text ...`)", file=sys.stderr)
            return 1

        ballots_list = [
            {"voter": v, "ranking": b["ranking"], "weight": b.get("weight", 1.0)}
            for v, b in ballots_dict.items()
        ]

        tally = condorcet.aggregate_votes(ballots_list, method=args.method or "schulze")
        dossier["tally_result"] = tally
        dossier["status"] = "concluded"
        dossier["concluded_at"] = hc.now_iso()
        dossier["concluded_by"] = concluder

        # Guard 2: flag, not block. Unanimity can be honest, so the record
        # carries the observation and conclude still succeeds.
        no_delib = unanimity_flag(dossier)
        dossier["deliberation_flag"] = (
            "NO-DELIBERATION-OBSERVED" if no_delib else "deliberation-observed")
        save_dossier(delib_dir, dossier)

    if args.json:
        print(json.dumps(dossier, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print(f"DELIBERATION CONCLUDED: {args.dossier_id}")
        print("=" * 60)
        print(f"Winner:           {tally['winner']}")
        print(f"Condorcet Winner: {tally['condorcet_winner'] or 'None (Cycle)'}")
        print(f"Total Ballots:    {tally['total_ballots']}")
        print(f"Deliberation:     {dossier['deliberation_flag']}")
        print(f"Concluded by:     {concluder}")
        print("-" * 60)
        print("Final Ranking:")
        for r in tally["ranking"]:
            print(f"  #{r['rank']} {r['candidate']:<20} (wins: {r['wins']}, losses: {r['losses']})")
        print("=" * 60)
    return 0


def cmd_show(args) -> int:
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    try:
        dossier = load_dossier(delib_dir, args.dossier_id)
    except DeliberationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(dossier, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print(f"DELIBERATION DOSSIER: {dossier['id']} [{dossier['status'].upper()}]")
        print("=" * 60)
        print(f"Title:     {dossier['title']}")
        print(f"Proposer:  {dossier['proposer']} (Task: {dossier['issuing_task']})")
        print(f"Evidence:  {', '.join(dossier['evidence'])}")
        print(f"Sponsors:  {', '.join(dossier['sponsors'])} ({len(dossier['sponsors'])}/{MIN_SPONSORS})")
        if dossier.get("case"):
            print(f"Case:      {dossier['case']}")
        if dossier.get("speaker_order"):
            print(f"Speakers:  {' -> '.join(dossier['speaker_order'])}")
        if dossier.get("scheduled_by"):
            print(f"Scheduled by: {dossier['scheduled_by']}")
        rounds = dossier.get("discussion", []) or []
        if rounds:
            print(f"Discussion: {len(rounds)} round(s) on "
                  f"{len(set(r.get('re') for r in rounds if isinstance(r, dict)))} "
                  f"alternative(s)")
        if dossier.get("tally_result"):
            print(f"Winner:    {dossier['tally_result']['winner']}")
        if dossier.get("deliberation_flag"):
            print(f"Flag:      {dossier['deliberation_flag']}")
        if dossier.get("concluded_by"):
            print(f"Concluded by: {dossier['concluded_by']}")
        print("=" * 60)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Deliberation protocol with 3-sponsor quorum & randomized speaker order (A-3)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    # propose
    p_prop = sub.add_parser("propose", help="propose a new assembly deliberation dossier")
    p_prop.add_argument("--title", required=True, help="title of the proposal")
    p_prop.add_argument("--evidence", action="append", required=True, help="evidence references (>= 1 required)")
    p_prop.add_argument("--proposer", default=None, help="proposing agent identity")
    p_prop.add_argument("--task", required=True, help="issuing task ID, T-NNN")
    p_prop.add_argument("--alternatives", action="append", default=None, help="options to rank (defaults to adopt, reject)")
    p_prop.add_argument("--case", default=None,
                        help="registered case id, C-NNN (T-428): links this dossier to "
                             "precedent.py's case register. Optional; re-validated as "
                             "registered-and-open at conclude, not here.")
    p_prop.add_argument("--harness-root", dest="harness_root", default=None)
    p_prop.add_argument("--json", action="store_true", default=False)
    p_prop.set_defaults(func=cmd_propose)

    # sponsor
    p_spon = sub.add_parser("sponsor", help="sponsor an existing proposal (3 required to convene)")
    p_spon.add_argument("dossier_id", metavar="D-NNN")
    p_spon.add_argument("--by", default=None, help="sponsoring agent identity")
    p_spon.add_argument("--harness-root", dest="harness_root", default=None)
    p_spon.add_argument("--json", action="store_true", default=False)
    p_spon.set_defaults(func=cmd_sponsor)

    # prior
    p_prior = sub.add_parser("prior", help="submit pre-deliberation straw poll / Bayesian prior")
    p_prior.add_argument("dossier_id", metavar="D-NNN")
    p_prior.add_argument("--voter", default=None, help="voter identity")
    p_prior.add_argument("--ranking", required=True, help="comma-separated ranked alternatives (A,B,C)")
    p_prior.add_argument("--weight", type=float, default=1.0, help="voter weight")
    p_prior.add_argument("--harness-root", dest="harness_root", default=None)
    p_prior.set_defaults(func=cmd_prior)

    # schedule
    p_sched = sub.add_parser("schedule", help="convene deliberation and generate deterministic speaker order")
    p_sched.add_argument("dossier_id", metavar="D-NNN")
    p_sched.add_argument("--speakers", default=None, help="comma-separated speaker identities")
    p_sched.add_argument("--seed", default=None, help="randomization seed (defaults to SHA-256 derived seed)")
    p_sched.add_argument("--by", default=None,
                         help="scheduling agent identity (T-428, eligibility-checked)")
    p_sched.add_argument("--harness-root", dest="harness_root", default=None)
    p_sched.add_argument("--json", action="store_true", default=False)
    p_sched.set_defaults(func=cmd_schedule)

    # discuss
    p_disc = sub.add_parser("discuss", help="record one discussion round on a convened deliberation (T-418)")
    p_disc.add_argument("dossier_id", metavar="D-NNN")
    p_disc.add_argument("--by", default=None, help="discussant identity")
    p_disc.add_argument("--re", dest="re_alternative", required=True, help="alternative under discussion")
    p_disc.add_argument("--text", required=True, help="non-empty discussion content")
    p_disc.add_argument("--harness-root", dest="harness_root", default=None)
    p_disc.set_defaults(func=cmd_discuss)

    # vote
    p_vote = sub.add_parser("vote", help="submit post-deliberation ranked ballot")
    p_vote.add_argument("dossier_id", metavar="D-NNN")
    p_vote.add_argument("--voter", default=None, help="voter identity")
    p_vote.add_argument("--ranking", required=True, help="comma-separated ranked alternatives")
    p_vote.add_argument("--weight", type=float, default=1.0, help="voter weight")
    p_vote.add_argument("--harness-root", dest="harness_root", default=None)
    p_vote.set_defaults(func=cmd_vote)

    # conclude
    p_conc = sub.add_parser("conclude", help="tally final votes using Condorcet engine and conclude deliberation")
    p_conc.add_argument("dossier_id", metavar="D-NNN")
    p_conc.add_argument("--method", choices=["schulze", "copeland"], default="schulze")
    p_conc.add_argument("--by", default=None,
                        help="concluding agent identity (T-428, eligibility-checked, non-clerk)")
    p_conc.add_argument("--harness-root", dest="harness_root", default=None)
    p_conc.add_argument("--json", action="store_true", default=False)
    p_conc.set_defaults(func=cmd_conclude)

    # show
    p_show = sub.add_parser("show", help="show dossier details")
    p_show.add_argument("dossier_id", metavar="D-NNN")
    p_show.add_argument("--harness-root", dest="harness_root", default=None)
    p_show.add_argument("--json", action="store_true", default=False)
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
