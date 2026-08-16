#!/bin/bash
# CP-1.2 spike: send an iMessage via AppleScript.
#
#   bash spikes/send_imessage.sh <handle> <text>
#
# <handle> is a phone number (+15551234567) or Apple ID email.
# Handle and text are passed to osascript as `argv`, never interpolated into
# the AppleScript source, so quotes and backslashes in the text are inert.
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "usage: $0 <handle> <text>" >&2
    exit 2
fi

/usr/bin/osascript - "$1" "$2" <<'APPLESCRIPT'
on run argv
    set targetHandle to item 1 of argv
    set msgText to item 2 of argv
    tell application "Messages"
        set svc to 1st service whose service type = iMessage
        send msgText to buddy targetHandle of svc
    end tell
end run
APPLESCRIPT
