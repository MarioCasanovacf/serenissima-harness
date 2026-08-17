# Operator enrolment: the five commands, and the one that is not a command

Every command below was run end to end against a sandbox before this file was written.
The outputs quoted are real. Where the sandbox differs from the operator's machine, the
difference is stated rather than papered over.

**What enrolment changes.** Before it, `roster.py` is bookkeeping and accepts any `--by`
string. After it, no colegiado, plaza or name exists unless it appears inside a warrant
signed by the key below. The harness cannot sign one: a test asserts no code path in
`warrant.py` can produce a signature (D-16, D-17).

**What it does not change.** Impersonation stays open and is architecturally unclosable
in-process: every agent runs as the same OS user on one filesystem, so no agent can hold a
secret from another. Enrolment closes MINTING, conditionally. It closes nothing else, and
`.harness/panel-verdict-PR-022-amendment.md` records two detectors that were silent about
even that until they were repaired.

---

## Step 1 — Generate the operator key. Use a passphrase.

```
ssh-keygen -t ed25519 -f ~/.ssh/harness_root -C "harness root operator"
```

Answer the passphrase prompt with a real passphrase. A passphrase-less key can be used by
anything running as this user, which is every agent in the harness, which defeats the
entire point.

## Step 2 — Load it into the agent with confirm-on-use.

```
ssh-add -c ~/.ssh/harness_root
```

`-c` is the whole custody decision. It makes the agent ask for confirmation on **every
single use**, so a signature can never happen without the operator seeing a prompt. Without
`-c`, any process running as this user can sign silently for as long as the agent holds
the key.

### Step 2b — on macOS, `-c` cannot prompt through Apple's agent. Read this before signing.

> **This document was wrong twice, on 2026-08-17.** First it mandated `-c` and then handed
> over a `-U` signing command that cannot succeed on a stock macOS; the flow had been
> described as tested end to end and the `-U` branch had not been exercised. Then the repair
> misdiagnosed the cause as a missing askpass program and did not work either. Both failures
> reached the operator as `agent refused operation`. What follows is verified end to end
> against a throwaway passphrase-protected key, both routes, before being written.

**The actual cause.** With `ssh-add -c` the AGENT is the party that has to ask, not the
command you typed. On macOS `SSH_AUTH_SOCK` points at Apple's launchd-managed agent
(`/var/run/com.apple.launchd.*/Listeners`), which has its own environment and never sees an
`SSH_ASKPASS` you export in your shell. So the agent holds a key marked confirm-on-use, has
no way to display the confirmation, and refuses. Exporting `SSH_ASKPASS` fixes the client
and does nothing for the agent.

Two routes work. Both keep the property that matters: **no signature happens without the
operator present.**

#### Route B, recommended: sign with the private key, no agent involved

```
ssh-keygen -Y sign -f ~/.ssh/harness_root -n harness-warrant <path to W-NNN.json>
```

Note `-f ~/.ssh/harness_root`, the PRIVATE key, with no `.pub` and no `-U`. Because step 1
gave the key a passphrase, **every signature demands that passphrase on the terminal.** No
configuration, no agent to manage, and a secret you have to know beats a dialog you can
click through.

An earlier version of this document warned against exactly this command on the grounds that
it "makes confirm-on-use decorative". That warning is FALSE for a passphrase-protected key
held outside an agent: there is nothing decorative about being asked for a passphrase you
must type. The warning only holds for a key with no passphrase.

#### Route A: keep confirm-on-use, by running your own agent

Use this if the key has no passphrase, or if you want the GUI confirmation specifically. The
private agent inherits `SSH_ASKPASS` from the shell that starts it, which is the whole point.

```
chmod +x .harness/bin/askpass_macos.sh
export SSH_ASKPASS="$PWD/.harness/bin/askpass_macos.sh"
export SSH_ASKPASS_REQUIRE=force
eval "$(ssh-agent -s)"          # your own agent, NOT Apple's
ssh-add -c ~/.ssh/harness_root
ssh-keygen -Y sign -f ~/.ssh/harness_root.pub -U -n harness-warrant <path to W-NNN.json>
```

Here `-f` points at the PUBLIC key and `-U` is required: together they route the signature
through the agent, which is what makes confirm-on-use fire. This is the one place in this
document where the `.pub` form is correct.

`SSH_ASKPASS_REQUIRE=force` is required, not decoration: without it OpenSSH prefers the
terminal and skips the helper. `ssh-agent -k` ends that agent when you are done.

The helper fails CLOSED: a broken dialog, a dismissal, a timeout, empty output, or any
string that is not an explicit authorization all deny. An askpass that returned success on
error would silently authorize every signature the agent is ever asked for, which is worse
than having none at all. `test_askpass.py` pins that, and it runs without touching your key:

```
python3 -m pytest .harness/tests/test_askpass.py -q
```

#### What is still forbidden

Reloading the key without `-c` into a long-lived agent, or stripping the passphrase. Either
one lets any process running as this user sign silently for as long as the agent holds the
key. The key's only purpose is that a human must wield it.

## Step 3 — Enrol the PUBLIC key. Only the public key ever leaves `~/.ssh`.

```
python3 .harness/bin/warrant.py init --root-pub ~/.ssh/harness_root.pub
```

Real output from the sandbox run:

```json
{
  "fingerprint": "SHA256:okI7rfYZVK5tIKm/j5X9HIlyuxf9fX6U3574eTerFV4",
  "trust_dir": ".../trust",
  "verify_out_of_band": "Verify this fingerprint OUT OF BAND against the operator's own
   record. It is the entire external trust root; nothing else here substitutes for it."
}
```

