#!/usr/bin/env python3
"""
Tests for the claude-content-engine quality gate hooks.

Run with: python3 tests/test_hooks.py

No dependencies beyond the standard library - these run in CI and should
run on any machine with python3.
"""

import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")
sys.path.insert(0, HOOKS_DIR)

from slop_patterns import scan_content  # noqa: E402

SLOPPY_TEXT = (
    "In today's fast-paced world, our game-changer platform will seamlessly "
    "revolutionize your workflow. Let's dive in and delve into the tapestry "
    "of possibilities. In conclusion, it's important to note that this is "
    "very good in order to succeed."
)

CLEAN_TEXT = (
    "We rebuilt the export pipeline last quarter. Batch jobs that took forty "
    "minutes now finish in six, and the on-call pager has been quiet since. "
    "The trade-off: exports are eventually consistent, so the dashboard can "
    "lag a write by up to thirty seconds."
)

# A normal coding-session summary. Blocking this was a real bug: "robust",
# "seamlessly", and "leverage" are ordinary words in technical conversation.
ENGINEERING_TEXT = (
    "I refactored the sync layer so the retry logic is more robust and the "
    "migration between the two schema versions happens seamlessly. The new "
    "adapter also lets us leverage the existing connection pool instead of "
    "opening new sockets, which cut p95 latency by roughly forty percent in "
    "the staging benchmarks."
)


def run_hook(script, payload):
    """Pipe a JSON payload into a hook script and return its parsed output."""
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode, json.loads(result.stdout)


class TestScanContent(unittest.TestCase):
    def test_detects_hard_slop(self):
        findings = scan_content(SLOPPY_TEXT)
        high = [f for f in findings if f["severity"] == "high"]
        matches = {f["match"].lower() for f in high}
        self.assertTrue(any("delve" in m for m in matches))
        self.assertTrue(any("game-changer" in m or "game changer" in m for m in matches))

    def test_detects_weak_copy(self):
        findings = scan_content(SLOPPY_TEXT)
        low = [f for f in findings if f["severity"] == "low"]
        suggestions = " ".join(f["suggestion"] for f in low)
        self.assertIn("in order to", suggestions.lower())

    def test_clean_text_passes(self):
        self.assertEqual(scan_content(CLEAN_TEXT), [])

    def test_short_text_is_skipped(self):
        self.assertEqual(scan_content("delve"), [])

    def test_allows_technical_robust_and_financial_leverage(self):
        text = (
            "The parser needs robust error handling before we ship it, and "
            "the fund's leverage ratio stayed under the covenant threshold "
            "for the third consecutive quarter of the fiscal year."
        )
        self.assertEqual(scan_content(text), [])

    def test_flags_excessive_exclamations(self):
        text = "Buy now! Amazing deal! Don't wait! Act fast! " * 3
        findings = scan_content(text)
        self.assertTrue(any(f["type"] == "tone" for f in findings))


class TestQualityGate(unittest.TestCase):
    def test_flags_sloppy_markdown_write(self):
        code, output = run_hook("quality_gate.py", {
            "tool_input": {"file_path": "/tmp/post.md", "content": SLOPPY_TEXT},
        })
        self.assertEqual(code, 0)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("Must fix", context)

    def test_ignores_code_files(self):
        code, output = run_hook("quality_gate.py", {
            "tool_input": {"file_path": "/tmp/script.py", "content": SLOPPY_TEXT},
        })
        self.assertEqual(code, 0)
        self.assertEqual(output, {})

    def test_clean_content_passes(self):
        code, output = run_hook("quality_gate.py", {
            "tool_input": {"file_path": "/tmp/post.md", "content": CLEAN_TEXT},
        })
        self.assertEqual(code, 0)
        self.assertEqual(output, {})

    def test_edit_tool_new_string_is_scanned(self):
        code, output = run_hook("quality_gate.py", {
            "tool_input": {"file_path": "/tmp/post.md", "new_string": SLOPPY_TEXT},
        })
        self.assertEqual(code, 0)
        self.assertIn("hookSpecificOutput", output)

    def test_malformed_input_does_not_crash(self):
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "quality_gate.py")],
            input="not json",
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {})


class TestContentReview(unittest.TestCase):
    def test_blocks_stop_on_sloppy_final_message(self):
        code, output = run_hook("content_review.py", {
            "last_assistant_message": SLOPPY_TEXT,
            "stop_hook_active": False,
        })
        self.assertEqual(code, 0)
        self.assertEqual(output.get("decision"), "block")
        self.assertIn("Rewrite", output.get("reason", ""))

    def test_allows_stop_on_clean_message(self):
        code, output = run_hook("content_review.py", {
            "last_assistant_message": CLEAN_TEXT,
            "stop_hook_active": False,
        })
        self.assertEqual(code, 0)
        self.assertEqual(output, {})

    def test_never_blocks_twice(self):
        code, output = run_hook("content_review.py", {
            "last_assistant_message": SLOPPY_TEXT,
            "stop_hook_active": True,
        })
        self.assertEqual(code, 0)
        self.assertEqual(output, {})

    def test_allows_short_conversational_replies(self):
        code, output = run_hook("content_review.py", {
            "last_assistant_message": "Done - the file is a real game-changer now.",
            "stop_hook_active": False,
        })
        self.assertEqual(code, 0)
        self.assertEqual(output, {})

    def test_engineering_talk_is_not_blocked(self):
        code, output = run_hook("content_review.py", {
            "last_assistant_message": ENGINEERING_TEXT,
            "stop_hook_active": False,
        })
        self.assertEqual(code, 0)
        self.assertEqual(output, {})

    def test_two_hard_matches_are_tolerated(self):
        message = (
            CLEAN_TEXT + " Some would call the rewrite a game-changer, and "
            "yes, it's worth noting the pager stayed quiet through launch week."
        )
        code, output = run_hook("content_review.py", {
            "last_assistant_message": message,
            "stop_hook_active": False,
        })
        self.assertEqual(code, 0)
        self.assertEqual(output, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
