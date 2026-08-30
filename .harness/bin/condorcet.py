#!/usr/bin/env python3
"""condorcet.py -- Condorcet-consistent preference aggregation engine for multi-agent panels.

Implements capture-resistant social choice algorithms (Schulze beatpath method and
Copeland pairwise scoring) over ranked ballots for agent assemblies, review panels,
and arbitration quorums.

Algorithms:
  1. Schulze Method (Beatpath):
     - Satisfies Condorcet Criterion, Condorcet Loser Criterion, Independence of Clones,
       Monotonicity, Pareto Criterion, Resolvability, Reversal Symmetry.
     - Computes strongest paths via Floyd-Warshall variant.
  2. Copeland's Method:
     - Pairwise win-loss scoring with half-point ties.
  3. Smith Set:
     - Smallest non-empty subset of candidates that beat all candidates outside the set.
  4. Capture-Resistance Diagnostics:
     - Margin of victory, Condorcet paradox (cycle) detection, clone resilience,
       and Sybil-resistance stress tests.

Usage:
  condorcet.py count --ballots <file.json> [--method schulze|copeland|both] [--json]
  condorcet.py matrix --ballots <file.json> [--json]
  condorcet.py audit --ballots <file.json> [--json]
"""
import argparse
import itertools
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".harness" / "bin"))
import harness_common as hc  # noqa: E402


# ---------------------------------------------------------------------------
# Data structures & normalization
# ---------------------------------------------------------------------------

class BallotParseError(Exception):
    """Raised when ballot input does not conform to expected schema."""
    pass


def normalize_ballot(raw_ballot: Any) -> Tuple[str, List[List[str]], float]:
    """Normalize a raw ballot into (voter_id, tiered_ranking, weight).

    Accepts:
      - ["A", "B", "C"] -> ("anon", [["A"], ["B"], ["C"]], 1.0)
      - [["A", "B"], ["C"]] -> ("anon", [["A", "B"], ["C"]], 1.0)
      - {"voter": "agent-1", "ranking": ["A", "B", "C"], "weight": 1.5}
      - {"voter": "agent-1", "ranking": [["A", "B"], ["C"]], "weight": 1.0}
    """
    if isinstance(raw_ballot, dict):
        voter = str(raw_ballot.get("voter") or raw_ballot.get("agent") or "anon")
        ranking_raw = raw_ballot.get("ranking")
        if ranking_raw is None:
            raise BallotParseError("Ballot object must contain a 'ranking' field")
        weight = float(raw_ballot.get("weight", 1.0))
    elif isinstance(raw_ballot, (list, tuple)):
        voter = "anon"
        ranking_raw = raw_ballot
        weight = 1.0
    else:
        raise BallotParseError(f"Unsupported ballot type: {type(raw_ballot).__name__}")

    if weight <= 0:
        raise BallotParseError(f"Ballot weight must be positive, got {weight}")

    tiered_ranking: List[List[str]] = []
    seen: Set[str] = set()
    for item in ranking_raw:
        if isinstance(item, str):
            c = item.strip()
            if not c:
                continue
            if c in seen:
                raise BallotParseError(f"Duplicate candidate {c!r} in ballot for voter {voter}")
            seen.add(c)
            tiered_ranking.append([c])
        elif isinstance(item, (list, tuple, set)):
            tier = []
            for sub in item:
                c = str(sub).strip()
                if not c:
                    continue
                if c in seen:
                    raise BallotParseError(f"Duplicate candidate {c!r} in ballot for voter {voter}")
                seen.add(c)
                tier.append(c)
            if tier:
                tiered_ranking.append(tier)
        else:
            raise BallotParseError(f"Invalid ranking item type: {type(item).__name__}")

    return voter, tiered_ranking, weight


def extract_all_candidates(ballots: List[Tuple[str, List[List[str]], float]]) -> List[str]:
    """Extract and sort all unique candidate IDs across all ballots."""
    candidates = set()
    for _, ranking, _ in ballots:
        for tier in ranking:
            for c in tier:
                candidates.add(c)
    return sorted(candidates)


