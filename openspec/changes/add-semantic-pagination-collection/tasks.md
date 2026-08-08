## 1. Stage Contracts and Configuration

- [x] 1.1 Extend discovery, stage names, validated reports, and model prompts for paginated documents and compact semantic page-advance progress.
- [x] 1.2 Add the positive `max_paginated_documents` agent setting with its documented default and configuration tests.

## 2. Paginated Collection

- [x] 2.1 Implement same-page retained collection composition, pre-replacement document capture, semantic advancement, loop detection, and hard-limit failure.
- [x] 2.2 Update browser-agent strategy dispatch and extraction orchestration to return captured documents for both supported strategies.

## 3. Final Document Assembly

- [x] 3.1 Add typed rendered-document capture and multi-document cleaning/assembly with per-source link resolution, stable order, single-page compatibility, and aggregate byte-limit enforcement.

## 4. Verification and Documentation

- [x] 4.1 Add focused tests for strategy discovery contracts, pagination continuation/completion/progress, unchanged and repeated pages, and hard-limit behavior.
- [x] 4.2 Add focused tests for multi-document assembly, relative links, output order, single-document compatibility, and aggregate output limits.
- [x] 4.3 Update user-facing retrieval and configuration documentation, then run OpenSpec validation and the project formatting, linting, typing, and test commands.
- [x] 4.4 Define relevance-scoped safe discovery probes in the specification and model prompt, including regression coverage for eligible, prohibited, irrelevant, and completeness-blocking controls.
- [x] 4.5 Remove redundant orchestration preconditions from the pagination-advance prompt and verify that it opens with the stage's decision responsibility.
