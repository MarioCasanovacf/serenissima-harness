# W-002: the first seating. What the operator is being asked to sign.

Drafted 2026-08-17. **UNSIGNED.** The coordinator cannot sign it and a test in
`.harness/tests/test_warrant.py` asserts no code path in the module can.

Payload: `.harness/warrants/W-002.json`
Digest: `sha256:14069b6a1acab5ab281d3abe66968728600154904c2e74e95ad67157491b41e3`

Supersedes W-001, which is WITHDRAWN and must never be applied.

---

## The command

```
ssh-keygen -Y sign -f ~/.ssh/harness_root -n harness-warrant \
    .harness/warrants/W-002.json
```

Note `-f ~/.ssh/harness_root`, the PRIVATE key, with no `.pub` and no `-U`. It will ask for
the key's passphrase on the terminal, and it asks on every single signature. That is the
human-presence check.

**This command was wrong here twice.** Both earlier versions used the `-f <pubkey> -U`
agent route, and both failed on the operator's machine with `agent refused operation`. With
`ssh-add -c` the AGENT is the party that must display the confirmation, and on macOS
`SSH_AUTH_SOCK` points at Apple's launchd-managed agent, which has its own environment and
never sees an `SSH_ASKPASS` exported in a shell. The agent route still works behind a
privately started `ssh-agent` and is written up as Route A in `OPERATOR-ENROLMENT.md`. It is
not the default because the default has to be the command that runs.

Then the coordinator runs `warrant.py apply --warrant W-002`, followed by
`warrant.py reconcile` and `roster.py roster`.

## What it seats: eleven plazas across three colleges

**`fedatario`** — process integrity. Paid for nothing else, and constrained the way
AgentCity constrains its clerks: **cannot legislate, cannot vote, cannot hold stakes.**

| plaza | name | what the office does |
| --- | --- | --- |
| `fedatario/registrar` | `fed-registrar` | binds a name to a key and to a principal |
| `fedatario/relator` | `fed-relator` | runs deliberation, in randomized speaking order |
| `fedatario/regulador` | `fed-regulador` | anchors evidence BEFORE discussion opens |
| `fedatario/codificador` | `fed-codificador` | turns a consensus into a record |

**`registro`** — paid for records that get confirmed and survive later citation.
`registro/author` 2 seats (`registro-a` seated), `registro/verifier` 3 seats
(`registro-b` seated).

**`revision`** — paid for refutations that hold up against reply, per PR-025 clause 1,
adversarial work pays more. `revision/verifier` 3 seats, all three seated:
`revision-doctrina`, `revision-ataque`, `revision-mecanismo`.

Nine of eleven seats filled. Two left empty so the roll can grow to a ceiling the operator
signed without needing a new warrant. Expiry 2026-11-10, aligned to the T-349 quarterly
watch, per D-20 DIS-4: a bound on a stolen key's blast radius.

## Why these four offices and not the two in W-001

Because the four name the failure this session actually committed. In round 4 the
coordinator drafted the panel brief, ran the panel, read the verdicts and wrote the record.
Registrar, Speaker, Regulator and Codifier are those four jobs, and holding all four is what
made the blind panel not blind.

The seat design also keeps Swiss hook H-20 from the operator's own commissioned research:
part-time practitioners embedded in working lineages, never a professional judging caste,
exposure capped, because the measured Swiss failure is that unlimited liability prices out
honest servers.

## What it does NOT do

The payload carries this verbatim, and it is the whole of the coordinator's claim:

> PR-022 clause 4 holds: this warrant confers a seat and a name, never a weight, a burden, a
> quorum or a permission.

No standing figure changes. No consequence attaches. `roster.py` remains bookkeeping.

## The question the coordinator is NOT deciding

**PR-028 clause 6, verbatim: "This charter authorizes no cell now."**

Whether seating a colegiado under an operator-signed warrant IS the act that authorizes the
first cell, or whether a published tier-1 record must land first, is set out both ways here
and not resolved:

- **The warrant suffices.** The operator is the only tier-1 authority (PR-026 c1). A signed
  warrant is a sovereign act, and clause 6 is a self-limitation of the charter record.
- **A record must land first.** Clause 6 is a deliberate hold and the enacting record
  precedes the seating.

The coordinator's citation record this session is four tier-1 miscitations deep, including
reading an ordering into PR-023 clause 1 that is not there and extending PR-017 past its
declared narrow scope. Its reading should not be taken on trust.

Also flagged: `CLAUDE.md` states recusal is not computed from colegiado membership "until an
amending record lands (PR-017)". That citation is suspect under defect
PR-017-OVEREXTENSION-A and should be re-derived before anyone relies on it.

## Still owed, and independent of this warrant

`warrant.py audit --expect "SHA256:..."` with the fingerprint held off the machine. Until
that runs the anchor is UNVERIFIED, and a measured trust-root swap forges a full ratification
in 109 ms while `reconcile` reports clean and lists the forged warrant as verified.

## Agent keys

Nine keypairs under `.harness/keys/`, which `.gitignore` excludes. Only public halves appear
in the payload.

D-17 is unchanged and stated rather than papered over: every agent runs as the same OS user
on one filesystem, so no agent can hold a secret from another. These keys bound ACCIDENT and
make acts attributable. They do not bound an adversary, and a test in the suite proves the
limit by stealing an agent key and forging with it.
