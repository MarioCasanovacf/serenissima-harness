# The judge seat, DRAFT ONLY (T-452 section 3, board T-468)

Nothing in this file mutates the live roster and nothing here is signed. The
warrant payload it documents already exists, unsigned, at
`.harness/warrants/W-003.json` (written by a real `warrant.py draft` call,
quoted below verbatim). `roster.py charter`/`plazas` are **recipes written
here, not executed** -- running them is the operator's or a later worker's
call, after the warrant is signed and applied, per `warrant.py apply_warrant`
being the thing that actually calls `roster.charter`/`plazas`/`issue`.

## 1. The colegiado and plaza recipe (T-452 section 3), as the warrant already carries it

Once the warrant below is signed and applied, `warrant.py apply` calls these
on the caller's behalf -- they are quoted here only so the shape is visible
without reading the JSON:

```
roster.py charter --colegiado judge \
  --incentive "a reasoned verdict on a filed suit, paid to distrust both parties"
roster.py plazas --epic gen-10-courts --colegiado judge --role verifier --count 1
```

Seat published BEFORE filled, exactly as decision 3 requires and exactly as
W-002 already does for every other office (`.harness/OPERATOR-ENROLMENT.md`:
"The signature sits on the establishment, not on the hire").

## 2. The warrant payload, UNSIGNED, already on disk

`.harness/warrants/W-003.json` -- real output of a real `warrant.py draft`
call, run against the live `.harness` root (never the operator's key; `draft`
cannot sign anything, pinned by `test_warrant.py`'s
`TheHarnessCannotSign.test_no_code_path_in_warrant_py_signs_anything`):

```
python3 .harness/bin/warrant.py draft \
  --epic gen-10-courts \
  --colegiado 'judge=a reasoned verdict on a filed suit, paid to distrust both parties' \
  --plaza 'judge/verifier=1' \
  --name 'judge-tbd:judge/verifier:<PLACEHOLDER-PUBKEY-PATH>:agentic judge, suits epic gen-10-courts (PLACEHOLDER NAME AND KEY -- replace both before signing)' \
  --valid-until 2027-01-31T00:00:00Z
```

**`judge-tbd` and its embedded public key are both placeholders.** The
public key embedded in `W-003.json` was generated in a scratch temp
directory for this draft only, its private half was never written anywhere
under this repository, and it signs nothing real. Before the operator signs:

1. Choose the real judge candidate's name.
2. Generate (or have the candidate generate) a real ed25519 keypair under
   that candidate's own key storage (never under `.harness/keys` by this
   worker, never by this file).
3. Re-run the `draft` command above with the real `--name` value
   (`<real-name>:judge/verifier:<real-pubkey-path>:<persona>`), which
   overwrites `.harness/warrants/W-003.json` with the real payload (or
   drafts a fresh `W-NNN` if `W-003` has since been superseded).

## 3. The exact command the operator runs to sign it

Printed verbatim by the `draft` call above (Route B,
`.harness/OPERATOR-ENROLMENT.md` step 2b):

```
SSH_AUTH_SOCK= ssh-keygen -Y sign -f ~/.ssh/harness_root -n harness-warrant .harness/warrants/W-003.json
```

Then, once signed:

```
python3 .harness/bin/warrant.py apply --warrant W-003
```

**Nothing above has been run by this worker.** `W-003.json.sig` does not
exist; `warrant.py reconcile` reports it `warrants_unsigned`, the same
"normal state of a draft awaiting the operator" `W-001.json` has carried
since gen-6.

## 4. Recusal checklist (T-452 section 3) -- advisory, NOT a gate (PR-017)

Run BY HAND at `issue` time by whoever fills the seat, exactly as
`roster.py eligible` is advisory and no further (`roster.py:366`,
`"IS_NOT_A_GATE"`):

- [ ] The candidate's name is not the claimant's name and not the
      respondent's name, for the specific suit the judge is about to decide.
- [ ] `roster.py eligible --record <any precedent record either party
      published that bears on this suit's contract>` has been run, and the
      candidate is NOT in `same_colegiado_would_be_excluded` and NOT the
      `author`.
- [ ] If the suit's `contract` traces to a `deliberate.py` dossier, that
      dossier has been read with `deliberate.py show <id>`, and the
      candidate neither appears among its `sponsor`s nor cast a `vote`.

This checklist decides nothing mechanically. Design section 3, quoted: "T-452
does not request [a PR-017] addendum -- the recusal check it specifies is
therefore the same class of REPORT `eligible` already is." A future worker
may promote any of the three checks above to a gate only through PR-017's own
amendment route, never by this file.

## 5. What this file is not

It is not a signed warrant, not a roster mutation, and not a consequence.
PR-022 clause 4 and the warrant's own `NOT_A_CONSEQUENCE` field both hold:
this seat, once filled, confers a name and nothing else.
