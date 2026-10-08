# T-432 design: per-agent signing identity, surveyed against D-17

**Date:** 2026-10-07 · **Role:** thinker · **No source edits in this document.**
**Decision made before any code, as the task requires. Operator approves before any
worker task is created (see "First worker tasks" at the end — listed, not boarded).**

## The standing limit this design cannot get around

D-17 (`.harness/coordinator-decisions-ruling-round-2.md`): every agent runs as the same
OS user on the same filesystem. There is no isolation boundary between agents, so no
agent can hold a secret another agent cannot read, and therefore no agent can have an
unforgeable identity *from inside the harness*. `warrant.py`, `attest.py` and
`OPERATOR-ENROLMENT.md` all restate this rather than working around it: minting is the
one place the system affords a human (the root key), and everything downstream is
forgeable-but-detectable (D-20's disincentive package, D-22's impersonation rule set).

T-432 asks a narrower question than "can we close D-17": can any of the five named
mechanisms move the boundary from *files on disk* to *a request a process must make*,
and if so, does moving it there actually buy anything new, given that subagents spawned
by one coding-agent process inherit that process's OS user and its ambient reach.

**The hard part, named precisely, because every option below is graded against it:**
a key file readable only by user X stops a *different OS user* from reading it. It does
nothing about a subagent spawned by the same coding-agent process that is already
running as X — that subagent can just ask whatever holds the key to sign, through
whatever channel the coding-agent process itself uses (a tool call, a socket, a CLI
invocation it can shell out to). The question is never "who can read the key," it is
**"who can ask the signer to sign, and does the signer have any way to tell which
caller is asking."** Every option is scored against that question, not against file
permissions.

## Survey

### 1. macOS Keychain items, one per agent

**Mechanism.** Each agent gets a Keychain item (a key or a secret) with an ACL naming
the one binary/process allowed to access it without a prompt.

**What it closes.** Nothing that D-17 opens. The Keychain ACL is keyed to a *code
signature or process identity*, not to "which agent's turn it logically is." Every
agent in this harness runs inside the same Claude Code process tree (or an equivalent
coding-agent runtime) as the same OS user; that process is exactly the accessor the ACL
would have to name, since it is the thing calling into Keychain Services on any
agent's behalf. Naming it grants every agent access; naming nothing defeats the point
of using Keychain at all.

**What stays open.** Full impersonation. A subagent that wants to sign as a different
agent's identity does not need to read a key file — it asks the same host process to
invoke Keychain the same way the legitimate agent would, and Keychain cannot
distinguish the two callers because they are the same OS process.

**What the operator must run by hand.** Creating N Keychain items and N ACL entries,
one per agent role, re-done every time a role is added — and re-approving the
`security` prompt (or a `-T` grant) for the harness binary on first use per item, which
on a hardened setup can recur on OS/Keychain updates.

**Cost in operator attention.** Front-loaded (N setup steps) plus occasional
re-approval noise; no per-act friction once an item's ACL is granted, which is also why
it buys no per-act protection.

**Falsifier a verifier can run on this machine.** Write two tiny scripts, `agent-a.sh`
and `agent-b.sh`, both invoking `security find-generic-password -s harness-agent-a -w`
(or equivalent `security "unlock-keychain"`/`-a` reads) from the *same shell session*
the coding-agent process would use. If `agent-b.sh` can read or use `agent-a`'s item
without a distinct human-visible prompt tied to agent-b's own process identity, the
ACL did not separate them. (Expected result: it succeeds — Keychain ACLs bind to the
calling binary, and every harness agent shares one.)

### 2. Separate OS user accounts, one per agent role

**Mechanism.** Create `agent-worker`, `agent-verifier`, etc. as real `dscl`-provisioned
macOS users (or `useradd` on Linux); each key file is `chmod 600` under that user's
home; agents run as `sudo -u agent-worker ...` or under `launchd`/`systemd` per-user
services.

**What it closes.** This is the one option that attacks D-17's premise directly rather
than working inside it: if role X truly executes as OS user X, standard filesystem
permissions keep user Y's key unreadable by user X's process, no matter how many
subagents X spawns. Within that boundary, the question "who can ask the signer to
sign" collapses back to a normal Unix answer: only processes running as that user.

