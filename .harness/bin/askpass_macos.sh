#!/bin/sh
# askpass helper for macOS, so `ssh-add -c` confirm-on-use can actually prompt.
#
# WHY THIS EXISTS. `ssh-add -c` makes ssh-agent ask for confirmation on every single
# use of a key. Asking requires a program that can display a prompt. A stock macOS
# has none, and OPENSSH DOES NOT FAIL OPEN: with nothing to ask with, the agent
# refuses the signature outright ("agent refused operation"). That refusal is the
# guard working. This script supplies the missing prompt rather than removing the
# guard.
#
# The alternative -- reloading the key without -c, or signing with `-f <privkey>` to
# bypass the agent -- makes confirm-on-use decorative and means a signature can
# happen without the operator present. For a key whose whole purpose is that only a
# human can wield it, that is the one property worth preserving.
#
# CONTRACT. ssh-agent invokes an askpass in two different modes and they are not
# interchangeable:
#   * confirmation  -- SSH_ASKPASS_PROMPT=confirm. The agent reads the EXIT STATUS.
#                      0 authorizes the operation, anything else denies it.
#   * passphrase    -- no such variable. The agent reads STDOUT.
# Getting these backwards either auto-approves every request or feeds a dialog
# button name in as a passphrase, so the two paths are kept strictly separate below.
#
# USAGE
#   chmod +x .harness/bin/askpass_macos.sh
#   export SSH_ASKPASS="$PWD/.harness/bin/askpass_macos.sh"
#   export SSH_ASKPASS_REQUIRE=force    # required: no TTY fallback, always prompt
#
# This script holds no secret, contacts no network, and writes no file.

PROMPT=${1:-"ssh-agent request"}

# Escape double quotes and backslashes for AppleScript's string literal.
ESCAPED=$(printf '%s' "$PROMPT" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')

if [ "$SSH_ASKPASS_PROMPT" = "confirm" ]; then
    # Confirmation mode: exit status is the answer. Default to DENY on any error,
    # timeout or dismissal, so a broken dialog can never approve a signature.
    ANSWER=$(osascript <<APPLESCRIPT 2>/dev/null
try
    set dlg to display dialog "$ESCAPED" ¬
        with title "Harness: autorizar firma" ¬
        buttons {"Denegar", "Autorizar"} ¬
        default button "Denegar" ¬
        cancel button "Denegar" ¬
        with icon caution ¬
        giving up after 120
    if gave up of dlg then
        return "DENY"
    end if
    if button returned of dlg is "Autorizar" then
        return "ALLOW"
    end if
    return "DENY"
on error
    return "DENY"
end try
APPLESCRIPT
)
    [ "$ANSWER" = "ALLOW" ] && exit 0
    exit 1
fi

# Passphrase mode: the answer goes to stdout.
osascript <<APPLESCRIPT 2>/dev/null
try
    set dlg to display dialog "$ESCAPED" ¬
        with title "Harness: frase de paso" ¬
        default answer "" ¬
        with hidden answer ¬
        buttons {"Cancelar", "OK"} ¬
        default button "OK" ¬
        cancel button "Cancelar"
    return text returned of dlg
on error
    return ""
end try
APPLESCRIPT