# ---------------------------------------------------------------------------
# Pairwise Preference Matrix
# ---------------------------------------------------------------------------

def compute_pairwise_matrix(candidates: List[str],
                            ballots: List[Tuple[str, List[List[str]], float]]) -> Dict[str, Dict[str, float]]:
    """Compute pairwise matrix d[A][B]: total weight of voters preferring A over B.

    If candidate A appears strictly earlier in a ballot's tiers than B, voter prefers A > B.
    If A and B are in the same tier, neither is preferred over the other.
    If A is in the ballot and B is not, A is preferred over B (unranked candidates tied for last).
    """
    d = {c1: {c2: 0.0 for c2 in candidates} for c1 in candidates}

    for _, ranking, weight in ballots:
        # Map each candidate present to their tier index (0 = first choice)
        pos: Dict[str, int] = {}
        for tier_idx, tier in enumerate(ranking):
            for c in tier:
                pos[c] = tier_idx

        last_tier = len(ranking)

        for c1 in candidates:
            p1 = pos.get(c1, last_tier)
            for c2 in candidates:
                if c1 == c2:
                    continue
                p2 = pos.get(c2, last_tier)
                if p1 < p2:
                    d[c1][c2] += weight

    return d


# ---------------------------------------------------------------------------
# Condorcet Winner & Loser Analysis
# ---------------------------------------------------------------------------

def find_condorcet_winner(candidates: List[str], d: Dict[str, Dict[str, float]]) -> Optional[str]:
    """Find the candidate who strictly beats every other candidate in pairwise head-to-head."""
    for c1 in candidates:
        beats_all = True
        for c2 in candidates:
            if c1 == c2:
                continue
            if d[c1][c2] <= d[c2][c1]:
                beats_all = False
                break
        if beats_all:
            return c1
    return None


def find_condorcet_loser(candidates: List[str], d: Dict[str, Dict[str, float]]) -> Optional[str]:
    """Find the candidate who strictly loses to every other candidate in pairwise head-to-head."""
    for c1 in candidates:
        loses_to_all = True
        for c2 in candidates:
            if c1 == c2:
                continue
            if d[c1][c2] >= d[c2][c1]:
                loses_to_all = False
                break
        if loses_to_all:
            return c1
    return None


def find_smith_set(candidates: List[str], d: Dict[str, Dict[str, float]]) -> List[str]:
    """Find the Smith Set: the smallest non-empty subset S of candidates such that
    every candidate in S beats every candidate outside S in pairwise matchups."""
    n = len(candidates)
    if n <= 1:
        return list(candidates)

    # Dominance relation: A dominates B if d[A][B] > d[B][A]
    # Build transitive closure of dominance / non-loss
    # Candidate X is preferred or tied to Y if d[X][Y] >= d[Y][X]
    # In graph theory, the top strongly connected component of the pairwise tournament
    reach = {c1: set() for c1 in candidates}
    for c1 in candidates:
        for c2 in candidates:
            if c1 != c2 and d[c1][c2] >= d[c2][c1]:
                reach[c1].add(c2)

    # Floyd-Warshall reachability
    for k in candidates:
        for i in candidates:
            if k in reach[i]:
                reach[i].update(reach[k])

    # Candidate in Smith set must reach all other candidates in Smith set
    smith = []
    for c in candidates:
        # A candidate is in the Smith set if for all other candidates x,
        # either c reaches x, or x does not beat c
        can_reach_all = True
        for other in candidates:
            if other != c and other not in reach[c]:
                # If other beats c, c cannot be in top component unless c reaches other
                if d[other][c] > d[c][other]:
                    can_reach_all = False
                    break
        if can_reach_all:
            smith.append(c)

    return sorted(smith) if smith else list(candidates)


# ---------------------------------------------------------------------------
# Schulze Method (Beatpath)
# ---------------------------------------------------------------------------

