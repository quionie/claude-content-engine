# Changelog

## 2.4.1

- Cut output bloat in the four biggest skills. An evaluation found skill outputs running 1.7-2.8x longer than needed, with only 33-49% of each file being usable content, because analytical scaffolding (SERP landscape, atomic-units breakdown, sequence maps, engagement plans, benchmark tables, distribution plans) was printed as deliverables. Blog Post Architect, Email Sequence Builder, Social Media Calendar, and Content Repurposer now return the requested content plus at most 5 lines of notes by default, and offer the extras in one line for anyone who wants them.

## 2.4.0

- Structural slop detection. The quality gate now grades shape, not just vocabulary: em-dash density, "It's not X. It's Y." contrast constructions, rhetorical-question density, tidy groups of three, metronomic sentence length, uniform paragraph length, formulaic closers, and a Flesch-Kincaid readability grade. Every check is a measured metric with an explicit threshold and a minimum sample size; prose is extracted first so code, headings, lists, and tables are ignored.
- Structural findings feed back to Claude through the PostToolUse gate on content files. They never block the Stop hook on their own.
- A few stock openers ("here's the thing", "let's be honest", "picture this") added to soft slop.

## 2.3.0

- New skill: Content Retro - the learning loop. Pulls real performance data (connected analytics tools, or numbers you paste), compares winners against losers with honest evidence rules, and writes findings back into the engine's memory so future drafts start smarter.
- Two new memory files: `content-log.md` (everything published, with metrics as they land) and `learnings.md` (data-backed findings and tracked experiments).
- Drafting skills now read `learnings.md` and apply solid findings as defaults; running experiments are treated as instructions.
- Redesigned the landing page.

## 2.2.0

- User-defined banned phrases: add your own cringe words to `~/.claude-content-engine/banned-phrases.txt` (one per line, `#` comments) and the quality gate flags them as must-fix everywhere.
- Content Memory now saves "never say X" feedback to the banned phrases file, so preferences you state once get enforced automatically.
- The banned-phrases file path can be overridden with the `CONTENT_ENGINE_BANNED_PHRASES` env var.

## 2.1.0

- Fixed the install flow: the repo now ships a real `marketplace.json`, and the installer registers and installs through the `claude plugin` CLI instead of hand-editing config files.
- Reworked the quality gate so feedback actually reaches Claude: the PostToolUse hook returns findings as `additionalContext`, and the Stop hook inspects the final message and can block completion until flagged phrases are rewritten.
- Tuned the gate for technical conversation: "seamless", "leverage", and "robust" moved from hard slop to soft slop, and the Stop hook requires three or more distinct hard-slop phrases before blocking.
- Moved the slop patterns into a shared module, added a test suite, and added CI.
- Refreshed the README: current install commands, accurate hook behavior, working docs links.

## 2.0.0

- Added skill chaining (Content Workflow), persistent content memory, and the quality gate hooks.

## 1.0.0

- Initial release: 6 content skills with install script.