## Step 4 — This one is not a command. Write the fingerprint down somewhere that is not this machine.

`warrant.py anchor` prints it again at any time. Put it in a password manager, a phone
note, or on paper. Anywhere that an agent with write access to this filesystem cannot
reach.

This is the step that carries the entire external trust root, and it is the only step no
software here can do for the operator. `.harness/trust/` is writable by every agent and is
NOT tracked by git, so every check inside `warrant.py` is consistent with whatever an
attacker wrote there. The fingerprint held off the machine is what breaks that circle.

## Step 5 — Verify, with the fingerprint from step 4.

```
python3 .harness/bin/warrant.py audit --expect "SHA256:<the fingerprint you wrote down>"
```

Expected on a healthy harness — `anchor_matches_operator: true`, no `ALARM`, exit 0:

```json
{ "enrolled": true, "anchor": "SHA256:okI7...", "expect_supplied": true,
  "roll_orphans": [], "roll_clean": true, "anchor_matches_operator": true }
```

**`audit` WITHOUT `--expect` is not an audit.** It is a self-consistency check and it says
so in its own output. Three states used to produce identical silence — un-enrolled, forged
root without `--expect`, and genuine root with a matching `--expect`. That defect
(AUDIT-EXPECT-DISCARDED) was found by the third blind panel and is repaired: supplying
`--expect` is now an ASSERTION that this harness is anchored, and a false assertion raises
an ALARM and exits 3. Verified in both directions:

```
audit --expect <correct>   -> anchor_matches_operator: true,  no ALARM,  exit 0
audit --expect <wrong>     -> anchor_matches_operator: false, ALARM: TRUST ROOT REPLACED, exit 3
audit --expect <anything>, un-enrolled -> ALARM: NO TRUST ROOT, exit 3
```

---

# Then: how agents come into existence

The signature sits on the **establishment**, not on the hire. The operator signs a seat
budget for an epic; filling a declared seat needs no further signature. The population is
then bounded absolutely by what the operator signed, which is the property PR-023 clause 1
asks for: the Sybil attack is defeated by the seat count, not by vetting each occupant.

This concedes that an agent could occupy a declared seat under a name it did not earn. That
is impersonation, which is open regardless (D-17), so the establishment model concedes
nothing already-conceded and closes minting completely.

## The coordinator drafts. It cannot sign.

```
python3 .harness/bin/warrant.py draft \
  --epic epic-name \
  --colegiado "banco=paga por prestamos cobrados" \
  --plaza "banco/judge=2" \
  --name "worker-a:banco/judge:/path/to/worker-a.pub:Ana"
```

`draft` writes an UNSIGNED payload and prints the exact command to sign it:

```
ssh-keygen -Y sign -f ~/.ssh/harness_root -n harness-warrant <path to W-NNN.json>
```

**Why the private key and no `-U`.** This is Route B from step 2b, and it is what `draft`
now prints. The passphrase from step 1 is demanded on the terminal for every signature, so
no signature happens without the operator present. `draft` printed the `-f <pubkey> -U`
agent form twice, and both times it failed on the operator's machine for the reason step 2b
gives: with `ssh-add -c` the agent must display the confirmation, and Apple's launchd agent
cannot. Route A is still correct where the operator runs their own agent; it is not what the
tool prints by default, because the default has to be the command that runs.

## The operator signs. The agent prompts.

Run the printed command. `ssh-add -c` produces a confirmation dialog. Declining it is how
a runaway loop gets stopped.

## The coordinator applies.

```
python3 .harness/bin/warrant.py apply --warrant W-001
```

Verified sandbox output, and note where the human name ends up:

```json
{ "warrant_id": "W-001", "signed_by": "SHA256:okI7...",
  "colegiados": ["banco"], "plazas": ["banco/judge=2"], "names": ["worker-a"] }
```

```json
"worker-a": { "colegiado": "banco", "role": "judge", "epic": "epic-prueba",
              "persona": "Ana", "issued_by": "warrant:W-001", ... }
```

**The human name is a field of the signed warrant, not a separate alias map.** That was the
condition on the human-names decision and it is already satisfied by the existing
`--name NAME:COLEGIADO/ROLE:PUBKEY[:PERSONA]` grammar. A display-alias file living outside
the warrant would be a second unreconciled registry — the exact shape of the
`agent_keys.json` defect the second blind panel found, and a place for an agent to rename
itself in the figures the operator reads. Inside the signed payload, `reconcile` covers it
for free.

## Cadence

**One signature per epic**, plus one per mid-epic supplement. The supplement is the
intended friction: it is the exact moment a runaway loop would be caught. `--valid-until`
bounds a stolen key's blast radius and should be set (D-20 DIS-4).

## Standing check

```
python3 .harness/bin/warrant.py audit --expect "SHA256:<your fingerprint>"
python3 .harness/bin/warrant.py reconcile
```

`reconcile` requires every roll row to trace to a verified warrant. On an un-enrolled
harness it now returns `clean: null` — NOT ASSESSED, never clean — and counts the unbacked
rows, because it previously reported zero orphans by virtue of examining zero rows. That is
the un-enroll/mint/re-enroll path its own docstring names, and `trust/` is untracked by
git, so deleting it leaves no trace in `git status`. `audit --expect` is the verb that
refuses that state; `reconcile` alone cannot tell "not yet built" from "just torn down".
