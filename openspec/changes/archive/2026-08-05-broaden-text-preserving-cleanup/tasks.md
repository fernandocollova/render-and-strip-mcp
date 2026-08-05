## 1. Text-preserving cleanup policy

- [x] 1.1 Replace the mixed dropped-tag and page-chrome policy in `html_elements.py` with an always-remove set that excludes only unsafe, non-textual, media, graphical, metadata, and form-state elements; add page landmark tags to the semantic allowlist.
- [x] 1.2 Update `html_cleaner.py` to destructively remove only that always-remove set, preserve landmark regions, and unwrap text-bearing form containers so their readable descendants survive with no form behavior or attributes.
- [x] 1.3 Retain the existing image-alt substitution, link sanitization, visibility-filtered input boundary, serialization format, and configured byte-limit failure behavior.

## 2. Regression coverage and documentation

- [x] 2.1 Replace article-focused unit expectations with assertions that visible header, navigation, aside, footer, and role-landmark text and structure survive with disallowed attributes removed.
- [x] 2.2 Add cleaner tests proving form labels, legends, button text, output text, and dialog text survive, while input values, textarea content, select/option text, scripts, media, graphics, iframes, and template content do not.
- [x] 2.3 Add a regression test that image alternative text inside a picture wrapper remains as plain text after cleanup.
- [x] 2.4 Update the Compose fixture assertions and expected exact clean HTML to include the newly preserved header and footer content.
- [x] 2.5 Update the public description of cleaned HTML to state that it retains safe visible whole-page text rather than article-only content.

## 3. Verification

- [x] 3.1 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 3.2 Run `uv run pytest` and confirm the configured coverage gate passes.
- [x] 3.3 Run `openspec validate broaden-text-preserving-cleanup --strict`.
