---
name: design-taste-production
description: Design, redesign, implement, or visually review distinctive production-ready web interfaces, executive decision memos, and mobile image concepts while preserving product constraints and the existing stack. Use for marketing and conversion pages, product and dashboard UI, transactional or multi-step flows, preserve-mode or overhaul-mode redesigns, reference-to-code work, visual quality audits, and web or mobile image concept direction. Apply Mario Casanova's personal system only when the exact personal:mario flag is explicit; without it, remain brand-neutral.
---

# Design Taste Production

Turn a brief, repository, or visual reference into coherent production UI. Treat taste as contextual
judgment under constraints, not as a preferred framework, aesthetic, or component recipe.

This is a declarative, reference-only capability. Its design reasoning, rules, and acceptance
criteria must remain independent of the model, agent runtime, command-line tool, vendor, and
hosting environment that execute it. Runtime-specific discovery may expose this directory, but it
must not change the skill's semantics or be required by its workflow.

## Lock the operating mode

Choose one primary mode before making design decisions. State it in the design read and do not
silently switch modes. If two modes imply materially different deliverables and the request does
not resolve them, ask one focused question. A task may name a secondary mode, but the primary mode
controls the workflow and acceptance bar.

| Mode | Primary outcome | Required reference |
| --- | --- | --- |
| Marketing / conversion | Communicate value and move an audience toward one measurable action | [marketing-surfaces.md](references/marketing-surfaces.md) |
| Product / task | Help a user understand state and complete recurring work, including dashboards | [product-and-transaction.md](references/product-and-transaction.md) |
| Transactional flow | Complete a consequential or multi-step action safely and recoverably | [product-and-transaction.md](references/product-and-transaction.md) |
| Redesign: preserve | Improve quality while keeping recognizable brand and product contracts | [redesign-preservation.md](references/redesign-preservation.md) |
| Redesign: overhaul | Establish a new visual language while retaining unapproved-to-change contracts | [redesign-preservation.md](references/redesign-preservation.md) |
| Reference to code | Translate supplied visual evidence into the target project's native implementation | [reference-to-code.md](references/reference-to-code.md) |
| Visual review | Diagnose hierarchy, coherence, usability, responsiveness, and production risk | [interface-quality.md](references/interface-quality.md) |
| Image concept | Define or produce art direction that serves the interface | [image-concepts.md](references/image-concepts.md) |
| Data visualization | Turn measures, comparisons, distributions, relationships, and uncertainty into inspectable evidence | [data-visualization.md](references/data-visualization.md) |
| Executive decision memo | Turn bounded evidence into a conclusion-led presentation for a decision-maker | [mario-executive-memo.md](references/mario-executive-memo.md) only with `personal:mario`; otherwise use the brief and quality references |

After selecting the primary mode, set the profile separately. Activate `personal:mario` only when
that exact flag is explicit in the request or project instructions. Never infer it from a person's
name, an artifact type, or this skill's availability. Without the flag, keep the visual language,
voice, palette, materiality, and surface color brand-neutral; a light paper canvas is not a default.

## Core workflow

1. **Inspect before proposing.** Read the relevant project files, representative screens and
   components, package and build configuration, design tokens, data shapes, routes, tests, and
   supplied references. Identify what is real, what is inferred, and what remains unknown.
2. **Frame the brief.** Read [brief-and-direction.md](references/brief-and-direction.md). Record the
   audience, user job, business goal, content and brand evidence, constraints, primary mode, and
   success signal. Enumerate every requested deliverable before implementation. Prefer one
   defensible interpretation over a collage of trends.
3. **Declare the design read.** In one compact statement, name the mode, audience, product job,
   visual direction, density, and motion posture. Distinguish decisions from assumptions.
4. **Preserve the product contract.** Keep the existing framework, package manager, component
   conventions, design system, data and API contracts, state semantics, routes, forms, analytics,
   consent and legal behavior, accessibility, SEO, content meaning, tests, and performance budgets
   unless the user explicitly authorizes a change. Overhaul mode is not permission to break them.