**What stays open.** (a) The *coordinator* — the one process dispatching work to
subagents — still has to run as some user, and if it is the one invoking
`sudo -u agent-worker` or orchestrating cross-user IPC, it effectively holds the
capability to act as every role, which re-derives D-17 at the orchestration layer
instead of the agent layer. (b) Every harness-side tool (`blackboard.py`, `lock.py`,
`attest.py`) would need cross-user file access (shared `.harness/` state, shared
locks) re-architected for multi-user permissions — today they assume a single-user
tree. (c) This harness's actual deployment mode (Claude Code subagents spawned
in-process by one coordinator session) does not currently support "this subagent runs
as a different OS user" as a primitive; it would require shelling out to `sudo`/`su`
per subagent call, which is a structural change to how the bench is invoked, not a
config change.

**What the operator must run by hand.** Provision each OS user once (`sysadminctl` /
`dscl` on macOS, `useradd` elsewhere), set up passwordless-but-logged `sudo` rules
scoped per role (or per-user `launchd` agents), and fix `.harness/` directory
permissions (group-writable with a shared group, or split into per-user subtrees) —
this is real systems administration, not a one-line enrolment step, and has to be
redone on every new machine the harness runs on.

**Cost in operator attention.** High one-time setup; low per-session cost after, but
every new agent role is a new OS account to provision and audit, and the sudoers file
itself becomes a thing that must be reviewed for drift.

**Falsifier a verifier can run on this machine.** As the coordinator's OS user, attempt
`cat ~agent-worker/.ssh/worker_key` and separately
`sudo -u agent-worker cat .../worker_key`. The first must fail (permission denied); if
the second succeeds without a password/log prompt tied to *that specific invocation*,
the sudo rule is too broad and the boundary is fictional. Also check: can the
coordinator's own process (not a human at a terminal) run that `sudo -u` command
non-interactively? If yes, the coordinator holds every role's capability and D-17 has
only moved up one layer.

### 3. Hardware tokens (YubiKey / Secure Enclave via `sign -se`, etc.)

**Mechanism.** The private key never leaves tamper-resistant hardware; signing requires
a physical touch (YubiKey) or a Secure Enclave API call gated by biometric/passcode
presence.

**What it closes.** Key *exfiltration*: no filesystem read, however privileged, yields
the private key material, because it was never written to a filesystem. This is a
strictly different property from "no agent can sign as another" — it is "the key
cannot be copied," not "the key cannot be invoked by the wrong caller."

**What stays open.** The touch/biometric gate is a *presence* check, not an *identity*
check among agents: a human (the operator) touching the token authorizes whatever
signing request happens to be in flight at that moment, and a subagent racing to fire
its own sign request in the window after a touch can get signed under the same touch.
With one token per machine (the realistic deployment — one human, one laptop), there is
exactly one hardware root, structurally identical in role to the ssh-agent `-c` key the
harness already uses for the operator's warrant signature (D-19). It does not give
*agents* distinct unforgeable identities; it gives the *operator* one unforgeable
gesture, which this harness already has via `ssh-add -c`. Buying N hardware tokens (one
per agent) would require the operator to physically touch N different devices, so it
degenerates into option 5 (operator-mediated, per-act friction) with extra hardware
cost and no extra guarantee, since every token still ultimately executes on the one
shared OS user's say-so about which process gets routed to which token.

**What the operator must run by hand.** Buy and provision each token, pair it with
`ssh-keygen -K` or PIV/age-plugin-yubikey enrollment, and — the part that actually
matters here — physically touch the correct token for the correct request every single
time, which requires the operator to *know which agent is asking* at the moment of the
touch (the harness has no UI that shows this reliably today).

**Cost in operator attention.** Highest of all five if done honestly (one touch per
signature, same shape as D-19's `ssh-add -c` but requiring physical presence rather
than a terminal passphrase); if the operator instead loads the token into a background
agent that signs without re-touching per call (defeating the point), it degrades to
option 1's guarantee.

**Falsifier a verifier can run on this machine.** Not independently runnable without
operator-owned hardware; the closest machine-local falsifier is to check whether the
harness's signing call path for this option has any mode that batches multiple logical
acts behind one touch (grep the implementation for a sign loop between two presence
checks). If such a mode exists, two different agents' acts can ride one touch and the
"per-act human gate" claim is false.

### 4. A separate signer process, running as a different OS user, holding keys for named agents, signing on request

**Mechanism.** A long-lived daemon (`signerd`) runs as its own OS user (or in a locked-
down container/VM), holds every agent's private key, and exposes a narrow RPC
(`sign(agent_name, payload) -> signature`) over a Unix socket or localhost port. Agents
never see key material; they send a payload and a claimed name and get a signature
back.

