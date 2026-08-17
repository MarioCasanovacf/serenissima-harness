# W-001: the first seating. What the operator is being asked to sign.

Drafted 2026-08-17 by the coordinator. **UNSIGNED.** The coordinator cannot sign it and a
test in `.harness/tests/test_warrant.py` asserts no code path in the module can.

Payload: `.harness/warrants/W-001.json`
Digest: `sha256:bcc2d895d5e9bf1de7d84902dc4b9f3c2483b7ca9beada8f9f6a64b2cca2be82`

---

## Why this warrant and not another

The operator's civilizational ladder, restated by him on 2026-08-17, has eleven rungs. The
measured position: rungs 1 through 4 built, rung 6 already live, rungs 7 through 10 empty,
rung 11 recorded but not instrumented. Rung 5 — offices with occupants — has a complete
scaffold (`roster.py`, `warrant.py`, `attest.py`) and **zero colegiados, zero plazas, zero
issued names.**

That vacancy is why the round-4 panel returned 12 refutations of 12. The instruments being
drafted were economic instruments for a society with no seated members. This warrant seats
the members.

## What it creates

**Two colegiados.** A colegiado declares what it is paid for, before the work exists.

| colegiado | paid for |
| --- | --- |
| `registro` | records that get confirmed and survive later citation |
| `revision` | refutations that hold up against reply (PR-025 c1: adversarial work pays more) |

**Eight plazas**, seats published before they are filled: `registro/author` 2,
`registro/verifier` 3, `revision/verifier` 3.

**Five names**, each bound to one seat and one public key inside the signed payload:
`registro-a` (author), `registro-b` (verifier), and `revision-doctrina`,
`revision-ataque`, `revision-mecanismo` (verifiers).

Three of eight seats are deliberately left empty, so the roll can grow without a new warrant
up to a ceiling the operator signed.

**Expiry 2026-11-10**, aligned to the T-349 quarterly watch. This is D-20 DIS-4: a bound on
a stolen key's blast radius, not a formality.

## Why these seats and not a bench of judges

Swiss hook H-20, from the research the operator commissioned: verdict-givers are part-time
practitioners embedded in working lineages, never a professional judging caste, and their
exposure is CAPPED, because the measured Swiss failure is that unlimited liability prices
out honest servers. The three `revision` seats are the four panel lenses this session has
been running as ad hoc subagents, made into offices. Three, not four: the historical lens is
research, not adjudication, and does not need a seat to do its work.

## What it does NOT do

The payload carries this line verbatim, and it is the whole of the coordinator's claim:

> PR-022 clause 4 holds: this warrant confers a seat and a name, never a weight, a burden, a
> quorum or a permission.

No standing figure changes. No consequence attaches. `roster.py` remains bookkeeping.

## The question the coordinator is NOT deciding

**PR-028 clause 6, verbatim: "This charter authorizes no cell now."**

Whether seating a colegiado under an operator-signed warrant IS the act that authorizes the
first cell, or whether a published tier-1 record must land before it, is a real question and
the coordinator will not answer it silently. Two readings:

- **The warrant suffices.** The operator is the only tier-1 authority (PR-026 c1). A signed
  warrant is a sovereign act, and clause 6 is a self-limitation of the charter record rather
  than a bar on the sovereign.
- **A record must land first.** Clause 6 is a deliberate hold, and the ordering discipline
  this project follows would put the enacting record before the seating.

The coordinator's own record on citation discipline is poor enough this session that the
operator should not take its reading on trust: four tier-1 miscitations, including reading
an ordering into PR-023 clause 1 that is not there, and extending PR-017 well past its
declared narrow scope. Both are recorded as defects.

Related and also flagged: `CLAUDE.md` states that recusal is not computed from colegiado
membership "until an amending record lands (PR-017)". That PR-017 citation is suspect under
defect PR-017-OVEREXTENSION-A and should be re-derived before anyone relies on it.

## The commands

Step 1, the operator signs. This is the only step the coordinator cannot perform.

```
ssh-keygen -Y sign -f ~/.ssh/harness_root.pub -U -n harness-warrant \
    .harness/warrants/W-001.json
```

`-U` signs THROUGH ssh-agent using only the public key, so the `ssh-add -c` confirm-on-use
prompt actually fires. Pointing `-f` at the private key file reads it directly and bypasses
the agent, which makes confirm-on-use decorative.

Step 2, the coordinator applies it.

```
python3 .harness/bin/warrant.py apply --warrant W-001
```

Step 3, verify the roll traces to a verified warrant.

```
python3 .harness/bin/warrant.py reconcile
python3 .harness/bin/roster.py roster
```

Still owed and independent of this warrant: `warrant.py audit --expect "SHA256:..."` with
the fingerprint held off the machine. Until that runs, the anchor is UNVERIFIED, and a
measured trust-root swap forges a full ratification in 109 ms while `reconcile` reports
clean.

## Agent keys

Five keypairs were generated under `.harness/keys/`, which `.gitignore` excludes. Only the
public halves appear in the payload.

D-17 is unchanged and is stated rather than papered over: every agent runs as the same OS
user on one filesystem, so no agent can hold a secret from another. These keys bound
ACCIDENT and make acts attributable. They do not bound an adversary, and a test in the
suite proves the limit by stealing an agent key and forging with it.
