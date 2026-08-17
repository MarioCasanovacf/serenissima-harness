# `.harness/trust/` — what is tracked here, and what that buys

Tracked by git, on the operator's explicit instruction of 2026-08-17 (decision D6):

- `root.pub` — the operator's root **public** key. The whole authorization model reduces to
  this file: a colegiado, a plaza and a name exist only inside a warrant that verifies
  against it.
- `root.fingerprint` — the SHA256 fingerprint, which is derivable from `root.pub` with
  `ssh-keygen -lf`. It is tracked as a convenience, not as an independent fact.

**No private key material is ever placed in this directory.** The operator's private key
lives in `~/.ssh/harness_root` and is never read, copied or referenced by any tool here. A
test asserts no code path in `warrant.py` can sign. Agent keypairs live in
`.harness/keys/`, which `.gitignore` excludes, and only public halves enter a warrant.

## What tracking buys, stated exactly

`trust/` is writable by every agent on this filesystem (D-17: every agent runs as the same
OS user, so no agent can hold a secret from another). Before this directory was tracked, an
agent could move `root.pub` aside, enrol its own key, mint names freely, and put the
original back — and because the directory was untracked, **none of that appeared in
`git status`**. That path was measured: a trust-root swap forged a full ratification in
109 ms while `reconcile` reported clean and listed the forged warrant as verified.

Tracking makes the swap a **visible diff**. That is the entire benefit and it is worth
naming its limit: a diff is evidence, not prevention. An agent can still swap the file, and
can still `git add` the swap. What it cannot do is make the change invisible.

## What it costs

This is a public repository. Committing `root.pub` ties the repository to that key. The
public key discloses nothing secret, and the exposure that matters is permanence: once
pushed, the association is durable even if the file is later removed.

## What still has to happen outside this machine

The fingerprint above is not self-authenticating. Every check inside `warrant.py` is
consistent with whatever an attacker wrote here, which is why `audit` says so about itself:

```
python3 .harness/bin/warrant.py audit --expect "SHA256:<the fingerprint you wrote down>"
```

Without `--expect`, `audit` is a self-consistency check and reports itself as UNVERIFIED.
The fingerprint held off the machine — password manager, phone note, paper — is what breaks
the circle. Tracking this directory adds a second witness; it does not replace that one.
