## MODIFIED Requirements

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
