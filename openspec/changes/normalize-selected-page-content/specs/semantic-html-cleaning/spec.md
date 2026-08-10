## MODIFIED Requirements

### Requirement: Top-level rendered document scope
The cleaner SHALL process only captured visibility-filtered subtrees selected from final rendered top-level documents. It SHALL exclude content outside each selected region, including surrounding page-level chrome, and SHALL exclude iframe document content and shadow-root internals from selected regions.

#### Scenario: Page contains surrounding chrome
- **WHEN** a final page contains global header, navigation, sidebar, search, or footer content outside its selected task-content region
- **THEN** the returned normalized HTML excludes that surrounding content

#### Scenario: Selected region contains an iframe
- **WHEN** a selected region contains a same-origin or cross-origin iframe with visible content
- **THEN** the returned normalized HTML excludes the iframe document's contents

#### Scenario: Selected region contains an open shadow root
- **WHEN** a selected region contains visible content inside an open shadow root
- **THEN** the returned normalized HTML excludes the shadow-root internals

### Requirement: Deterministic semantic document serialization
The cleaner SHALL parse captured selected-region HTML with Beautiful Soup's Python built-in `html.parser` and return `<!doctype html>` followed by an `html/head/body` document with UTF-8 metadata and exactly one top-level `main`. It SHALL use this same document shape for one or multiple captured regions, append normalized region content in capture order without page-boundary wrappers, and unwrap a captured outer `main` rather than nest it. Outside the required document skeleton it SHALL allow only `article`, `section`, `header`, `footer`, `nav`, `aside`, `h1` through `h6`, `p`, `br`, `hr`, `blockquote`, `pre`, `code`, `ul`, `ol`, `li`, `dl`, `dt`, `dd`, `details`, `summary`, `table`, `caption`, `thead`, `tbody`, `tfoot`, `tr`, `th`, `td`, `a`, `strong`, `em`, `b`, `i`, `u`, `s`, `small`, `sub`, `sup`, `abbr`, `time`, `address`, `kbd`, `samp`, `var`, `mark`, `q`, and `cite`. Disallowed generic layout tags and text-bearing form containers SHALL be unwrapped when their readable descendants are retained. The cleaner SHALL remove all attributes except sanitized link `href` and `title`, table-cell `colspan`, `rowspan`, and `scope`, `datetime` on time elements, and semantic `title` on abbreviation elements.

#### Scenario: One selected region is serialized
- **WHEN** retained-document collection captures one task-content region
- **THEN** the result contains the fixed skeleton, one top-level `main`, and the region's normalized semantic content inside that `main`

#### Scenario: Multiple selected regions are serialized
- **WHEN** paginated-document collection captures multiple task-content regions
- **THEN** the result uses the same fixed skeleton and one top-level `main` containing all normalized region content in capture order without per-page wrappers

#### Scenario: Selected region is a main element
- **WHEN** a captured selected region has an outer `main`
- **THEN** its normalized children are placed in the result's one top-level `main` without creating a nested or second `main`
