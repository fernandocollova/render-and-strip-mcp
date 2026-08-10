## Context

Both supported strategies currently capture complete visibility-filtered top-level documents. The cleaner returns one cleaned document unchanged for retained collection, but wraps every cleaned page body in a `section` for pagination. This repeats page chrome and creates strategy-dependent output. Collection already ends on a fresh accessibility snapshot, and the pinned `browser_evaluate` tool accepts an element description and snapshot target reference, so the collection completion can hand one current content target directly to orchestration.

## Goals / Non-Goals

**Goals:**

- Select one contiguous task-relevant content region after retained collection completes on every captured page.
- Exclude page-level chrome by capture boundary, without special first-page behavior or tag-name deletion.
- Apply one cleaning and assembly path to retained and paginated captures.
- Produce a fixed document skeleton with exactly one top-level `main` containing normalized semantic content in capture order.
- Keep region capture, cleaning, and assembly concrete and readable, even when that means reparsing intermediate HTML.

**Non-Goals:**

- Preserve source layout, classes, IDs, styles, or exact outer containers.
- Infer metadata, score content density, classify boilerplate heuristically, or recreate Trafilatura.
- Preserve page boundaries in the public output or deduplicate similar records across pages.
- Retain the first page's global header, navigation, sidebar, search controls, or footer.
- Support multiple disjoint selected regions per captured page.

## Decisions

### Collection completion owns semantic region selection

`CollectionReport` will require a non-empty human-readable element description and current Playwright snapshot target. Its model-facing completion arguments remain flat (`selected_region_element` and `selected_region_target`) so the generated OpenAI function schema stays within the same portable subset required of remote tools; a concrete `SelectedRegion` property provides the typed internal handoff. The collection prompt will require one contiguous region containing all content relevant to the caller task while excluding surrounding page chrome. The target is valid only for the final fresh observation of that collection stage and is captured immediately; it is never persisted or reused after pagination.

This uses the model where semantic judgment is already available instead of adding a second model stage or application-owned content-scoring heuristics.

### Orchestration captures the selected visible subtree

The capture callback will accept the validated region selection. A dedicated rendered-content function will invoke `browser_evaluate` with the selected element and target, clone only descendants that satisfy the existing visibility predicates, and return the selected subtree's outer HTML. It will reject missing, stale, non-element, or malformed results with a domain error. URL and original-tab validation remain immediately before capture.

Capturing `outerHTML` retains semantic containers such as lists and tables. The application will not ask the model to transcribe content or generate HTML.

### Every strategy returns the same capture model

Rename the document-oriented request-local value to a content-oriented value containing `html` and `source_url`. Retained collection returns a one-item list and pagination returns a many-item list. Neither strategy performs final serialization, and the normalizer has no one-document compatibility branch.

The small amount of repeated parsing is intentional: each region is cleaned independently against its own source URL, then the cleaned documents are parsed again for assembly. This keeps link resolution and existing cleaner policy obvious.

### Normalize into one application-owned document

Each captured region will pass through the existing removal, semantic allowlist, attribute, image-alt, and source-aware link policies. Assembly will create exactly:

```html
<!doctype html>
<html><head><meta charset="utf-8"></head><body><main>…</main></body></html>
```

Cleaned region content is appended to the final `main` in capture order. An outer cleaned `main` is unwrapped to avoid nested `main` elements; other retained semantic roots, including `article`, `section`, lists, and tables, remain intact. Generic source wrappers are already unwrapped by the cleaner. The aggregate UTF-8 limit is enforced only after complete assembly.

### Page chrome is excluded by boundary, not element deletion

No first-page shell is captured or reintroduced. The model is instructed to exclude surrounding page-level chrome from its selected region. Semantic `header` or `footer` elements naturally inside an article or other selected region remain subject to the normal allowlist; globally deleting those tag names would lose legitimate content and is unnecessary.

## Risks / Trade-offs

- **A model selects an overly broad or narrow region** → Give the completion field a precise task-content contract and require semantic evidence; do not add silent fallback to the full body.
- **A snapshot target becomes stale before capture** → Capture immediately after completion and fail without partial output if Playwright cannot resolve it.
- **A selected root produces awkward but parseable semantics after generic wrappers are removed** → Preserve semantic outer roots, unwrap only an outer `main`, and add representative list, table, article, and generic-container tests.
- **Output no longer contains whole-page context** → This is an intentional breaking policy; callers receive only task-relevant selected content under a uniform wrapper.
- **Independent cleaning and reparsing costs extra CPU and memory** → Prefer the clearer source-aware pipeline; browser and model work dominates expected request cost.

## Migration Plan

Update the model completion schema and prompt, then region capture and strategy handoffs, then replace document assembly with the uniform normalizer. Update contract tests and documentation in the same release. Rollback requires restoring the previous completion schema and whole-document capture together because old model reports do not contain region targets.

## Open Questions

None.
