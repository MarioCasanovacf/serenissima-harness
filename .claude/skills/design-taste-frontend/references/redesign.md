# Redesign Protocol

Read this file whenever changing an existing interface.

## Classify the mode

- **Preserve:** modernize without breaking the recognizable brand.
- **Overhaul:** establish a new visual language while preserving content and product behavior.
- **Greenfield:** use only when no existing surface exists or the user explicitly approves a
  restart.

If preserve versus overhaul changes the solution and the brief is silent, ask one focused
question.

## Audit before editing

Record:

- Framework, package manager, component architecture, design system, and installed dependencies.
- Brand colors, typography, logo treatment, icon family, radii, spacing, and motion language.
- Information architecture, routes, navigation labels, anchors, and conversion paths.
- Content blocks, copy voice, real assets, signature interactions, and reusable primitives.
- Accessibility behavior: landmarks, headings, keyboard flow, focus, contrast, labels, and alt
  text.
- Analytics identifiers, events, form field names, consent behavior, SEO metadata, structured
  data, canonical URLs, redirects, and social cards.
- Existing DESIGN_VARIANCE, MOTION_INTENSITY, and VISUAL_DENSITY.
- Broken behavior, performance traps, generic visual patterns, and content debt.

## Preserve by default

Do not silently change route slugs, primary navigation, anchor IDs, form field names or order,
analytics hooks, consent or legal copy, logo or wordmark, brand colors, copy voice, SEO metadata,
structured data, accessibility wins, or public behavior. These are product contracts, not visual
preferences.

## Modernize in risk order

1. Typography and hierarchy.
2. Spacing and vertical rhythm.
3. Color and neutral consistency while retaining the brand accent.
4. States and restrained motion.
5. Hero and key-section composition.
6. Full block replacement only when the existing structure cannot satisfy the brief.

When IA, content, and SEO are sound, prefer targeted evolution. When structural debt breaks mobile,
accessibility, or comprehension, propose the larger change and make its migration risks explicit.

## Verify redesign integrity

Compare before and after for route coverage, navigation, content, forms, analytics, SEO,
accessibility, responsive behavior, and performance. A visually stronger page that loses tracking,
content, keyboard access, or discoverability is a regression.
