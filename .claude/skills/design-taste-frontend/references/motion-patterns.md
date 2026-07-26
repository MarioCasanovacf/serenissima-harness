# Motion Patterns

Read this file only when motion is requested, already established, or justified by hierarchy,
feedback, state transition, or storytelling. Motion is optional.

## Choose the lightest mechanism

1. Use native CSS transitions for hover, focus, disclosure, and small state changes.
2. Use the project's existing animation library for component choreography.
3. Use IntersectionObserver or supported CSS scroll-driven animation for simple reveals.
4. Use Motion when it is already installed in a React project and motion values or layout
   transitions materially help.
5. Use GSAP with ScrollTrigger only for deliberate scroll storytelling, pinning, or timelines that
   simpler mechanisms cannot express.
6. Use WebGL only when a true canvas or 3D deliverable is in scope and performance has been
   budgeted.

Do not mix multiple animation engines in the same component subtree. Do not install an engine
solely to animate opacity and translation.

## Motion contract

- Justify every animation in one sentence.
- Keep interactions responsive and interruptible.
- Animate transform and opacity where possible. Avoid layout-thrashing properties.
- Honor prefers-reduced-motion. At reduced motion, remove parallax, pinning, autoplay, large
  translations, and continuous loops while preserving content and state feedback.
- Ensure content remains reachable without animation or JavaScript.
- Pause or stop offscreen continuous work.
- Clean up timelines, observers, listeners, and requestAnimationFrame callbacks.
- Test keyboard, touch, coarse pointer, slow device, and resize behavior.
- Keep cumulative layout shift near zero by reserving space before animation starts.

## Pattern selection

| Need | Pattern | Guardrail |
| --- | --- | --- |
| Reveal hierarchy | short stagger or grouped fade | preserve reading order |
| State transition | layout or opacity transition | announce semantic state separately |
| Button feedback | brief scale or translation | retain focus visibility |
| Story sequence | sticky section or pinned timeline | provide reduced-motion linear flow |
| Wide narrative | horizontal pan | keep keyboard and touch access; avoid trapping scroll |
| Ambient depth | restrained parallax | disable for reduced motion and small screens |

Avoid scroll listeners that update framework state every frame, decorative infinite marquees,
cursor hijacking, forced smooth scrolling, and motion whose only purpose is to demonstrate the
library. One marquee per page is an upper bound, not a target.

## React-specific note

Only in a React project that already uses Motion, import from the installed package's documented
entry point and keep motion values outside React render state. Only in a project that already uses
GSAP, create timelines inside a scoped lifecycle and revert them during cleanup. Otherwise use the
native mechanism the project already supports.
