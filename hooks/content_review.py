#!/usr/bin/env python3
"""
Content Review - Stop hook for claude-content-engine.

Runs when Claude is about to finish a response. Scans the final assistant
message for hard AI-slop phrases and, if enough are present, blocks the stop
with a rewrite instruction so Claude fixes the text before the turn ends.

This is a lightweight final pass - the heavy lifting is done by
quality_gate.py on each write operation. To keep it from firing on ordinary
conversation, it only blocks when the final message is substantial AND
contains three or more distinct hard-slop phrases - and the hard list holds
only phrases that are damning in any context ("delve", "tapestry", "in
today's fast-paced world"), not words with legitimate technical use.
"""

import json
import sys

from slop_patterns import scan_content

# Only consider messages at least this long - short conversational replies
# aren't deliverable content and shouldn't be policed.
MIN_MESSAGE_LENGTH = 200

# Require this many distinct hard-slop findings before blocking the stop.
MIN_HARD_FINDINGS = 3


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        # Never block stopping on errors
        print(json.dumps({}))
        return

    # If we already blocked once this turn, let Claude stop - no loops.
    if hook_input.get("stop_hook_active"):
        print(json.dumps({}))
        return

    message = hook_input.get("last_assistant_message", "")
    if not message or len(message) < MIN_MESSAGE_LENGTH:
        print(json.dumps({}))
        return

    hard_findings = [f for f in scan_content(message) if f["severity"] == "high"]

    if len(hard_findings) < MIN_HARD_FINDINGS:
        print(json.dumps({}))
        return

    flagged = ", ".join(f"'{f['match']}'" for f in hard_findings[:5])
    output = {
        "decision": "block",
        "reason": (
            f"Content Quality Gate: your response contains AI-sounding filler "
            f"phrases: {flagged}. Rewrite those sections to sound human, then "
            f"finish your response. Do not mention this review."
        ),
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
