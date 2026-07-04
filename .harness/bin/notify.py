#!/usr/bin/env python3
"""Remote messenger CLI for the Universal Agent Harness (.harness/notify_config.json).

ZCode parity item #2 ("Remote Bot Control / Messenger Hooks", see
fetched_docs/zcode_features.md §B): lets an agent (or a Claude Code
Notification/Stop hook) push a status message to an external channel
(Telegram bot, or a generic JSON webhook). SHIPS DISABLED. Sending real
network traffic is a human gate (see state.json human_gates ->
"activating or sending remote webhook notifications (T-005) for the
first time") -- this tool enforces that gate mechanically, not just by
convention: `send` only reaches the network code path when the config
says enabled=true AND dry_run=false AND url is non-empty. The config
this tool `init`s ships with enabled=false, dry_run=true, url="" --
zero network is reachable until a human edits the config file by hand.

Usage:
  python3 .harness/bin/notify.py init
    Writes a template .harness/notify_config.json. Refuses to overwrite
    an existing file (exit 1) -- never clobbers a human's real config.
  python3 .harness/bin/notify.py status
    Prints the config state (provider, url, enabled, dry_run). The
    token is ALWAYS redacted: "***set***" if non-empty, "(empty)"
    otherwise. Never prints the raw token value.
  python3 .harness/bin/notify.py send --message "<text>" [--title "<t>"] [--dry-run]
    Loads the config. DRY RUN (prints provider, target url with any
    token substring redacted, and the exact JSON payload that WOULD be
    sent; logs notify_dry_run; exits 0; makes NO network call) when ANY
    of the following holds:
      - no config file exists yet
      - config["enabled"] is not literally true
      - config["dry_run"] is true
      - --dry-run was passed on the command line
    Only when enabled && !dry_run && url is a non-empty string does this
    tool attempt urllib.request.urlopen(...) -- that code path is
    unreachable with the shipped (init'd) config. Any send failure
    (network error, bad response, etc.) is caught -- this tool must
    NEVER crash the caller -- logs notify_failed, and exits 1.

Config schema (.harness/notify_config.json, gitignored -- see
.gitignore "Secrets (T-005 messenger config may hold tokens)"):
  {
    "enabled": false,
    "dry_run": true,
    "provider": "generic",
    "url": "",
    "token": "",
    "_activation": "HUMAN GATE (state.json human_gates): to activate, a
        human sets enabled=true, dry_run=false, fills url/token.
        Providers: 'telegram' (url = bot sendMessage endpoint, token =
        bot token, chat_id field required) or 'generic' (POST JSON to
        url)."
  }

Activation path (DO NOT wire until the human gate approves activation):
  1. A human runs `notify.py init` (if not already done), then hand-edits
     .harness/notify_config.json: sets "enabled": true, "dry_run": false,
     fills "provider" ("telegram" or "generic"), "url", "token" (and
     "chat_id" for telegram).
  2. state.json human_gates.require_human_approval_for already lists
     "activating or sending remote webhook notifications (T-005) for the
     first time" -- that approval is what step 1 represents; this tool
     does not ask for confirmation itself, the human editing the config
     file by hand IS the approval act.
  3. OPTIONALLY, a human may wire this as a Claude Code Notification or
     Stop hook in .claude/settings.json, e.g.:

       {
         "hooks": {
           "Stop": [
             {
               "hooks": [
                 {
                   "type": "command",
                   "command": "python3 \"$CLAUDE_PROJECT_DIR/.harness/bin/notify.py\" send --message \"Claude Code session stopped\" --title \"harness\"",
                   "timeout": 10
                 }
               ]
             }
           ],
           "Notification": [
             {
               "hooks": [
                 {
                   "type": "command",
                   "command": "python3 \"$CLAUDE_PROJECT_DIR/.harness/bin/notify.py\" send --message \"Claude Code needs your attention\" --title \"harness\"",
                   "timeout": 10
                 }
               ]
             }
           ]
         }
       }

     DO NOT WIRE THIS HOOK JSON until the human gate approves activation
     (state.json human_gates) -- until then this block is documentation
     only. Even if wired prematurely with the shipped config, `send`
     would still only DRY RUN (enabled=false, dry_run=true, url="") --
     but the gate is about deliberate human intent, not just the config
     defaults, so wiring stays a separate, later, human-approved step.

Notes:
  - stdlib-only, python3 >= 3.9 (no `match` statements, no 3.10+ syntax).
  - Never crashes the caller: send() catches all failures (config
    errors, network errors) and degrades to a logged, non-zero exit
    rather than raising.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

import harness_common as hc

CONFIG_PATH = hc.HARNESS / "notify_config.json"

TEMPLATE = {
    "enabled": False,
    "dry_run": True,
    "provider": "generic",
    "url": "",
    "token": "",
    "_activation": (
        "HUMAN GATE (state.json human_gates): to activate, a human sets "
        "enabled=true, dry_run=false, fills url/token. Providers: "
        "'telegram' (url = bot sendMessage endpoint, token = bot token, "
        "chat_id field required) or 'generic' (POST JSON to url)."
    ),
}


# ------------------------------ helpers -------------------------------------

def _load_config():
    """Return (config_dict_or_None, error_message_or_None)."""
    if not CONFIG_PATH.exists():
        return None, "no config file at {}".format(CONFIG_PATH)
    data = hc.read_json(CONFIG_PATH)
    if data is None:
        return None, "config at {} exists but could not be parsed as JSON".format(CONFIG_PATH)
    return data, None


def _redact_token(text, token):
    """Replace any occurrence of a non-empty token substring in `text` with
    '***REDACTED***'. Safe no-op if token is empty/missing."""
    if not text:
        return text
    if token and isinstance(token, str) and token in text:
        return text.replace(token, "***REDACTED***")
    return text


def _redact_url(url, token):
    return _redact_token(url or "", token or "")


def _should_dry_run(config, cli_dry_run):
    """Returns (dry_run: bool, reason: str)."""
    if cli_dry_run:
        return True, "--dry-run flag passed"
    if config is None:
        return True, "no config file (run `notify.py init`)"
    if config.get("enabled") is not True:
        return True, "config.enabled is not true"
    if config.get("dry_run", True):
        return True, "config.dry_run is true"
    if not (isinstance(config.get("url"), str) and config.get("url").strip()):
        return True, "config.url is empty"
    return False, "enabled && !dry_run && url set"


def _build_payload(config, title, message):
    """Build the exact provider-specific JSON payload that WOULD be sent."""
    provider = (config or {}).get("provider", "generic")
    if provider == "telegram":
        text = "*{}*\n{}".format(title, message) if title else message
        payload = {
            "chat_id": (config or {}).get("chat_id", ""),
            "text": text,
            "parse_mode": "Markdown",
        }
    else:
        payload = {"title": title or "", "message": message}
    return provider, payload


# ------------------------------- commands -----------------------------------

def cmd_init(args):
    del args
    if CONFIG_PATH.exists():
        print(
            "refused: {} already exists. Not overwriting an existing config "
            "(it may hold real secrets or human-set enable flags). Delete it "
            "yourself first if you really want a fresh template.".format(CONFIG_PATH)
        )
        return 1
    hc.atomic_write_json(CONFIG_PATH, TEMPLATE)
    hc.log_event("notify_config_initialized", path=str(CONFIG_PATH))
    print(
        "created: {} (enabled=false, dry_run=true, provider=generic, url/token "
        "empty). This file is gitignored -- see .gitignore. Activation is a "
        "HUMAN GATE: see state.json human_gates and this file's own "
        "'_activation' field.".format(CONFIG_PATH)
    )
    return 0


def cmd_status(args):
    del args
    config, err = _load_config()
    if config is None:
        print("no config (run init)")
        if err:
            print("detail: {}".format(err))
        return 1
    token = config.get("token", "")
    token_display = "***set***" if (isinstance(token, str) and token) else "(empty)"
    url = config.get("url", "")
    url_display = _redact_url(url, token) if url else "(empty)"
    print("config: {}".format(CONFIG_PATH))
    print("  enabled:  {}".format(config.get("enabled", False)))
    print("  dry_run:  {}".format(config.get("dry_run", True)))
    print("  provider: {}".format(config.get("provider", "generic")))
    print("  url:      {}".format(url_display))
    print("  token:    {}".format(token_display))
    dry_run, reason = _should_dry_run(config, False)
    print("  effective send() mode: {} ({})".format("DRY RUN" if dry_run else "LIVE", reason))
    return 0


def cmd_send(args):
    config, load_err = _load_config()
    dry_run, reason = _should_dry_run(config, args.dry_run)
    provider, payload = _build_payload(config, args.title, args.message)
    token = (config or {}).get("token", "")
    url = (config or {}).get("url", "")

    if dry_run:
        redacted_url = _redact_url(url, token) if url else "(no url configured)"
        print("DRY RUN (reason: {}) -- no network call made.".format(reason))
        if load_err and config is None:
            print("note: {}".format(load_err))
        print("provider: {}".format(provider))
        print("target url: {}".format(redacted_url))
        print("payload that WOULD be sent:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        hc.log_event(
            "notify_dry_run",
            provider=provider,
            title=args.title,
            reason=reason,
            url_configured=bool(url),
        )
        return 0

    # LIVE path -- unreachable with the shipped config: reaching here requires
    # a human to have hand-edited notify_config.json to enabled=true,
    # dry_run=false, with a non-empty url (see _should_dry_run above).
    try:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if provider != "telegram" and token:
            headers["Authorization"] = "Bearer {}".format(token)
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = getattr(resp, "status", None) or resp.getcode()
        hc.log_event("notify_sent", provider=provider, title=args.title, status_code=status_code)
        print("sent via {} (status {})".format(provider, status_code))
        return 0
    except Exception as exc:  # noqa: BLE001 -- must never crash the caller
        hc.log_event("notify_failed", provider=provider, title=args.title, error=str(exc)[:400])
        print("send failed ({}): {}".format(provider, exc))
        return 1


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="write a template notify_config.json (refuses to overwrite)").set_defaults(func=cmd_init)
    sub.add_parser("status", help="print config state (token always redacted)").set_defaults(func=cmd_status)

    p_send = sub.add_parser("send", help="send (or dry-run) a notification")
    p_send.add_argument("--message", required=True)
    p_send.add_argument("--title", default=None)
    p_send.add_argument("--dry-run", action="store_true", help="force dry-run regardless of config")
    p_send.set_defaults(func=cmd_send)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
