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
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")
sys.path.insert(0, HOOKS_DIR)

# Isolate every test from a real banned-phrases file on this machine.
os.environ["CONTENT_ENGINE_BANNED_PHRASES"] = os.devnull

from slop_patterns import load_custom_patterns, scan_content  # noqa: E402
from structure import scan_structure  # noqa: E402

# AI-shaped prose: no banned words, but every structural tell at once.
AI_SHAPED_TEXT = """Most teams think they have a writing problem — but that's not the real issue. It's not about writing faster. It's about writing smarter. Why? Because the tools have changed, the audience has changed, and the standards have changed. The result? Content that is polished, consistent, and forgettable.

Here's what actually happens when you automate content — you get volume without voice. The posts are clean, correct, and completely empty. Readers notice — even when they can't say why. They scroll past without a second thought. Engagement drops, reach drops, and trust drops with it.

So what's the alternative — and does it actually work? The answer is a system that learns from results. It's not a tool. It's a loop. Every piece gets logged, measured, and graded. The findings become defaults — automatically. Your drafts get sharper, tighter, and more specific over time.

The catch? It takes discipline to log everything — but the payoff compounds quickly. Teams that commit see the difference within a month — better hooks, better rhythm, better results. That's the difference between writing content and building a content engine — and it matters more than ever.

In conclusion, the future of content belongs to teams that learn from what they ship. What do you think? Let me know in the comments below."""


def metronomic_text(n=12):
    """n sentences of nearly identical length - the rhythm an LLM falls into."""
    base = "The team shipped the update on time and the customers noticed the change right away"
    return " ".join(base + (" again." if i % 2 else " today.") for i in range(n))

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


def run_hook(script, payload, phrases_file=None):
    """Pipe a JSON payload into a hook script and return its parsed output.

    phrases_file points the hook at a banned-phrases fixture; by default the
    hook sees an empty file so tests don't depend on this machine's config.
    """
    env = dict(os.environ)
    env["CONTENT_ENGINE_BANNED_PHRASES"] = phrases_file or os.devnull
    result = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    return result.returncode, json.loads(result.stdout)


def write_phrases(*lines):
    """Write a banned-phrases fixture file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    f.write("\n".join(lines) + "\n")
    f.close()
    return f.name


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


class TestStructure(unittest.TestCase):
    def types(self, text):
        return {f["type"] for f in scan_structure(text)}

    def test_ai_shaped_prose_trips_multiple_checks(self):
        found = self.types(AI_SHAPED_TEXT)
        for expected in ("structure_em_dashes", "structure_contrast",
                         "structure_rhetorical", "structure_closer"):
            self.assertIn(expected, found)

    def test_metronomic_sentences_flagged(self):
        self.assertIn("structure_rhythm", self.types(metronomic_text()))

    def test_real_human_prose_passes(self):
        readme = open(os.path.join(REPO_ROOT, "README.md"), encoding="utf-8").read()
        self.assertEqual(scan_structure(readme), [])

    def test_short_text_never_fires(self):
        self.assertEqual(scan_structure("Short — dashy — text — here — done — ok."), [])

    def test_code_blocks_are_ignored(self):
        code = "```\n" + ("x = a — b — c — d\n" * 40) + "```\n"
        prose = "The migration finished ahead of schedule. " * 30
        self.assertNotIn("structure_em_dashes", self.types(code + prose))

    def test_list_items_are_not_sentences(self):
        bullets = "\n".join("- Long and flowing?" for _ in range(8))
        prose = "The export pipeline was rebuilt last quarter and the pager has been quiet since then. " * 10
        self.assertNotIn("structure_rhetorical", self.types(prose + "\n\n" + bullets))

    def test_structure_findings_reach_claude_via_quality_gate(self):
        code, output = run_hook("quality_gate.py", {
            "tool_input": {"file_path": "/tmp/post.md", "content": AI_SHAPED_TEXT},
        })
        self.assertEqual(code, 0)
        self.assertIn("em-dash", output["hookSpecificOutput"]["additionalContext"])

    def test_structure_alone_never_blocks_a_stop(self):
        code, output = run_hook("content_review.py", {
            "last_assistant_message": AI_SHAPED_TEXT,
            "stop_hook_active": False,
        })
        self.assertEqual(code, 0)
        self.assertEqual(output, {})


class TestCustomPhrases(unittest.TestCase):
    def test_parses_file_skipping_comments_and_blanks(self):
        path = write_phrases("# my cringe list", "", "circle back", "synergize")
        try:
            self.assertEqual(len(load_custom_patterns(path)), 2)
        finally:
            os.unlink(path)

    def test_missing_file_means_no_patterns(self):
        self.assertEqual(load_custom_patterns("/nonexistent/nope.txt"), [])

    def test_custom_phrase_is_a_hard_finding(self):
        findings = scan_content(
            CLEAN_TEXT + " We should circle back on the dashboard question.",
            custom_patterns=load_custom_patterns(
                path := write_phrases("circle back")
            ),
        )
        os.unlink(path)
        custom = [f for f in findings if f["type"] == "custom_phrase"]
        self.assertEqual(len(custom), 1)
        self.assertEqual(custom[0]["severity"], "high")

    def test_whole_word_matching(self):
        path = write_phrases("ai")
        try:
            patterns = load_custom_patterns(path)
            self.assertEqual(
                scan_content(CLEAN_TEXT + " That idea stayed in my brain.",
                             custom_patterns=patterns),
                [],
            )
        finally:
            os.unlink(path)

    def test_quality_gate_flags_banned_phrase_in_content_file(self):
        path = write_phrases("circle back")
        try:
            code, output = run_hook("quality_gate.py", {
                "tool_input": {
                    "file_path": "/tmp/post.md",
                    "content": CLEAN_TEXT + " Let's circle back next week.",
                },
            }, phrases_file=path)
        finally:
            os.unlink(path)
        self.assertEqual(code, 0)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("circle back", context)
        self.assertIn("banned phrases list", context)


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
