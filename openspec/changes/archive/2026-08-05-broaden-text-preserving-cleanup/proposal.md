## Why

The cleaner currently treats structural page regions and all form-related elements as disposable chrome. That loses visible text that a browser task deliberately made ready for downstream extraction, including contact-page labels, footer contact details, navigation labels, and sidebars.

## What Changes

- Preserve visible text from page-level header, footer, navigation, aside, and ARIA landmark regions instead of deleting those regions solely by structural role.
- Preserve readable descendants of text-bearing form containers and controls by unwrapping them, while continuing to omit control values, selectable options, executable content, media, and graphical payloads.
- **BREAKING**: Returned clean HTML can contain additional visible page text and semantic landmark elements compared with prior cleaner output.
- Keep final-DOM capture, the public MCP signature, link sanitization, visibility filtering, and byte-limit behavior unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `semantic-html-cleaning`: Broaden the cleaned document from article-focused content to safe visible textual whole-page content.

## Impact

- Updates `src/render_and_strip_mcp/html_elements.py` and `src/render_and_strip_mcp/html_cleaner.py`.
- Replaces cleaner assertions that expect page chrome and all form text to be removed, and updates Compose fixture output expectations.
- Does not add dependencies, alter the public tool parameters, or add task parsing or incremental scroll capture.
