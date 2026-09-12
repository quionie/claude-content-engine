"""
Structural slop detection for the claude-content-engine quality gate.

Word-level slop ("delve", "tapestry") is easy to avoid now. What gives
AI-shaped writing away in 2026 is rhythm and shape: the "It's not X. It's Y."
contrast, rhetorical questions that answer themselves, tidy groups of three,
an em-dash in every sentence, paragraphs of identical length, the formulaic
wrap-up. Readers clock these in seconds.

Every check here is a measurable metric with an explicit threshold, computed
on prose only (code blocks, headings, list items, and tables are excluded),
and each needs a minimum amount of text before it can fire - short pieces
and ordinary human variation shouldn't trip it.
"""

import re
import statistics

# --- Minimum sample sizes before a metric is allowed to fire ---
MIN_WORDS = 120
MIN_SENTENCES_FOR_RHYTHM = 10
MIN_PARAGRAPHS_FOR_UNIFORMITY = 4

# --- Thresholds ---
EM_DASH_PER_100_WORDS = 1.5      # and at least EM_DASH_MIN_COUNT total
EM_DASH_MIN_COUNT = 4
CONTRAST_MIN_COUNT = 2           # "not X, but Y" / "It's not X. It's Y."
RHETORICAL_MIN_COUNT = 3         # questions in prose ...
RHETORICAL_MIN_RATIO = 0.15      # ... and as a share of sentences
FRAGMENT_QUESTION_MIN = 2        # "Why? Because..." / "The catch?"
TRIPLE_MIN_COUNT = 3             # "faster, cheaper, and smarter"
SENTENCE_CV_MAX = 0.30           # coefficient of variation of sentence length
PARAGRAPH_CV_MAX = 0.25          # coefficient of variation of paragraph length
GRADE_LEVEL_MAX = 13.0           # Flesch-Kincaid grade
LONG_SENTENCE_MEAN = 28          # mean words per sentence

CONTRAST_PATTERNS = [
    r"\bnot (?:just|only|merely|simply)\b[^.!?\n]{2,80}?[,;.]\s*(?:but|it'?s|this is|that'?s)\b",
    r"\b(?:it'?s|this is|that'?s|this isn'?t|that isn'?t|isn'?t) not (?:a |an |about |the )?[^.!?\n]{2,60}?\.\s+(?:it'?s|this is|that'?s)\b",
]

FRAGMENT_QUESTION = r"(?:^|[.!?]\s+)(?:why|how|the (?:result|catch|answer|problem|kicker|best part|takeaway|twist|lesson))\?"

FORMULAIC_CLOSERS = [
    r"^(?:in (?:conclusion|summary|short)|to (?:sum|wrap) (?:up|it up|things up)|ultimately|the bottom line|final thoughts)\b",
    r"\b(?:what do you think|let me know in the comments|drop a comment|share this with someone|follow (?:me|us) for more|thanks for reading)\b",
    r"\bso,? (?:what'?s next|where do we go from here)\b",
]

TRIPLE_PATTERN = r"\b\w+, \w+, and \w+\b"


