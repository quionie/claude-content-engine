#!/usr/bin/env python3
"""
Content Quality Gate - PostToolUse hook for claude-content-engine.

Scans written content for AI slop patterns, cliches, weak copy, and common
low-effort writing. Findings are returned via hookSpecificOutput.additionalContext,
which Claude Code injects into Claude's context as a system reminder - so Claude
sees the feedback and self-corrects before the user reads the final output.

This hook runs after Write/Edit operations on content files
(markdown, text, etc.) - not on code files.
"""

import json
import os
import sys

from slop_patterns import scan_content

# File extensions that contain written content (not code)
CONTENT_EXTENSIONS = {
    ".md", ".mdx", ".txt", ".html", ".htm",
}


def should_scan(filepath):
    """Only scan known content file types. Everything else is skipped."""
    if not filepath:
        return False
    _, ext = os.path.splitext(filepath)
    return ext.lower() in CONTENT_EXTENSIONS


def format_findings(findings):
    """Format findings into feedback for Claude."""
    if not findings:
        return None

    high = [f for f in findings if f["severity"] == "high"]
    medium = [f for f in findings if f["severity"] == "medium"]
    low = [f for f in findings if f["severity"] == "low"]

    parts = ["Content Quality Gate - issues detected in the file you just wrote:\n"]

    if high:
        parts.append("Must fix (AI slop detected):")
        for f in high:
            parts.append(f"- '{f['match']}' - {f['suggestion']}")
        parts.append("")

    if medium:
        parts.append("Should fix:")
        for f in medium:
            parts.append(f"- '{f['match']}' - {f['suggestion']}")
        parts.append("")

    if low:
        parts.append("Consider fixing:")
        for f in low:
            parts.append(f"- '{f['match']}' - {f['suggestion']}")
        parts.append("")

    parts.append(
        "Edit the file now to rewrite the flagged sections before presenting "
        "the content to the user. Do not mention this review."
    )

    return "\n".join(parts)


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({}))
        return

    tool_input = hook_input.get("tool_input", {})
    filepath = tool_input.get("file_path", tool_input.get("path", ""))

    if not should_scan(filepath):
        print(json.dumps({}))
        return

    # The content that was written, depending on which tool ran
    content = (
        tool_input.get("content")        # Write
        or tool_input.get("new_string")  # Edit
        or tool_input.get("new_source")  # NotebookEdit
        or ""
    )

    if not content:
        print(json.dumps({}))
        return

    message = format_findings(scan_content(content))

    if message:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": message,
            }
        }
    else:
        output = {}

    print(json.dumps(output))


if __name__ == "__main__":
    main()
