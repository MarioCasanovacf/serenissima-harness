# React, Next.js, and Tailwind Branch

Read this file only when the inspected project already uses one of these technologies or the user
explicitly authorizes it for greenfield work. This branch is not the portable default.

## Inspect first

1. Read package.json, the lockfile, scripts, framework config, styling config, and representative
   components.
2. Preserve the package manager and installed major versions.
3. Identify whether Next.js uses the App Router or Pages Router and whether React Server
   Components are in play.
4. Identify the Tailwind major version and existing token or utility conventions.
5. Reuse installed component, icon, font, and animation libraries before proposing another.

Do not emit an install command or mutate dependencies unless the package is missing, the addition
is necessary, project policy allows it, and the user authorized it.

## React and Next.js

- Keep static layout in server-rendered components when the project uses Server Components.
- Isolate browser APIs, pointer physics, scroll observers, and animation libraries in small client
  leaves. Add the client directive only where required.
- Keep providers that use client state in a dedicated client boundary.
- Use local state for discrete UI state. Avoid rerendering a component tree for continuous scroll
  or pointer values; use the project's motion values, refs, observers, or requestAnimationFrame
  pattern.
- Clean up event listeners, observers, timelines, and animation frames in effects.
- Use the project's image and font facilities. In Next.js, preserve next/image and next/font
  conventions when already configured.
- Preserve route structure, metadata, structured data, cache behavior, analytics events, and
  server/client boundaries during redesigns.

## Tailwind

- Match the installed major version. Do not migrate Tailwind as a side effect of visual work.
- Reuse theme tokens and project utilities instead of scattering arbitrary values.
- Express mobile behavior explicitly and test the actual breakpoints configured by the project.
- Prefer grid utilities over brittle width calculations.
- Avoid h-screen for a mobile full-height hero when min-height with dynamic viewport units is
  supported by the browser policy.
- Keep class composition consistent with the project. If it uses variants or a class-merging
  helper, follow that convention.
- Tailwind v4 projects commonly use the dedicated PostCSS or Vite integration. Never replace a
  working configuration from memory.

## Dependency-neutral alternatives

If React, Next.js, or Tailwind is absent, stop using this branch. Translate the design intent into
the project's native framework, CSS modules, scoped styles, design tokens, or plain HTML/CSS
without introducing this stack.
