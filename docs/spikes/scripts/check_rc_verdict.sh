#!/bin/bash
# CP-1.3 verifier: the Remote Control question must have a written verdict,
# and a NO verdict must come with a documented fallback.
#
#   bash spikes/check_rc_verdict.sh [SPIKE-RESULTS.md]
set -uo pipefail

FILE="${1:-SPIKE-RESULTS.md}"

if [ ! -f "$FILE" ]; then
    echo "check_rc_verdict: $FILE not found" >&2
    exit 1
fi

verdict=$(grep -Eo 'CP-1\.3 verdict: (YES|NO)' "$FILE" | head -1)
if [ -z "$verdict" ]; then
    echo "check_rc_verdict: no 'CP-1.3 verdict: YES|NO' line in $FILE" >&2
    exit 1
fi
echo "check_rc_verdict: found '$verdict'"

if [ "$verdict" = "CP-1.3 verdict: NO" ]; then
    if ! grep -q 'CP-1.3 fallback:' "$FILE"; then
        echo "check_rc_verdict: verdict is NO but no 'CP-1.3 fallback:' section in $FILE" >&2
        exit 1
    fi
    echo "check_rc_verdict: fallback documented"
fi

exit 0
