## Context

See `proposal.md` for motivation. The current discovery contract recognizes only content that can coexist in one final DOM, collection mutates one tracked tab, and browser orchestration extracts and cleans that tab exactly once. Replacing pagination therefore loses prior pages and is deliberately classified as unsupported. The implementation must retain the same-origin policy, isolated tracked tab, model-guided semantic interaction, compact stage context, and all-or-nothing result behavior.

## Goals / Non-Goals

**Goals:**

- Compose existing retained-document collection with immediate next-page traversal.
- Support caller-defined semantic cutoffs without introducing site-specific parsers.
- Preserve compact cross-page reasoning needed for semantic completion.
- Produce one valid cleaned result whose links are resolved against their source pages.
- Bound traversal independently of model-stage action limits.

**Non-Goals:**

- Following record-detail, `Read more`, or equivalent links.
- Filtering individual records from a boundary page.
- Adding a deterministic date, version, or site-specific cutoff parser.
- Returning partial pages after any limit or integration failure.

## Decisions

### Add a distinct paginated discovery strategy

`DiscoveryStrategy` will gain `paginated-documents`. Discovery will select it only for a proven immediate next-page transition that replaces the current same-origin result document. This keeps replacing navigation out of `retained-final-document` while avoiding a generic fallback that might traverse unrelated links.

Alternative: treat pagination as another retained reveal and inject earlier HTML into the browser DOM. Rejected because injected content is not page-owned rendered state, complicates visibility behavior, and couples collection to unsafe DOM mutation.

### Define probe safety by relevance, visible semantics, and completeness

Discovery will ignore controls unrelated to revealing or advancing the caller's target result set. It may probe one transition only when a plausibly relevant control visibly represents a non-mutating reveal or immediate page advance. Forms, target-state changes, authentication, durable mutations, deletion, downloads, record-detail navigation, and controls with uncertain effects remain ineligible. An unresolved control causes `unknown` only when it is plausibly relevant and leaving it unused prevents discovery from establishing complete supported collection; unrelated or redundant ambiguity does not reject an otherwise supported page.

Alternative: instruct the model only to probe "safely." Rejected because it does not define eligible effects or distinguish an irrelevant unfamiliar control from an unresolved reveal mechanism that threatens completeness.

### Compose retained collection per page

The paginated handler will call the existing retained-document collector on every current page. It will then invoke an orchestration-owned capture callback before running page advancement. This callback seam keeps browser/session I/O in `BrowserAgent` while allowing strategy code to own the traversal loop and directly reuse the existing collector.

Alternative: rerun access, discovery, reset, and reconstruction for every page. Rejected because pagination pages share one established target-result view and repeating the full pipeline adds cost without a new semantic access problem.

### Use a dedicated page-advance stage with compact cumulative progress

Each page-advance iteration receives the original task, captured-document count, current page observation, and the preceding compact progress summary returned by the prior iteration. Its validated report states either `advanced` or `complete`, replaces the compact progress summary, and provides evidence. The model is instructed to continue under uncertainty, to use the natural terminal page when no explicit cutoff exists, and never to treat record-detail links as Next controls.

The orchestration will reject `advanced` when the page state did not change and reject repeated collected page identities. This adds deterministic evidence around the model-guided transition without pretending to parse arbitrary semantic cutoffs.

Alternative: infer cutoffs in Python from dates or page numbers. Rejected because the caller explicitly controls semantics through the natural-language task and future target sites may expose different fields and ordering.

### Capture raw visible documents and clean after successful collection

Each page capture stores its visibility-filtered HTML and observed top-level URL before replacement. No HTML is returned until traversal succeeds. Final processing cleans each raw document against its own URL, preserving correct relative-link resolution, then wraps multiple cleaned bodies in ordered semantic sections under one document skeleton. One captured page follows the existing cleaner path unchanged.

Alternative: clean and concatenate serialized documents during traversal. Rejected because it blurs collection and final-cleaning milestones and makes aggregate byte-limit handling less clear.

### Keep semantic completion and hard safety separate

The task's explicit semantic cutoff, or the site's natural terminal page by default, determines successful completion. A new positive `max_paginated_documents` setting defaults to 25 and remains invocation-wide. After capturing the maximum page, the advance stage still assesses completion; `complete` succeeds, while `advanced` causes an execution-limit failure with no output.

Alternative: return pages captured before the hard limit. Rejected because it violates the existing no-partial-result contract and could silently omit requested records.

## Risks / Trade-offs

- [Model incorrectly interprets an ambiguous cutoff] → Preserve the task verbatim, require evidence and cumulative progress, continue under uncertainty, and leave semantic precision under caller control.
- [Repeated whole-page bodies duplicate site chrome] → Preserve whole-page behavior intentionally; semantic record extraction and filtering remain out of scope.
- [Large page sets consume memory] → Enforce the document limit, total timeout, and final UTF-8 output cap; capture only visibility-filtered HTML.
- [Dynamic snapshots evade exact loop detection] → Check both unchanged immediate transitions and repeated collected page identities, with the hard document limit as a final guard.
- [Page layouts change later in traversal] → Run retained collection independently on every page and fail if a stage cannot prove completion.

## Migration Plan

Add the strategy and setting with backward-compatible defaults. Existing retained-document behavior and the public MCP tool signature remain unchanged. Rollback consists of removing the paginated strategy from discovery and dispatch; no persisted data migration is required.