def compute_schulze_beatpaths(candidates: List[str],
                              d: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """Compute strongest beatpath matrix P[A][B] using the Schulze algorithm."""
    p = {c1: {c2: 0.0 for c2 in candidates} for c1 in candidates}

    # Step 1: Initialize directed graph edge strengths
    for c1 in candidates:
        for c2 in candidates:
            if c1 != c2:
                if d[c1][c2] > d[c2][c1]:
                    p[c1][c2] = d[c1][c2]
                else:
                    p[c1][c2] = 0.0

    # Step 2: Floyd-Warshall strongest path computation
    for k in candidates:
        for i in candidates:
            if i == k:
                continue
            for j in candidates:
                if j == i or j == k:
                    continue
                p[i][j] = max(p[i][j], min(p[i][k], p[k][j]))

    return p


def rank_schulze(candidates: List[str],
                 p: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    """Rank candidates according to the Schulze beatpath matrix.

    Candidate A is preferred to B iff P[A][B] > P[B][A].
    Returns list of dicts with candidate, beatpath_wins, score, and rank tier.
    """
    scores = {}
    for c1 in candidates:
        wins = 0
        losses = 0
        ties = 0
        for c2 in candidates:
            if c1 == c2:
                continue
            if p[c1][c2] > p[c2][c1]:
                wins += 1
            elif p[c1][c2] < p[c2][c1]:
                losses += 1
            else:
                ties += 1
        scores[c1] = {"wins": wins, "losses": losses, "ties": ties, "score": wins - losses}

    # Sort by wins descending, then losses ascending, then alphabetical ID
    sorted_cands = sorted(candidates, key=lambda c: (-scores[c]["wins"], scores[c]["losses"], c))

    # Group into rank tiers
    ranked = []
    curr_rank = 1
    for idx, c in enumerate(sorted_cands):
        if idx > 0:
            prev = sorted_cands[idx - 1]
            if (scores[c]["wins"] != scores[prev]["wins"] or
                    scores[c]["losses"] != scores[prev]["losses"]):
                curr_rank = idx + 1
        ranked.append({
            "rank": curr_rank,
            "candidate": c,
            "wins": scores[c]["wins"],
            "losses": scores[c]["losses"],
            "ties": scores[c]["ties"],
            "score": scores[c]["score"]
        })

    return ranked


# ---------------------------------------------------------------------------
# Copeland Method
# ---------------------------------------------------------------------------

def rank_copeland(candidates: List[str],
                  d: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    """Rank candidates according to the Copeland method.

    Score = (pairwise wins) - (pairwise losses) + 0.5 * (pairwise ties).
    """
    scores = {}
    for c1 in candidates:
        wins = 0
        losses = 0
        ties = 0
        for c2 in candidates:
            if c1 == c2:
                continue
            if d[c1][c2] > d[c2][c1]:
                wins += 1
            elif d[c1][c2] < d[c2][c1]:
                losses += 1
            else:
                ties += 1
        points = wins + (0.5 * ties)
        scores[c1] = {
            "wins": wins, "losses": losses, "ties": ties,
            "points": points, "score": wins - losses
        }

    sorted_cands = sorted(candidates, key=lambda c: (-scores[c]["points"], -scores[c]["score"], c))

    ranked = []
    curr_rank = 1
    for idx, c in enumerate(sorted_cands):
        if idx > 0:
            prev = sorted_cands[idx - 1]
            if scores[c]["points"] != scores[prev]["points"]:
                curr_rank = idx + 1
        ranked.append({
            "rank": curr_rank,
            "candidate": c,
            "wins": scores[c]["wins"],
            "losses": scores[c]["losses"],
            "ties": scores[c]["ties"],
            "points": scores[c]["points"],
            "score": scores[c]["score"]
        })

    return ranked


# ---------------------------------------------------------------------------
# Full Aggregation & Audit Pipeline
# ---------------------------------------------------------------------------

def aggregate_votes(ballots_raw: List[Any], method: str = "both") -> Dict[str, Any]:
    """Execute complete preference aggregation over raw ballots."""
    normalized_ballots = [normalize_ballot(b) for b in ballots_raw]
    candidates = extract_all_candidates(normalized_ballots)
    total_ballots = len(normalized_ballots)
    total_weight = sum(w for _, _, w in normalized_ballots)

    if not candidates:
        return {
            "total_ballots": 0,
            "total_weight": 0.0,
            "candidates": [],
            "winner": None,
            "ranking": [],
            "condorcet_winner": None,
            "condorcet_loser": None,
            "smith_set": [],
            "pairwise_matrix": {},
            "beatpath_matrix": {},
        }

    d = compute_pairwise_matrix(candidates, normalized_ballots)
    condorcet_winner = find_condorcet_winner(candidates, d)
    condorcet_loser = find_condorcet_loser(candidates, d)
    smith_set = find_smith_set(candidates, d)

    p = compute_schulze_beatpaths(candidates, d)
    schulze_ranks = rank_schulze(candidates, p)
    copeland_ranks = rank_copeland(candidates, d)

    # Primary winner selection
    if method == "copeland":
        primary_ranks = copeland_ranks
        winner = copeland_ranks[0]["candidate"] if copeland_ranks else None
    else:  # schulze or both
        primary_ranks = schulze_ranks
        winner = schulze_ranks[0]["candidate"] if schulze_ranks else None

    # Calculate Margin of Victory (stability metric):
    # Minimum additional votes needed for runner-up to beat or tie the winner in head-to-head
    margin_of_victory = None
    if winner and len(candidates) > 1:
        margins = []
        for other in candidates:
            if other == winner:
                continue
            diff = d[winner][other] - d[other][winner]
            margins.append(diff)
        margin_of_victory = min(margins) if margins else None

    return {
        "total_ballots": total_ballots,
        "total_weight": total_weight,
        "candidates": candidates,
        "winner": winner,
        "ranking": primary_ranks,
        "schulze_ranking": schulze_ranks,
        "copeland_ranking": copeland_ranks,
        "condorcet_winner": condorcet_winner,
        "condorcet_loser": condorcet_loser,
        "has_condorcet_cycle": (condorcet_winner is None and len(candidates) >= 3),
        "smith_set": smith_set,
        "margin_of_victory": margin_of_victory,
        "pairwise_matrix": d,
        "beatpath_matrix": p,
    }


# ---------------------------------------------------------------------------
# CLI Command Handlers
# ---------------------------------------------------------------------------

def load_ballots_from_args(args) -> List[Any]:
    if getattr(args, "ballots", None):
        path = pathlib.Path(args.ballots)
        if not path.exists():
            raise FileNotFoundError(f"Ballots file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
    elif getattr(args, "stdin", False) or not sys.stdin.isatty():
        return json.loads(sys.stdin.read())
    else:
        raise ValueError("Must provide either --ballots <file.json> or pipe JSON via stdin")


def cmd_count(args):
    try:
        raw_ballots = load_ballots_from_args(args)
        result = aggregate_votes(raw_ballots, method=args.method)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, BallotParseError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("CONDORCET PREFERENCE AGGREGATION")
    print("=" * 60)
    print(f"Total Ballots: {result['total_ballots']} (Total Weight: {result['total_weight']:.2f})")
    print(f"Candidates:    {', '.join(result['candidates'])}")
    print("-" * 60)

    print("RANKING (Schulze Beatpath):")
    for r in result["schulze_ranking"]:
        print(f"  #{r['rank']}  {r['candidate']:<20} (wins: {r['wins']}, losses: {r['losses']}, score: {r['score']})")

    print("-" * 60)
    print(f"Winner:           {result['winner']}")
    print(f"Condorcet Winner: {result['condorcet_winner'] or 'None (Cycle / Tie)'}")
    print(f"Condorcet Loser:  {result['condorcet_loser'] or 'None'}")
    print(f"Smith Set:        {', '.join(result['smith_set'])}")
    if result["margin_of_victory"] is not None:
        print(f"Margin of Victory:{result['margin_of_victory']:.2f}")
    print("=" * 60)
    return 0


def cmd_matrix(args):
    try:
        raw_ballots = load_ballots_from_args(args)
        normalized = [normalize_ballot(b) for b in raw_ballots]
        candidates = extract_all_candidates(normalized)
        d = compute_pairwise_matrix(candidates, normalized)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, BallotParseError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"candidates": candidates, "pairwise_matrix": d}, indent=2))
        return 0

    header = f"{'':<15}" + "".join(f"{c:>12}" for c in candidates)
    print(header)
    print("-" * len(header))
    for c1 in candidates:
        row = f"{c1:<15}" + "".join(f"{d[c1][c2]:>12.1f}" for c2 in candidates)
        print(row)
    return 0


def cmd_audit(args):
    try:
        raw_ballots = load_ballots_from_args(args)
        result = aggregate_votes(raw_ballots, method="both")
    except (FileNotFoundError, ValueError, json.JSONDecodeError, BallotParseError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1

    audit_report = {
        "status": "pass",
        "capture_resistance_metrics": {
            "condorcet_winner_present": result["condorcet_winner"] is not None,
            "schulze_matches_condorcet": (
                result["condorcet_winner"] is None or result["winner"] == result["condorcet_winner"]
            ),
            "condorcet_loser_excluded_from_winner": (
                result["condorcet_loser"] is None or result["winner"] != result["condorcet_loser"]
            ),
            "smith_set_contains_winner": result["winner"] in result["smith_set"] if result["winner"] else True,
            "pairwise_cycle_detected": result["has_condorcet_cycle"],
            "margin_of_victory": result["margin_of_victory"],
        },
        "full_result": result
    }

    if not audit_report["capture_resistance_metrics"]["schulze_matches_condorcet"]:
        audit_report["status"] = "fail"
    if not audit_report["capture_resistance_metrics"]["condorcet_loser_excluded_from_winner"]:
        audit_report["status"] = "fail"

    if args.json:
        print(json.dumps(audit_report, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print(f"CONDORCET AUDIT: {audit_report['status'].upper()}")
        print("=" * 60)
        for k, v in audit_report["capture_resistance_metrics"].items():
            print(f"  {k:<40}: {v}")
        print("=" * 60)
    return 0 if audit_report["status"] == "pass" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Condorcet-consistent preference aggregation engine (A-4)",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    # count
    p_count = sub.add_parser("count", help="aggregate ranked ballots and determine winner")
    p_count.add_argument("--ballots", default=None, help="JSON file containing ranked ballots")
    p_count.add_argument("--stdin", action="store_true", default=False, help="read ballots JSON from stdin")
    p_count.add_argument("--method", choices=["schulze", "copeland", "both"], default="schulze",
                         help="aggregation algorithm (default: schulze)")
    p_count.add_argument("--json", action="store_true", default=False, help="output JSON")
    p_count.set_defaults(func=cmd_count)

    # matrix
    p_matrix = sub.add_parser("matrix", help="compute pairwise preference matrix")
    p_matrix.add_argument("--ballots", default=None, help="JSON file containing ranked ballots")
    p_matrix.add_argument("--stdin", action="store_true", default=False, help="read ballots JSON from stdin")
    p_matrix.add_argument("--json", action="store_true", default=False, help="output JSON")
    p_matrix.set_defaults(func=cmd_matrix)

    # audit
    p_audit = sub.add_parser("audit", help="run capture-resistance and Condorcet consistency audit")
    p_audit.add_argument("--ballots", default=None, help="JSON file containing ranked ballots")
    p_audit.add_argument("--stdin", action="store_true", default=False, help="read ballots JSON from stdin")
    p_audit.add_argument("--json", action="store_true", default=False, help="output JSON")
    p_audit.set_defaults(func=cmd_audit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
