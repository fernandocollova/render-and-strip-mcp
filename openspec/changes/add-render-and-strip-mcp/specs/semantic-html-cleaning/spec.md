## ADDED Requirements

### Requirement: Top-level rendered document scope
The cleaner SHALL process only the final rendered top-level document. It SHALL exclude iframe document content and shadow-root internals from the returned HTML.

#### Scenario: Page contains an iframe
- **WHEN** the final page contains a same-origin or cross-origin iframe with visible content
- **THEN** the returned clean HTML excludes the iframe document's contents

#### Scenario: Page contains an open shadow root
- **WHEN** the final page contains visible content inside an open shadow root
- **THEN** the returned clean HTML excludes the shadow-root internals

### Requirement: Visible semantic content preservation
The cleaner SHALL retain whole-page textual semantic content that is not hidden by a `hidden` attribute, `aria-hidden="true"`, a hidden ancestor, closed `<details>` state outside its `<summary>`, or computed `display:none`, `visibility:hidden|collapse`, `content-visibility:hidden`, or `opacity:0`. It SHALL remove template and inert content. It SHALL retain offscreen content and SHALL NOT attempt visual occlusion or clipping analysis.

#### Scenario: Visible article content is retained
- **WHEN** the final top-level document contains visible headings, paragraphs, a list, a table, and a link
- **THEN** the clean HTML retains their readable text and semantic structure

#### Scenario: Hidden content is excluded
- **WHEN** the final rendered document contains content hidden by an attribute or computed layout style
- **THEN** the clean HTML excludes that content

#### Scenario: Offscreen content remains
- **WHEN** textual semantic content is rendered outside the current viewport without matching a defined hidden condition
- **THEN** the clean HTML retains that content as part of the whole page

### Requirement: Non-textual and presentation cleanup
The cleaner SHALL remove scripts, stylesheet and style elements, inline event handlers, animation-related presentation data, media and graphical elements, forms and controls, comments, generic presentation attributes, `<base>`, refresh metadata, and other executable or non-text content. It SHALL remove navigation and aside elements, elements with navigation/banner/contentinfo/complementary roles, and page-level headers/footers outside `main` or `article`. It SHALL unwrap generic layout elements and headers/footers inside `main` or `article` while retaining their textual descendants. Before removing an image with non-empty alternative text, it SHALL replace it with plain text in the form `[Image: <alt text>]`.

#### Scenario: Styled media-rich page is cleaned
- **WHEN** the final document contains CSS, JavaScript, video, images, canvases, SVG, forms, controls, navigation, and visible article text
- **THEN** the returned HTML excludes the presentation, media, executable, and page-chrome elements while retaining the article text structure

### Requirement: Deterministic semantic document serialization
The cleaner SHALL parse with Beautiful Soup's Python built-in `html.parser` and return `<!doctype html>` followed by an `html/head/body` document with UTF-8 metadata and a textual title when present. Outside the required document skeleton it SHALL allow only `main`, `article`, `section`, `h1` through `h6`, `p`, `br`, `hr`, `blockquote`, `pre`, `code`, `ul`, `ol`, `li`, `dl`, `dt`, `dd`, `details`, `summary`, `table`, `caption`, `thead`, `tbody`, `tfoot`, `tr`, `th`, `td`, `a`, `strong`, `em`, `b`, `i`, `u`, `s`, `small`, `sub`, `sup`, `abbr`, `time`, `address`, `kbd`, `samp`, `var`, `mark`, `q`, and `cite`. Disallowed generic layout tags SHALL be unwrapped when their textual descendants are retained. The cleaner SHALL remove all attributes except sanitized link `href` and `title`, table-cell `colspan`, `rowspan`, and `scope`, `datetime` on time elements, and semantic `title` on abbreviation elements.

#### Scenario: Complete document is serialized
- **WHEN** visible semantic content is cleaned from a rendered page with a title
- **THEN** the result contains a doctype, UTF-8 `html/head/body` skeleton, title, and only allowed semantic elements and attributes

### Requirement: Link destination sanitization
The cleaner SHALL resolve relative link destinations against the final page URL. It SHALL retain fragment, HTTPS, `mailto:`, and `tel:` destinations, and SHALL retain HTTP destinations only when plain HTTP is enabled. It SHALL remove destinations using other schemes, embedded credentials, malformed URLs, `<base>` behavior, or executable values while preserving readable link text. If a link has no readable text and has an `aria-label`, the cleaner SHALL use that label as link text and remove the attribute.

#### Scenario: Relative HTTPS link is preserved
- **WHEN** a visible link has a relative destination on an HTTPS final page
- **THEN** the result contains the equivalent absolute HTTPS destination

#### Scenario: Executable destination is removed
- **WHEN** a visible link uses a `javascript:`, `data:`, `file:`, or `blob:` destination
- **THEN** the result preserves its readable text without an `href` attribute

#### Scenario: Plain HTTP link follows configuration
- **WHEN** a visible link resolves to plain HTTP
- **THEN** its destination is retained only when plain HTTP is enabled

### Requirement: Clean HTML size behavior
The cleaner SHALL enforce an optional UTF-8 byte limit on the serialized clean HTML. A configured limit of `0` SHALL mean unlimited. If a nonzero limit is exceeded, the tool SHALL fail with an MCP tool error and SHALL NOT return truncated HTML.

#### Scenario: Unlimited clean HTML default
- **WHEN** the clean HTML byte limit is configured as `0`
- **THEN** the cleaner does not impose an application-level output-size cap

#### Scenario: Clean HTML exceeds configured limit
- **WHEN** serialized clean HTML exceeds a nonzero configured byte limit
- **THEN** the tool returns an MCP tool error instead of a truncated document
