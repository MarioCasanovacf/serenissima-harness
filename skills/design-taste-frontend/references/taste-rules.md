# Portable Taste Rules

## Contents

- Brief signals and dials
- Foundation selection
- Visual hierarchy
- Layout and material
- Content and states
- Assets and accessibility
- Anti-patterns

## Brief signals and dials

Read page kind, audience, vibe words, references, existing brand assets, conversion goal, and
quiet constraints such as regulated, public-sector, accessibility-first, or child-facing use.
Audience and constraints outrank personal taste.

Set three explicit dials:

| Dial | 1 | 10 |
| --- | --- | --- |
| DESIGN_VARIANCE | symmetric and conservative | asymmetric and experimental |
| MOTION_INTENSITY | static except feedback | cinematic and scroll-led |
| VISUAL_DENSITY | gallery-like and airy | compact and information-rich |

Typical starting points are 7/6/4 for a mainstream landing page, 8/7/3 for a creative portfolio,
5/3/3 for a calm editorial surface, and 3/2/5 for a trust-first public service. Treat these as
starting points, never hidden defaults. Existing redesigns start from the current interface.

Avoid automatic AI-purple gradients, a centered hero over a dark mesh, three equal feature cards,
glass on every surface, looping motion, generic copy, and an unexamined default font stack.

## Foundation selection

Preserve the project's existing design system when it is coherent. Use one system per surface.
When the brief genuinely maps to an official system and the project can support it, prefer the
official implementation:

| Context | Likely system |
| --- | --- |
| Microsoft enterprise | Fluent UI |
| Material product | Material 3 |
| IBM enterprise analytics | Carbon |
| Shopify admin | Polaris |
| Atlassian product | Atlaskit |
| GitHub-like developer surface | Primer |
| UK public service | GOV.UK Frontend |
| US public service | USWDS |

Do not add any of these merely because they appear in this table. Verify compatibility and obtain
authorization before installing. Aesthetic names such as bento, editorial, brutalist,
glassmorphism, kinetic type, and liquid glass do not imply an official web package. Label
approximations honestly.

## Visual hierarchy

- Make the primary action and page proposition obvious without relying on decoration.
- Keep display type intentional. Use a serif only when brand or editorial context justifies it.
- Emphasize words with weight or italic within the same family instead of injecting a random font.
- Give italic descenders enough line-height and padding so glyphs are not clipped.
- Lock one neutral family, one accent, and a consistent corner-radius rule unless the design system
  defines a documented hierarchy.
- Treat color as semantic and brand-bearing. Do not use purple, beige-and-brass, or any other
  fashionable palette as an automatic category shortcut.
- Test text and controls to WCAG AA contrast. Check buttons, placeholders, focus rings, disabled
  states, text over images, and both light and dark modes when both are supported.

## Layout and material

- Prefer a clear grid, content rhythm, and deliberate whitespace over card containers everywhere.
- Use cards only when containment or elevation communicates real hierarchy.
- Avoid complex percentage math when the existing CSS system offers grid or a reliable layout
  primitive.
- Keep full-height sections stable on mobile by using dynamic viewport units when supported by the
  project's browser policy.
- Vary section composition with purpose. Do not repeat the same split image-and-text pattern three
  times or create asymmetry that breaks reading order.
- Keep navigation on one line at desktop when content permits. Make mobile collapse explicit.
- Keep hero copy concise enough that the primary action is visible at common laptop heights.
- Use tinted, restrained shadows. Avoid pure-black default shadows and arbitrary z-index values.

## Content and states

- Preserve real content. Do not invent customers, metrics, testimonials, logos, inventory,
  locations, awards, weather, version labels, or operational status.
- Avoid placeholder brands such as Acme, fake people such as Jane Doe, and pseudo-precise numbers.
- Do not use decorative scroll instructions, status dots, locale strips, section numbers, or
  mono-uppercase eyebrow labels as filler.
- Use no em dash or en dash as visible prose punctuation. Rewrite with periods, commas, colons,
  parentheses, or a regular hyphen for ranges.
- Keep one CTA intent per decision point. Do not duplicate the same action under different labels.
- Implement applicable loading, empty, error, success, hover, active, focus, and disabled states.
- Use skeletons shaped like the eventual content rather than a generic spinner where skeletons are
  appropriate.
- Keep form names, order, labels, validation semantics, and analytics bindings stable unless the
  user authorizes a change.

## Assets and accessibility

- Reuse real brand imagery and icons already present before sourcing alternatives.
- Keep one icon family and follow the project's icon convention. Do not hand-draw arbitrary icon
  paths when a maintained, already-installed family provides the glyph.
- Provide meaningful alt text for informative images and empty alt text for decorative images.
- Preserve semantic landmarks, heading order, keyboard navigation, visible focus, labels, reduced
  motion, zoom, and screen-reader behavior.
- Reserve image dimensions or aspect ratios to prevent layout shift. Avoid fake screenshots made
  from decorative boxes.
- If final art is unavailable and no authorized tool can provide it, use an explicit placeholder
  slot and disclose it.

## Anti-pattern audit

Reject a design when visual novelty hides unclear hierarchy, a trend is mistaken for a design
system, motion lacks a user-facing purpose, content is fabricated, or the implementation replaces
working project conventions without need. Taste improves the product's existing constraints; it
does not erase them.
