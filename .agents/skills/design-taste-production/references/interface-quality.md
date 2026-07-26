# Interface Quality

Apply these criteria to implementation and visual review. Context outranks preference.

## Hierarchy and composition

- Make the page purpose, current state, and primary next action legible before decoration.
- Use spacing, alignment, scale, weight, and contrast as a system. Break the grid only when the
  break improves emphasis without damaging reading order or responsiveness.
- Vary composition according to content. Avoid mechanical repetition of identical cards, split
  sections, centered headlines, or ornamental metadata.
- Use containers when grouping, interaction, or elevation has meaning; whitespace alone is often
  the clearer separator.
- Keep primary content and action visible at realistic mobile and laptop heights.

## Type, color, and material

- Reuse the product's type and color tokens when present. For a new system, define a restrained
  hierarchy that survives long labels, localization, zoom, and content extremes.
- Treat color as semantic and brand-bearing. Do not reach automatically for purple gradients,
  dark meshes, beige luxury palettes, glass surfaces, or any other category shortcut.
- Keep iconography, radii, borders, shadows, and illustration treatment internally consistent.
  Novelty does not justify mixed visual grammars.
- Meet applicable WCAG contrast for text, controls, focus indicators, and text over media.

## Content and interaction

- Preserve real content and its meaning. Improve clarity without manufacturing evidence.
- Give every control an understandable label and applicable hover, focus, active, disabled,
  loading, error, and success behavior.
- Keep keyboard order aligned with visual order. Preserve landmarks, heading structure, labels,
  alt text, zoom, touch targets, screen-reader state, and visible focus.
- Use motion as information or feedback, not proof of technical sophistication.

## Product and data quality

- In dashboards, establish overview, change, exception, and action hierarchy. Do not decorate data
  at the cost of comparison, units, timestamps, source, or confidence.
- Keep tables usable with long values, missing values, many columns, selection, sorting, filtering,
  pagination, and narrow viewports. Choose deliberate adaptation instead of hiding essential data.
- Distinguish system status, user state, permission, freshness, and validation. A colored dot alone
  is not a sufficient status model.

## Anti-generic review

Reject work when it could belong to any product because the copy, hierarchy, imagery, and state
model ignore the brief. Also reject visual novelty that hides the user job, copied references that
ignore the target system, and polished happy paths that omit failure or recovery.
