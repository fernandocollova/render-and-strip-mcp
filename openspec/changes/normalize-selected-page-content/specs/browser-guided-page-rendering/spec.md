## MODIFIED Requirements

### Requirement: Render-and-strip MCP tool input and result
The MCP server SHALL expose a Streamable HTTP tool named `render_and_strip_page` that accepts a non-empty HTTP(S) initial URL and non-empty natural-language browser task. It SHALL reject a plain-HTTP URL by default and accept it only when `allow_plain_http` is enabled. It SHALL always reject URL schemes other than HTTP(S). On success, the tool SHALL return only one normalized semantic HTML string produced after successful collection through a supported strategy. For both retained-document and paginated-document collection, that string SHALL use the same fixed document shape and SHALL contain only cleaned task-relevant selected-region content under one top-level `main`, in capture order. On failure, the tool SHALL return an MCP tool error and SHALL NOT return partial HTML.

#### Scenario: Successful retained-document rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose retained-document pipeline completes within its limits
- **THEN** the tool returns one normalized semantic document containing the selected content from the greedily expanded final page state under one `main`

#### Scenario: Successful browser-guided rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose selected supported collection pipeline completes within its limits
- **THEN** the tool returns only the normalized semantic HTML produced by the common selected-content normalization path

#### Scenario: Successful paginated rendering
- **WHEN** a caller invokes `render_and_strip_page` with a valid URL and task whose paginated-document pipeline reaches semantic or natural completion within its limits
- **THEN** the tool returns one normalized semantic document containing every captured selected region in source order under one `main`

#### Scenario: Invalid tool input
- **WHEN** a caller supplies an empty URL or task, a non-HTTP(S) URL, or a plain-HTTP URL while `allow_plain_http` is disabled
- **THEN** the tool returns a validation error before opening a Playwright MCP session

#### Scenario: Plain HTTP is explicitly enabled
- **WHEN** a caller supplies a plain-HTTP initial URL and `allow_plain_http` is enabled
- **THEN** the tool permits initial navigation
