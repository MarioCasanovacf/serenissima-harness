# Delivery Preflight

Run every applicable check. Fix failures before delivery and disclose checks that the environment
could not execute.

## Brief and foundation

- [ ] Design read states page kind, audience, visual language, and foundation.
- [ ] DESIGN_VARIANCE, MOTION_INTENSITY, and VISUAL_DENSITY are explicit and brief-driven.
- [ ] Existing stack, package manager, design system, tokens, and conventions are preserved.
- [ ] No unapproved dependency, framework migration, image generation, or web access was assumed.
- [ ] Redesign mode and preservation contract were audited when applicable.

## Visual coherence

- [ ] One coherent palette, accent strategy, type system, icon family, and radius rule is used.
- [ ] The hero communicates proposition and action at common laptop and mobile heights.
- [ ] Section layouts vary without breaking reading order or repeating a template mechanically.
- [ ] Cards communicate containment; spacing is used when containment is unnecessary.
- [ ] No generic AI-purple, three-card, dark-mesh, glass-everywhere, fake-dashboard, or decorative
      metadata pattern slipped in without brief support.
- [ ] Visible copy contains no em dash or en dash used as prose punctuation.
- [ ] No fabricated people, logos, testimonials, metrics, awards, inventory, locations, or status.
- [ ] Final assets are real, or placeholders are explicit and disclosed.

## Interaction and accessibility

- [ ] Semantic structure, heading order, keyboard flow, visible focus, labels, and alt text work.
- [ ] Text, controls, placeholders, and focus indicators meet WCAG AA contrast.
- [ ] Controls have applicable hover, active, focus, disabled, loading, empty, error, and success
      states.
- [ ] CTA labels do not wrap unexpectedly and duplicate intents were removed.
- [ ] Motion is justified, interruptible, cleaned up, and reduced-motion safe.
- [ ] Content remains reachable without animation and on touch or coarse-pointer devices.

## Responsive and performance

- [ ] Inspect representative narrow mobile, wide mobile, tablet, laptop, and large desktop widths.
- [ ] No horizontal overflow, clipped display type, broken grid, hidden CTA, or unstable viewport.
- [ ] Images reserve space, responsive sources are sensible, and critical assets are not oversized.
- [ ] Core Web Vitals risks were checked: loading, interaction latency, layout shift, and excess
      client-side work.
- [ ] Theme variants supported by the project were tested.

## Product integrity

- [ ] Routes, nav labels, anchors, forms, analytics, consent, legal copy, SEO, and structured data
      remain intact unless explicitly changed.
- [ ] Existing tests plus relevant lint, type, build, and browser or render checks pass.
- [ ] The final report lists tests, visual inspection, placeholders, and any unverified behavior.
