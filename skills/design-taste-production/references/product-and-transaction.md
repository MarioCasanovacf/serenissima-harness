# Product and Transaction

Use for application UI, dashboards, workspaces, settings, onboarding, checkout, account recovery,
forms, and multi-step flows. Task completion, comprehension, and recovery outrank spectacle.

## Product and dashboard surfaces

- Identify the user's recurring decisions and rank overview, exceptions, detail, and actions around
  them. Do not turn every metric into an equally prominent card.
- Preserve source, units, time range, freshness, comparison basis, confidence, permissions, and
  empty or partial-data meaning. Never fill missing product data with plausible fiction.
- Keep filters, search, sorting, selection, pagination, drill-down, exports, and saved state aligned
  with existing contracts. Make active filters and reset behavior visible.
- Use charts only when they improve comparison or pattern recognition. Provide labels, accessible
  equivalents, and meaningful empty or error states.
- Design for dense real content: long names, localization, zero values, many rows, sparse results,
  latency, permission restrictions, and narrow screens.

## Transactional and multi-step flows

1. Map entry conditions, step sequence, branching, validation, side effects, persistence, exit,
   success, and recovery before styling.
2. Preserve field names, payloads, API sequencing, idempotency, authentication, authorization,
   pricing, totals, consent, legal text, and analytics unless a contract change is approved.
3. Show progress when it helps orientation. Do not imply a linear sequence when the flow branches
   or permits review and correction.
4. Validate near the relevant field, retain valid input after recoverable failure, and distinguish
   user correction from system failure. Never clear a costly form without warning.
5. Summarize consequential changes before commitment. Make price, scope, destination, irreversible
   effects, and recurring terms explicit.
6. For destructive actions, communicate impact and provide cancellation, confirmation, undo, or
   recovery proportionate to risk.
7. Make success specific and durable: confirm what happened, show the resulting state, and provide
   the next useful action without trapping the user.

## State completeness

Cover applicable initial, loading, partial, empty, stale, offline, permission-denied, validation,
system-error, retrying, duplicate-submission, success, and resumed-session states. Preserve focus
and announcements through transitions. Disable duplicate commits without hiding progress.

Visual refinement is successful only when the real task, data, and failure paths remain correct.
