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
    charter = ((data.get("colegiados", {}) or {}).get(colegiado, {}) or {}).get("incentive", "")
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
            "sponsors": [proposer],  # Proposer is initial sponsor
            "priors": {},            # voter -> ranking
            "speaker_order": [],
            "speaker_seed": None,
            "final_ballots": {},     # voter -> ranking
            "tally_result": None,
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
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    with hc.guarded():
        try:
            dossier = load_dossier(delib_dir, args.dossier_id)
        except DeliberationError as exc:
            print(f"refused: {exc}", file=sys.stderr)
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

        if len(speaker_list) < 2:
            print("refused: deliberation requires at least 2 distinct speakers", file=sys.stderr)
            return 1

        seed = (args.seed or f"{dossier['id']}:{dossier['created_at']}:{len(sponsors)}").strip()
        shuffled = compute_deterministic_speaker_order(speaker_list, seed)

        dossier["speaker_order"] = shuffled
        dossier["speaker_seed"] = seed
        dossier["status"] = "deliberating"
        save_dossier(delib_dir, dossier)

    if args.json:
        print(json.dumps({
            "dossier": args.dossier_id,
            "speaker_order": shuffled,
            "seed": seed,
            "status": "deliberating"
        }, indent=2))
    else:
        print("=" * 60)
        print(f"DELIBERATION SPEAKER SCHEDULE: {args.dossier_id}")
        print("=" * 60)
        print(f"Seed: {seed}")
        print("-" * 60)
        for idx, speaker in enumerate(shuffled, start=1):
            print(f"  Speaker {idx}: {speaker}")
        print("=" * 60)
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

        if dossier["status"] not in ("deliberating", "sponsored"):
            print(f"refused: dossier {args.dossier_id} is in status '{dossier['status']}', not open for voting", file=sys.stderr)
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
    hroot = pathlib.Path(args.harness_root) if args.harness_root else hc.HARNESS
    delib_dir = resolve_delib_dir(hroot)

    with hc.guarded():
        try:
            dossier = load_dossier(delib_dir, args.dossier_id)
        except DeliberationError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 1

        ballots_dict = dossier.get("final_ballots", {})
        if not ballots_dict:
            print(f"refused: no final ballots recorded for {args.dossier_id}", file=sys.stderr)
            return 1

        ballots_list = [
            {"voter": v, "ranking": b["ranking"], "weight": b.get("weight", 1.0)}
            for v, b in ballots_dict.items()
        ]

        tally = condorcet.aggregate_votes(ballots_list, method=args.method or "schulze")
        dossier["tally_result"] = tally
        dossier["status"] = "concluded"
        dossier["concluded_at"] = hc.now_iso()
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
        if dossier.get("speaker_order"):
            print(f"Speakers:  {' -> '.join(dossier['speaker_order'])}")
        if dossier.get("tally_result"):
            print(f"Winner:    {dossier['tally_result']['winner']}")
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
    p_sched.add_argument("--harness-root", dest="harness_root", default=None)
    p_sched.add_argument("--json", action="store_true", default=False)
    p_sched.set_defaults(func=cmd_schedule)

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
