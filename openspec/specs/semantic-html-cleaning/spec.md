## Purpose

Produce a deterministic semantic HTML representation of the final rendered page.

## Requirements

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
The cleaner SHALL remove scripts, stylesheet and style elements, inline event handlers, animation-related presentation data, media and graphical elements, comments, `<base>`, refresh metadata, and other executable or non-text content. It SHALL remove form-control values and selectable-option text, including input, textarea, select, option, datalist, and progress elements. It SHALL retain visible textual descendants of form, fieldset, label, legend, button, output, and dialog elements by unwrapping those elements rather than deleting their descendants. It SHALL retain visible text in navigation, aside, header, footer, and elements with navigation/banner/contentinfo/complementary roles; page structure alone SHALL NOT cause their text to be removed. Before removing an image with non-empty alternative text, it SHALL replace it with plain text in the form `[Image: <alt text>]`.

#### Scenario: Visible whole-page text is retained
- **WHEN** the final document contains visible page header, navigation, aside, main content, footer, a role-based landmark, and text-bearing form descendants
- **THEN** the returned HTML retains their readable text while excluding form-control values and selectable-option text

#### Scenario: Styled media-rich page is cleaned
- **WHEN** the final document contains CSS, JavaScript, video, images, canvases, SVG, forms, controls, navigation, and visible page text
- **THEN** the returned HTML excludes executable, presentation, media, graphical, and form-value content while retaining visible textual page content, including navigation and form labels

### Requirement: Deterministic semantic document serialization
The cleaner SHALL parse with Beautiful Soup's Python built-in `html.parser` and return `<!doctype html>` followed by an `html/head/body` document with UTF-8 metadata and a textual title when present. Outside the required document skeleton it SHALL allow only `main`, `article`, `section`, `header`, `footer`, `nav`, `aside`, `h1` through `h6`, `p`, `br`, `hr`, `blockquote`, `pre`, `code`, `ul`, `ol`, `li`, `dl`, `dt`, `dd`, `details`, `summary`, `table`, `caption`, `thead`, `tbody`, `tfoot`, `tr`, `th`, `td`, `a`, `strong`, `em`, `b`, `i`, `u`, `s`, `small`, `sub`, `sup`, `abbr`, `time`, `address`, `kbd`, `samp`, `var`, `mark`, `q`, and `cite`. Disallowed generic layout tags and text-bearing form containers SHALL be unwrapped when their readable descendants are retained. The cleaner SHALL remove all attributes except sanitized link `href` and `title`, table-cell `colspan`, `rowspan`, and `scope`, `datetime` on time elements, and semantic `title` on abbreviation elements.

#### Scenario: Complete whole-page document is serialized
- **WHEN** a rendered page contains a title and visible textual landmark elements
- **THEN** the result contains a doctype, UTF-8 `html/head/body` skeleton, title, the allowed semantic landmark elements, and only allowed attributes

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