5. **Implement natively.** Reuse installed dependencies and established primitives. Express the
   direction in the project's own framework and styling model. Do not introduce React, Tailwind,
   GSAP, another design system, dark mode, a font, or any dependency merely because this skill
   mentions a visual possibility.
6. **Resolve the whole state space.** Design responsive layout plus applicable loading, empty,
   partial, error, success, disabled, permission, offline, validation, and destructive-action
   states. For dashboards and flows, protect data legibility, task continuity, and recovery.
7. **Render and iterate.** Inspect representative narrow and wide viewports and real content
   extremes when preview tooling exists. Compare hierarchy, reading order, overflow, contrast,
   focus, interaction feedback, and contract preservation. Do not call a mockup production-ready
   without proportionate build, test, and visual evidence.
8. **Preflight delivery.** Read [production-preflight.md](references/production-preflight.md), fix
   applicable failures, cross-check every requested deliverable, and report checks that could not
   run.

## Reference routing

Load only what the active mode needs; every reference is directly linked here.

- Always read [brief-and-direction.md](references/brief-and-direction.md),
  [interface-quality.md](references/interface-quality.md), and
  [production-preflight.md](references/production-preflight.md).
- Read [marketing-surfaces.md](references/marketing-surfaces.md) for marketing, campaign,
  editorial-conversion, pricing, launch, or other acquisition surfaces.
- Read [product-and-transaction.md](references/product-and-transaction.md) for application UI,
  dashboards, data-dense workspaces, forms, checkout, onboarding, settings, and multi-step flows.
- Read [data-visualization.md](references/data-visualization.md) whenever a surface contains a KPI,
  chart, analytical figure, metric comparison, table of numbers, or date/period display.
- Read [redesign-preservation.md](references/redesign-preservation.md) whenever an existing surface
  changes, in either preserve or overhaul mode.
- Read [reference-to-code.md](references/reference-to-code.md) when screenshots, mockups, websites,
  or other visual examples are implementation inputs.
- Read [image-concepts.md](references/image-concepts.md) only when imagery is part of the brief or
  image concept is the selected mode.
- Read [style-lenses.md](references/style-lenses.md) when the brief lacks a visual vocabulary or
  competing directions need to be separated.
- With the exact `personal:mario` flag, read [mario-activation.md](references/mario-activation.md),
  [mario-structure-and-voice.md](references/mario-structure-and-voice.md), and
  [mario-data-semantics.md](references/mario-data-semantics.md). Do not load or apply them otherwise.
- With `personal:mario`, read [mario-surface-translation.md](references/mario-surface-translation.md)
  for dashboards, personal landing pages, case studies, reports, or presentations; also read
  [mario-executive-memo.md](references/mario-executive-memo.md) for a decision memo or executive deck.
- Read [mario-calibration.md](references/mario-calibration.md) only when running a controlled Mario
  profile comparison, negative control, blind review, or promotion decision.
- Read [upstream-provenance.md](references/upstream-provenance.md) only for attribution, auditing,
  redistribution, or upstream comparison.

Do not recursively load unrelated files from references.

## Conditional capabilities

Use image generation, image search, or browsing only when available, authorized, and necessary.
For image work, prefer existing repository assets, then user-provided assets, then an authorized
tool. Otherwise deliver a specific concept brief or clearly labeled placeholder without claiming
it is final art. Use placeholders only for truly missing external assets or dependencies; specify
each placeholder's dimensions, role, and replacement next step. Do not fabricate product
screenshots, customers, metrics, logos, or endorsements.

Use motion only when it clarifies hierarchy, feedback, continuity, or narrative. Prefer the
project's existing mechanism and the lightest adequate technique. Preserve content without motion,
honor reduced-motion preferences, avoid scroll capture, and clean up observers, listeners, and
timelines. Motion libraries are conditional implementation choices, never a requirement.

## Delivery contract

Deliver the implemented or reviewed surface together with the mode and design read, preserved and
intentionally changed contracts, verification evidence, and any placeholders or unresolved risks.
For a review-only request, prioritize findings by user impact and cite the affected screen or
component; do not mutate the project unless asked.
