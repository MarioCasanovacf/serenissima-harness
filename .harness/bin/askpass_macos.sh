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
# SCOPE, stated exactly. This helper only reaches an agent the operator starts
# themselves, because that agent inherits SSH_ASKPASS from the shell. It does NOT
# reach Apple's launchd-managed agent, which is what SSH_AUTH_SOCK points at by
# default and which has its own environment. Exporting SSH_ASKPASS in a shell fixes
# the client and does nothing for that agent. So this script is Route A of
# OPERATOR-ENROLMENT.md, not the default route.
#
# The default route signs with `-f <privkey>` and no -U, which does not involve an
# agent at all and demands the key's passphrase on the terminal every time. An
# earlier version of this header called that route "decorative". That was WRONG for
# a passphrase-protected key: a secret the operator must type is not decorative. The
# property both routes keep is the only one that matters -- no signature without the
# operator present. Reloading the key WITHOUT -c, or stripping the passphrase, is
# what breaks it, and both remain forbidden.
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
