"""
Shared slop-detection patterns and scanner for the claude-content-engine hooks.

Both quality_gate.py (PostToolUse) and content_review.py (Stop) import from
this module so the pattern lists can't drift apart.
"""

import os
import re

# Users can add their own banned phrases, one per line. Lines starting with
# "#" and blank lines are ignored. The env var exists mainly so tests can
# point at a fixture instead of the real file.
CUSTOM_PHRASES_FILE = os.environ.get(
    "CONTENT_ENGINE_BANNED_PHRASES",
    os.path.join(os.path.expanduser("~"), ".claude-content-engine", "banned-phrases.txt"),
)

# --- AI slop patterns ---
# Phrases that almost always signal lazy AI-generated text, by severity.

HARD_SLOP = [
    # Words/phrases that are dead giveaways
    r"\bdelve\b",
    r"\btapestry\b",
    r"\bunlock the power\b",
    r"\bin today'?s (?:fast-paced|ever-changing|digital|modern) (?:world|landscape|era|age)\b",
    r"\bit'?s important to note\b",
    r"\bit'?s worth noting\b",
    r"\bin the realm of\b",
    r"\bgame[ -]?changer\b",
    r"\bparadigm shift\b",
    r"\bsynergy\b",
    r"\bholistic approach\b",
    r"\bcut(?:ting)?[ -]?edge\b",
    r"\binnovative solution\b",
    r"\bempowering\b",
    r"\btransformative\b",
    r"\bgroundbreaking\b",
    r"\brevolutionize\b",
    r"\bworld-class\b",
    r"\bnot just .+? but (?:also )?.+? it'?s\b",
    r"\bwhether you'?re .+? or .+?,\b",
    r"\bfrom .+? to .+?, we'?ve got you covered\b",
]

SOFT_SLOP = [
    # Phrases that are sometimes fine but often signal AI filler.
    # "seamless", "leverage", and "robust" live here rather than in HARD_SLOP:
    # they're overused in marketing copy but ordinary in technical writing,
    # and hard-flagging them made the Stop hook police normal engineering
    # conversation.
    r"\bseamless(?:ly)?\b",
    r"\bleverage\b(?! (?:ratio|point))",  # allow financial usage
    r"\brobust\b(?! (?:error|test|check))",  # allow technical usage
    r"\bin conclusion\b",
    r"\bas we'?ve (?:seen|discussed|explored)\b",
    r"\blet'?s (?:dive|explore|unpack)\b",
    r"\bwithout further ado\b",
    r"\bin this (?:article|blog post|guide|piece)\b",
    r"\bhope this (?:helps|was helpful|article)\b",
    r"\bthe (?:landscape|world) of\b",
    r"\bnavigat(?:e|ing) the\b",
    r"\bharnessing?\b",
    r"\bfoster(?:ing)?\b",
    r"\bpivotal\b",
    r"\bmyriad\b",
    r"\bplethora\b",
    r"\bcommence\b",
    r"\butilize\b",
    r"\bfacilitate\b",
]

# --- Weak copy patterns ---
WEAK_PATTERNS = [
    (r"\bvery (?:good|nice|great|important|big|small)\b", "Replace 'very + weak adjective' with a stronger word"),
    (r"\breally (?:good|nice|great|important)\b", "Replace 'really + weak adjective' with a stronger word"),
    (r"\b(?:I|we) (?:think|believe|feel) that\b", "Cut the hedge - just state the claim"),
    (r"\bin order to\b", "Replace 'in order to' with 'to'"),
    (r"\bdue to the fact that\b", "Replace 'due to the fact that' with 'because'"),
    (r"\bat the end of the day\b", "Cliche - cut or replace"),
    (r"\bmoving forward\b", "Corporate filler - cut it"),
    (r"\bneedless to say\b", "If it's needless, don't say it"),
    (r"\bit goes without saying\b", "Then don't say it"),
]


def load_custom_patterns(path=None):
    """Read the user's banned-phrases file into a list of regex patterns.

    Each phrase is escaped and matched literally, with word boundaries added
    where the phrase starts or ends with a word character (so "very unique"
    won't match inside "delivery uniquely", but a phrase ending in "!" still
    works). A missing or unreadable file just means no custom patterns.
    """
    if path is None:
        path = CUSTOM_PHRASES_FILE
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []

    patterns = []
    for line in lines:
        phrase = line.strip()
        if not phrase or phrase.startswith("#"):
            continue
        prefix = r"\b" if (phrase[0].isalnum() or phrase[0] == "_") else ""
        suffix = r"\b" if (phrase[-1].isalnum() or phrase[-1] == "_") else ""
        patterns.append(prefix + re.escape(phrase) + suffix)
    return patterns


def _first_match(pattern, text):
    """Return the first match of pattern in text, or None."""
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0).strip() if match else None


def scan_content(text, custom_patterns=None):
    """Scan text for quality issues. Returns a list of findings.

    custom_patterns overrides the user's banned-phrases file (pass [] to
    disable it); by default the file is loaded and merged in. Custom phrases
    count as hard findings - the user banned them on purpose.
    """
    findings = []

    if not text or len(text.strip()) < 50:
        return findings

    if custom_patterns is None:
        custom_patterns = load_custom_patterns()

    # Check the user's own banned phrases
    for pattern in custom_patterns:
        matched = _first_match(pattern, text)
        if matched:
            findings.append({
                "severity": "high",
                "type": "custom_phrase",
                "match": matched,
                "suggestion": f"'{matched}' is on your banned phrases list - rewrite without it."
            })

    # Check hard slop
    for pattern in HARD_SLOP:
        matched = _first_match(pattern, text)
        if matched:
            findings.append({
                "severity": "high",
                "type": "ai_slop",
                "match": matched,
                "suggestion": f"Remove or rewrite: '{matched}' is a common AI-generated filler phrase."
            })

    # Check soft slop (only flag if 2+ found)
    soft_matches = []
    for pattern in SOFT_SLOP:
        matched = _first_match(pattern, text)
        if matched:
            soft_matches.append(matched)

    if len(soft_matches) >= 2:
        findings.append({
            "severity": "medium",
            "type": "ai_pattern",
            "match": ", ".join(soft_matches[:5]),
            "suggestion": f"Multiple AI-sounding phrases detected: {', '.join(soft_matches[:5])}. Rewrite to sound more natural."
        })

    # Check weak patterns
    for pattern, suggestion in WEAK_PATTERNS:
        matched = _first_match(pattern, text)
        if matched:
            findings.append({
                "severity": "low",
                "type": "weak_copy",
                "match": matched,
                "suggestion": suggestion
            })

    # Check for excessive exclamation marks (sign of fake enthusiasm)
    exclamation_count = text.count("!")
    sentence_count = max(len(re.split(r"[.!?]+", text)) - 1, 1)
    if exclamation_count > 3 and exclamation_count / sentence_count > 0.3:
        findings.append({
            "severity": "medium",
            "type": "tone",
            "match": f"{exclamation_count} exclamation marks in {sentence_count} sentences",
            "suggestion": "Too many exclamation marks - reads as fake enthusiasm. Keep to 1-2 per piece max."
        })

    return findings
