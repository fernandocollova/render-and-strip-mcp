## Context

The current renderer already captures the visibility-filtered final top-level document after the browser agent completes its caller task. The cleaner then removes all elements in one dropped-tag set, removes page-chrome landmarks, and unpacks remaining markup to a fixed semantic allowlist. See proposal.md for the resulting loss of useful visible text.

## Goals / Non-Goals

**Goals:**
- Return an inclusive, deterministic, text-only representation of the final rendered page.
- Retain meaningful visible text without retaining active form behavior, media, arbitrary attributes, or unsafe link destinations.
- Preserve enough semantic landmark structure for a downstream model to distinguish page regions.

**Non-Goals:**
- Interpret the caller task to select a subset of the final page.
- Return input values, selected options, textarea content, or other control state.
- Preserve images, media, graphics, scripts, styles, iframe content, shadow-root content, or form interactivity.
- Accumulate virtualized or discarded content while the agent scrolls; the existing final-DOM capture remains the boundary.

## Decisions

### Split destructive removal from text-preserving normalization

Replace the mixed dropped-tag policy with a set for content that must be destructively removed: executable, embedded, media, graphical, metadata, and stateful value/control elements. Do not include text-bearing containers such as `form`, `fieldset`, `label`, `legend`, `button`, `output`, or `dialog` in that set. The normal semantic-cleaning pass will unwrap those disallowed containers, retaining only their text descendants.

This preserves textual form labels and actions without introducing form behavior or copied values. Adding form controls to the semantic allowlist was rejected because the result is a text document, not an interactive reproduction. Retaining control values or all option text was rejected because it exposes incidental state and can substantially inflate output with non-rendered choice lists.

### Preserve structural page regions but continue stripping their attributes

Add `header`, `footer`, `nav`, and `aside` to the semantic allowlist. Stop deleting those elements or containers solely because they carry a navigation/banner/contentinfo/complementary role. Their attributes, including `role`, are still removed by the existing attribute policy.

Keeping these landmark tags is preferred to unwrapping every region because it helps downstream extraction distinguish contact details, navigation labels, and supplementary content. Retaining arbitrary attributes or ARIA values is unnecessary for the text-only contract and would expand the sanitizer surface.

### Keep the capture pipeline and safety policies unchanged

Do not change the browser task loop, its newly internalized current-page guidance, visibility-cloning expression, final-origin checks, image-alt conversion, link sanitization, document serialization shape, or output byte-limit behavior. The change solely broadens what textual content survives cleaning after the agent has produced its final page state.

Task-aware region selection and content accumulation during scrolling are separate features. They require a defined capture contract and cannot be implemented correctly by altering cleaner tag policy alone.

## Risks / Trade-offs

- [Extra navigation and footer text increases output size and downstream context use] → Preserve the existing configurable byte cap and document the output expansion as a breaking result change.
- [Cookie dialogs or other visible overlays can remain in the result] → The browser task can dismiss them when needed; visibility filtering and the final-DOM boundary remain unchanged.
- [Unwrapping a text-bearing form container can flatten its structure] → Retain the readable descendants while deliberately excluding interactive tags and their state.
- [A virtualized page removes earlier rows after scrolling] → Explicitly leave incremental capture out of scope; do not claim a complete historical scroll transcript.

## Migration Plan

1. Ship the policy, cleaner, specification, and test updates together.
2. Downstream consumers that require article-only input can filter the added semantic landmarks or use their existing extraction instructions.
3. Roll back by restoring the former page-chrome removal policy if the increased output is unacceptable; no stored data or API migration is required.