def extract_prose(text):
    """Return (paragraphs, sentences) of prose, dropping non-prose markdown."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)  # frontmatter
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)                  # fenced code
    text = re.sub(r"`[^`\n]*`", "", text)                                   # inline code
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)                  # links -> text

    def is_prose_line(line):
        if line.startswith(("#", "|", ">", "- ", "* ", "+ ", "<")):
            return False
        return not re.match(r"^\d+[.)] ", line)

    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        lines = [l for l in lines if is_prose_line(l)]
        if lines:
            paragraphs.append(" ".join(lines))

    prose = " ".join(paragraphs)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose) if len(s.strip().split()) >= 2]
    return paragraphs, sentences


def _cv(values):
    """Coefficient of variation: how much values spread around their mean."""
    if len(values) < 2:
        return None
    mean = statistics.mean(values)
    if mean == 0:
        return None
    return statistics.pstdev(values) / mean


def _syllables(word):
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    groups = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not word.endswith(("le", "ee")) and groups > 1:
        groups -= 1
    return max(groups, 1)


def grade_level(sentences):
    """Flesch-Kincaid grade level for a list of sentences."""
    words = [w for s in sentences for w in s.split()]
    if not words or not sentences:
        return None
    syllables = sum(_syllables(w) for w in words)
    return 0.39 * (len(words) / len(sentences)) + 11.8 * (syllables / len(words)) - 15.59


def _finding(kind, severity, match, suggestion):
    return {"severity": severity, "type": f"structure_{kind}", "match": match, "suggestion": suggestion}


def scan_structure(text):
    """Scan prose for AI-shaped structure. Returns a list of findings."""
    paragraphs, sentences = extract_prose(text)
    prose = " ".join(paragraphs)
    words = prose.split()
    word_count = len(words)
    findings = []

    if word_count < MIN_WORDS:
        return findings

    # Em-dash density
    dashes = len(re.findall(r"—|–| -- ", prose))
    per_100 = dashes / word_count * 100
    if dashes >= EM_DASH_MIN_COUNT and per_100 > EM_DASH_PER_100_WORDS:
        findings.append(_finding(
            "em_dashes", "medium",
            f"{dashes} em-dashes in {word_count} words ({per_100:.1f} per 100)",
            "Em-dash overload reads as AI. Turn most into commas, periods, or parentheses.",
        ))

    # "Not X, but Y" / "It's not X. It's Y." contrast constructions
    contrasts = sum(len(re.findall(p, prose, re.IGNORECASE)) for p in CONTRAST_PATTERNS)
    if contrasts >= CONTRAST_MIN_COUNT:
        findings.append(_finding(
            "contrast", "medium",
            f"{contrasts} 'not X, but Y' contrast constructions",
            "The 'It's not X. It's Y.' move is the most recognizable AI tic of the moment. Keep at most one, and say the Y directly.",
        ))

    # Rhetorical questions
    questions = sum(1 for s in sentences if s.endswith("?"))
    fragments = len(re.findall(FRAGMENT_QUESTION, prose, re.IGNORECASE))
    if sentences and questions >= RHETORICAL_MIN_COUNT and questions / len(sentences) > RHETORICAL_MIN_RATIO:
        findings.append(_finding(
            "rhetorical", "medium",
            f"{questions} questions in {len(sentences)} sentences",
            "Too many rhetorical questions that answer themselves. State the point instead of asking it.",
        ))
    elif fragments >= FRAGMENT_QUESTION_MIN:
        findings.append(_finding(
            "rhetorical", "low",
            f"{fragments} one-word question setups ('Why?', 'The catch?')",
            "The 'Why? Because...' setup is a tell. Cut the question and keep the answer.",
        ))

    # Tidy groups of three
    triples = len(re.findall(TRIPLE_PATTERN, prose))
    if triples >= TRIPLE_MIN_COUNT:
        findings.append(_finding(
            "triples", "low",
            f"{triples} 'A, B, and C' single-word triples",
            "Groups of three everywhere feel machine-tidy. Break some into pairs, or let one item carry a clause.",
        ))

    # Sentence rhythm (burstiness)
    if len(sentences) >= MIN_SENTENCES_FOR_RHYTHM:
        lengths = [len(s.split()) for s in sentences]
        mean_len = statistics.mean(lengths)
        cv = _cv(lengths)
        if cv is not None and cv < SENTENCE_CV_MAX and 8 <= mean_len <= 35:
            findings.append(_finding(
                "rhythm", "medium",
                f"sentences average {mean_len:.0f} words with little variation (cv {cv:.2f})",
                "Metronomic rhythm. Human writing is bursty: follow a long sentence with a short one. Vary length on purpose.",
            ))
        if mean_len > LONG_SENTENCE_MEAN:
            findings.append(_finding(
                "long_sentences", "low",
                f"sentences average {mean_len:.0f} words",
                "Sentences are long on average. Split a few - especially the openers.",
            ))

    # Paragraph uniformity
    if len(paragraphs) >= MIN_PARAGRAPHS_FOR_UNIFORMITY:
        plens = [len(p.split()) for p in paragraphs]
        cv = _cv(plens)
        if cv is not None and cv < PARAGRAPH_CV_MAX:
            findings.append(_finding(
                "paragraphs", "low",
                f"{len(paragraphs)} paragraphs all around {statistics.mean(plens):.0f} words (cv {cv:.2f})",
                "Every paragraph is the same size. Let one run long and drop a one-liner somewhere.",
            ))

    # Formulaic closer
    if paragraphs:
        last = paragraphs[-1].strip()
        for pattern in FORMULAIC_CLOSERS:
            m = re.search(pattern, last, re.IGNORECASE)
            if m:
                findings.append(_finding(
                    "closer", "medium",
                    m.group(0).strip(),
                    "Formulaic wrap-up. End on the strongest specific point, not a summary or an engagement ask.",
                ))
                break

    # Readability
    grade = grade_level(sentences) if sentences else None
    if grade is not None and grade > GRADE_LEVEL_MAX:
        findings.append(_finding(
            "readability", "low",
            f"reads at grade level {grade:.0f}",
            "Dense for content that has to be skimmed. Shorter words, shorter sentences.",
        ))

    return findings
