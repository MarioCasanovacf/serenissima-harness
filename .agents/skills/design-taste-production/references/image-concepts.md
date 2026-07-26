# Image Concepts

Use only when imagery is part of the brief or image concept is the locked mode. Image tooling is
optional; a strong, executable art-direction brief is a valid deliverable.

## Start from the interface role

Name the image's job: explain the product, establish emotion, provide evidence, show context, anchor
identity, or support narrative. Define placement, crop behavior, focal safe area, expected aspect
ratios, responsive variants, text overlay needs, contrast, and performance budget before generating
or sourcing art.

## Write a production concept

Specify subject, environment, composition, camera or rendering language, light, palette, material,
texture, mood, negative space, exclusions, and how the image connects to the design system. Prefer a
coherent image family over unrelated prompts for each section. Include accessibility intent and
fallback behavior.

For mobile multi-frame concepts, first lock platform conventions, safe areas and system regions,
navigation model, keyboard behavior, typography, spacing, radii, and icon language. Map the logical
flow and its loading, empty, error, success, permission, and interruption states before composing
frames. Maintain a compact design bible across every screen so chrome, components, content density,
and interaction cues remain consistent. Honor whether the request asks for raw screens or device
mockups; never force a phone frame or presentation mockup onto production screen assets.

Do not request or present fabricated customer evidence, product UI, logos, endorsements, people,
locations, or metrics as real. Avoid imitating a living artist or copying protected brand assets.
Use supplied and licensed material according to its terms.

## Choose the capability conditionally

1. Reuse appropriate repository assets.
2. Use user-provided assets.
3. Use authorized image generation, search, or licensed sources when available and in scope.
4. Otherwise provide the concept specification and a clearly labeled placeholder only for the
   truly missing external asset or dependency. State its dimensions, interface role, and the next
   step required to replace it.

When a tool produces an asset, inspect anatomy, text, logos, edges, transparency, crop resilience,
color, compression, and fit in the actual interface. Generate responsive variants only when they
serve real layout needs. Record the tool or source and any licensing or attribution requirement.
