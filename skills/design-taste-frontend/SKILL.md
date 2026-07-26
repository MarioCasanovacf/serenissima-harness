---
name: design-taste-frontend
description: Design and implement distinctive, production-ready marketing frontends, landing pages, portfolios, editorial pages, and careful redesigns without generic AI-looking patterns. Use when creating or polishing a web-facing brand surface, inferring a visual direction from a brief, or auditing an existing marketing interface while preserving its stack, design system, information architecture, analytics, and accessibility.
---

# Design Taste Frontend

Apply taste as a contextual design discipline, not as a replacement stack. Read the brief and the
project before choosing an aesthetic or implementation technique.

## Scope

Use this skill for marketing sites, landing pages, portfolios, editorial pages, campaign surfaces,
and the public-facing portions of a larger product. It is not the primary workflow for
dense dashboards, data tables, admin panels, multi-step product flows, code editors, realtime
collaboration UI, or native mobile. For those, use their domain system and apply this skill only to
the surrounding marketing or brand surface.

## Core workflow

1. **Infer the brief and scope.** Identify the page kind, audience, brand signals, references,
   desired tone, conversion goal, content constraints, and risk constraints. If two materially
   different directions remain plausible, ask one focused question. Otherwise proceed.
2. **Inspect before changing.** Read the repository and preserve its framework, package manager,
   component conventions, design tokens, information architecture, routes, analytics hooks,
   accessibility behavior, content voice, and working dependencies. Do not assume React, Next.js,
   Tailwind, Motion, image generation, or web access.
3. **Declare a design read and dials.** State one concise line: page kind, audience, visual
   language, and chosen design-system or aesthetic family. Set DESIGN_VARIANCE,
   MOTION_INTENSITY, and VISUAL_DENSITY from 1 to 10, with a short rationale.
4. **Choose the foundation honestly.** Prefer the existing design system. If the brief requires an
   official system already suitable for the stack, use it rather than imitating it. Treat
   glassmorphism, bento, editorial, brutalist, dark-tech, and similar terms as aesthetics, not
   official packages.
5. **Load only applicable references.** Always read [taste-rules.md](references/taste-rules.md).
   Read the remaining files only when their condition below is true.
6. **Implement within the existing project.** Reuse installed packages and established
   primitives. Do not change framework or package manager, add dependencies, rewrite content, or
   alter routes merely to follow this skill. Make responsive and accessible behavior part of the
   implementation, not a later patch.
7. **Test and render.** Run the repository's relevant checks. When a local preview or render
   workflow exists, inspect the result at representative mobile and desktop widths and iterate on
   hierarchy, overflow, contrast, focus, motion, and content integrity.
8. **Run preflight.** Read [preflight.md](references/preflight.md), fix every applicable failure,
   and report any check that could not be executed.

## Reference routing

- Read [taste-rules.md](references/taste-rules.md) for the portable visual and content rules on
  every task.
- Read [react-next-tailwind.md](references/react-next-tailwind.md) only when the inspected project
  already uses React, Next.js, or Tailwind, or the user explicitly authorizes that stack for a
  greenfield build.
- Read [motion-patterns.md](references/motion-patterns.md) only when motion is requested, is
  already part of the product language, or materially improves hierarchy, feedback, or
  storytelling.
- Read [redesign.md](references/redesign.md) only when modifying an existing interface.
- Read [preflight.md](references/preflight.md) before delivery.
- Read [upstream-provenance.md](references/upstream-provenance.md) when auditing attribution,
  updating this adaptation, or comparing it with upstream.

All references are one level below this file. Do not recursively load unrelated references.

## Conditional tools and assets

Use image generation or web research only when the capability is available, the user has
authorized it, and it is in scope. Never make either a prerequisite for completing the design.
Treat imagegen and web capabilities as optional tools, never as assumed dependencies.
Never call an external LLM API from project code or shell commands to compensate for a missing
tool.

For visual assets, prefer this order:

1. Existing brand and repository assets.
2. User-provided assets.
3. Authorized, available image-generation or web tooling.
4. Explicitly labeled placeholder slots that preserve layout without pretending to be final art.

Do not fabricate screenshots with decorative divs or claim placeholder imagery is production art.
Do not install a package without checking the manifest, lockfile, package manager, project policy,
and user authorization.

## Delivery contract

Ship complete, coherent changes rather than a disconnected mockup. Preserve user content and
behavior unless the brief authorizes changes. Explain the chosen design read, note which
conditional references were used, list verification performed, and disclose placeholders or
unverified behavior.
