# Changelog

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