**What it closes.** Nothing, as specified above, and this is the option where that is
easiest to see concretely because the request path is explicit. `signerd` must decide
whether a given RPC call is *authorized to request a signature as agent-worker*. Every
caller — every subagent spawned by the coordinator's process — connects to that socket
as the same OS user the coordinator runs as. Unless `signerd` can cryptographically
distinguish *which subagent* opened the connection (it cannot: a Unix domain socket's
peer credentials, `SO_PEERCRED`, report the connecting *process's* uid/gid/pid, not an
application-level "which role is this logically"), it is reduced to trusting a
self-reported `agent_name` field in the request — exactly roster.py's `--by` problem
(`hc.agent_id()` reads an environment variable the caller controls) relocated to a new
socket. This is the single most important finding of the survey: **a separate signer
process does not change who can ask it to sign; it only changes where the key lives.**
The read boundary moves from "a file any agent-process can open" to "a socket any
agent-process can connect to and lie to," and D-17's conclusion — no agent can hold a
secret another agent cannot effectively use — survives the move intact, because the
asking-process is still the single shared OS user on both sides of the move.

**What stays open.** All of impersonation, for the reason above. What it *does* buy,
and this is real: key material is centralized in one process's memory rather than
scattered across N files, so (a) a code-read bug in one worker task cannot leak a key
by accident (only `signerd`'s own surface can), and (b) every sign request can be
logged centrally with full payload, giving a complete audit trail of every signature
*request* even for ones that get refused — which none of options 1–3 give you for free.
If `signerd` additionally required a per-request operator confirmation (collapsing it
into option 5, or wiring it to the same `ssh-add -c` mechanism W-002 already uses for
the root), the per-act human gate reappears, at the cost of the operator's attention
that D-19 already accepted for the root key.

**What the operator must run by hand.** Stand up and keep alive the `signerd` process
under its own OS user (back to option 2's provisioning burden, but only for one
account instead of N); define and review its request-authorization policy (today that
policy is necessarily "trust the caller's self-reported name," so the operator's real
job becomes periodically auditing `signerd`'s request log for names that should not
have been able to ask — a detective control, not a preventive one).

**Cost in operator attention.** Moderate setup (one daemon, one OS user) plus ongoing
log review; no per-act friction unless deliberately added (at which point it is
option 5's cost).

**Falsifier a verifier can run on this machine.** Start a minimal stub `signerd` that
authorizes purely on a request-body `agent_name` field. From one terminal (one process,
one OS user — standing in for "the coordinator's subagents"), send two RPCs claiming
`agent_name="worker-a"` and `agent_name="worker-b"` respectively. Both must be signed
successfully with no distinguishing signal available to `signerd` beyond the string the
caller supplied. If `signerd` has no independent channel confirming which name is
truthful (and in a same-user, same-filesystem deployment it structurally cannot), the
falsifier passes trivially — which is the point: it demonstrates the gap rather than
closing it.

### 5. Short-lived tokens minted by the operator per dispatch

**Mechanism.** Before dispatching a subagent for task T-ID under role R, the operator
(or a tool only the operator's human-presence gate can trigger — e.g. requiring the
same `ssh-add -c`/terminal-passphrase prompt W-002 already uses) mints a token scoped to
`(agent_name, task_id, role, expiry)`. The subagent presents that token to request a
signature or to perform a privileged act; the token is single-use or short-TTL.

**What it closes.** This is the only option on the list whose unforgeability argument
does not route back through "trust the caller's self-report," because the *minting*
step — the one irreducible human action — happens before the subagent exists to lie
about its name, the same structural move `warrant.py` already makes for
colegiado/plaza/name minting (D-16: "the unforgeable boundary goes exactly at MINTING
and nowhere else"). A token minted for `(worker-a, T-432, thinker)` cannot be relabeled
by a subagent that wants to act as `worker-b`, because relabeling it breaks whatever
signature/MAC the operator's minting step applied — the forgery would require the
operator's minting key, which is exactly D-17's "the only unstealable key in this
system is the operator's."

**What stays open.** Everything *within* the window the token is valid for. If a token
scoped to `(worker-a, T-432)` is handed to the subagent process, and that subagent is
(as it structurally is, per the "hard part" framing above) just the coordinator's
process acting on worker-a's behalf, nothing stops the coordinator from using that same
token to perform acts under worker-a's name that worker-a's task did not actually
justify — the token proves "the operator authorized *something* called worker-a doing
*something* under T-432," not "this specific act is the one the operator saw." This is
exactly W-002's own stated limit: "signed plazas bound HOW MANY seats exist. They do
not bound WHO occupies them" (Track 4, ruling round 4). It is the warrant/plaza model
already running in this harness, scaled down from epoch-grain to dispatch-grain — which
is also its cost (below).

**What the operator must run by hand.** One minting action per dispatch — not per
epic, as W-002's plazas already are, and not per signature, as D-19's `ssh-add -c`
already is, but per *task claim*. That is a materially higher cadence than either
existing human gate in this harness. Track 3 (ruling round 4) already names the general
fix for this cost — "certification is batched... one signature certifies an epoch's set,
so the operator's attention cost is O(1) per epoch rather than O(1) per unit" — and the
same batching could apply here: mint a *set* of per-dispatch tokens once per epic
(effectively what W-002's plazas already are) rather than one per claim, trading some
of option 5's freshness guarantee back for W-002's existing cadence.

**Cost in operator attention.** Without batching: highest-frequency human gate in the
harness (per dispatch, not per epic or per signature). With batching to epic-grain, it
converges on what W-002 already costs — meaning the real marginal cost of "add dispatch
tokens" over "just use warrant plazas as already designed" may be small, which is worth
testing before building a second minting path next to `warrant.py`'s.

**Falsifier a verifier can run on this machine.** Mint a token scoped to
`(worker-a, T-999, worker, expiry=+5m)` with a stub minter using an HMAC keyed to a
file only the "operator" role can read in the test fixture. From the same OS user,
attempt to (a) use the token as minted — must succeed — and (b) tamper the
`agent_name` field and re-present it — must fail closed (bad MAC). Then let the TTL
lapse and re-present the untampered token — must fail closed (expired). All three are
mechanically checkable with no hardware and no new OS accounts, which is why this is
the cheapest falsifier to actually run of the five.

## The one sentence the task asks for

No option on this list closes impersonation on one machine: every option except
separate OS user accounts (option 2) is defeated by the same fact — the asking process
and the signing process end up sharing one OS user's ambient reach — and option 2 only
relocates the boundary to a layer (the coordinator-to-subagent dispatch path) that this
harness's actual deployment mode does not currently enforce, so D-17 stands as stated.

## What the seated notarial office (fedatario, warrant W-002) could certify under each option

W-002 seats `fedatario/registrar`, `/relator`, `/regulador`, `/codificador` — four
offices explicitly barred from legislating, voting, or holding a stake (W-002 briefing).
Their job is process integrity, not substantive adjudication, which is exactly why some
of what they certify does not need agent identity solved at all.

| Option | What `fedatario/registrar` could newly certify | Limit |
|---|---|---|
| 1. Keychain items | "A signature was produced by whichever process holds this Keychain ACL" — no new binding over what `attest.py` already gives (key-on-disk, same guarantee). | Registrar cannot certify *which agent* asked; the ACL doesn't name one. |
| 2. Separate OS users | If actually wired through the dispatch path: "this act was signed by a process running as OS user `agent-worker`," a genuinely stronger fact than today's "signed with a key file labeled worker-a." | Still cannot certify the *coordinator* did not act as worker-a, per the survey above. |
| 3. Hardware tokens | "A human touched a physical device at this timestamp" — reinforces `regulador`'s evidence-anchored-before-discussion role with a presence fact, not an identity fact. | Does not separate which agent's act the touch was authorizing. |
| 4. Signer daemon | `registrar` gains a complete, centralized request log — every sign *attempt*, including refused ones — which it cannot get today scattered across N key files. Strengthens `codificador`'s record-making (more to turn into a record). | The log records self-reported names; registrar can certify the log is complete, not that the names in it are true. |
| 5. Dispatch tokens | `registrar` can certify "the operator minted a token for exactly this `(agent, task, role)` tuple before the act" — the strongest binding on the list, matching what warrants already do for colegiado/plaza/name. | Still cannot certify the *specific act* under that token is the one the operator intended, per W-002's own "plazas bound how many, not who" limit. |

**Notarial pieces that do not depend on identity at all**, and are available today
regardless of which (if any) option above is ever built:

- **`attest.py retract`** (designed in T-406, `.harness/design-T-406-retraction.md`): a
  retraction is the *signer's own* chain disowning its own prior act. It needs no
  stronger identity than the chain already has — D-17's forger-can-retract-falsely
  limit is named and accepted in that design, not solved by it, and the design is
  honest that the asymmetry (DIS-2: credit follows the signature, forgery can only
  damage the victim, never enrich the forger) is the whole defence. This verb is
  orthogonal to T-432: it works exactly as well under option 1 as under option 5.
- **`warrant.py audit --expect <fingerprint>`**: refuses to report clean without a
  fingerprint supplied *out of band*, by a human, from outside the machine. This is the
  one piece of the whole system that structurally cannot be satisfied by anything
  running on this machine, by any of the five options — it is not an agent-identity
  mechanism, it is an operator-presence mechanism, and it stays exactly as strong (or
  weak) no matter which option T-432 eventually recommends building.
- **`reconcile`**: ties every roster row back to a verified warrant; it is a check
  over *minting*, which D-16/D-17 already established is the one place this harness can
  afford a human, and it does not change shape under any of the five options since none
  of them touches minting.

These three are worth keeping in any worker-task sequencing: they are available now,
cost nothing further to rely on, and should not be re-litigated inside T-432's identity
work.

## Recommendation

**Option 5 (short-lived, operator-minted dispatch tokens), batched to epic-grain so its
attention cost converges on what W-002 already charges, is the recommended option.**
Reasons, weighed against the other four:

- It is the only option whose unforgeability argument does not bottom out in "trust the
  asking process's self-report" (option 4's `signerd`, and by extension option 1's
  Keychain ACL, both reduce to that). It bottoms out in the operator's minting key
  instead, which D-16/D-17 already establish is the one secret this harness can afford.
- It needs no new systems administration (option 2's per-OS-user accounts) and no new
  hardware procurement or physical-presence workflow (option 3) — it is a software
  artifact shaped like `warrant.py`'s existing draft/sign/apply flow, so it extends a
  pattern the operator has already learned rather than teaching a new one.
- Its stated limit ("bounds how many, not who" — identical to W-002's own stated limit
  on plazas) is the same limit the operator has already accepted once, in writing, for
  the warrant mechanism. Recommending a second mechanism with a *novel* limit would ask
  the operator to evaluate a new risk; recommending one with the *same, already-accepted*
  limit does not.
- Its falsifier is the cheapest of the five to actually run (no hardware, no new OS
  accounts, three mechanically checkable properties: tamper-fails, replay-fails,
  expiry-fails).

The honest cost of this recommendation is the one it shares with warrant plazas: it
does not and cannot certify that a specific act performed under a dispatch token is the
act the operator actually intended, only that some act under that `(agent, task, role)`
tuple was authorized before the fact. That is Track 4's unclosed point, restated at
dispatch grain instead of epic grain, and this design does not pretend otherwise.

### First worker tasks (listed here only — not created on the board; the operator
approves this design first)

1. Specify the dispatch-token format: fields `(agent_name, task_id, role, issued_at,
   expiry, nonce)`, MAC'd with a key only the operator's minting step can use (mirror
   `warrant.py`'s draft/sign separation: a `draft` step any agent can run that emits an
   UNSIGNED token request, and a `mint` step that requires the same out-of-band
   human-presence gate `OPERATOR-ENROLMENT.md` already documents for warrants).
2. Write the verifier (`token.py verify`) that a) rejects tampered fields (bad MAC),
   b) rejects expired tokens, c) rejects tokens whose `(agent_name, task_id, role)` does
   not match the claim/lock call presenting them — wired into `blackboard.py claim` and
   `lock.py acquire` as an optional, additive check (does not change existing behavior
   when no token is required, so there is no flag day, mirroring `warrant.py`'s own
   backward-compatibility discipline).
3. Decide and record the batching grain (per-epic vs. per-task) as its own small
   ratified decision before building it, since the recommendation above only works if
   the attention-cost argument (epic-grain) is the one actually implemented — per-task
   grain would reintroduce the highest-frequency human gate in the harness and should
   not ship by accident.
4. Write the falsifier test (tamper / replay / expiry, as specified in option 5's
   survey entry above) before wiring the token into any claim path, so the guarantee is
   pinned before anything depends on it — the same sequencing discipline T-406 and
   `warrant.py` both follow (design and falsifier before the mechanism keys any
   consequence).
5. Explicitly do NOT build option 4's signer daemon as a substitute: the survey above
   shows it does not change the asking-process boundary, and building it first would
   spend operator attention on a mechanism with the weaker, unexamined-until-now limit
   when the stronger one (option 5) costs about the same to build.

None of the above is created on the blackboard by this task. T-432 is handed to the
verifier role next; the operator ratifies the recommendation before any of the five
items becomes a boarded task.
