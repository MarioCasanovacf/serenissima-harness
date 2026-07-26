# Data visualization and numeric composition

Make the analytical question visible before styling the chart. A graph is evidence, not texture.

## Select the chart from the comparison

| Analytical job | Default form | Required discipline |
| --- | --- | --- |
| Exact value or KPI | Annotated number | State unit, period, benchmark, and direction; do not add a chart without a comparison. |
| Category magnitude or rank | Horizontal bar | Use a common zero baseline and sort deliberately unless source order has meaning. |
| Change over time | Line; columns for short discrete periods | Preserve intervals, mark missing data, and label the final value or relevant event directly. |
| Part to whole | 100% stacked bar | Keep order stable and label segments directly; prefer a table when exact values matter most. |
| Distribution | Histogram, dot/strip plot, box plot, or interval plot | Show spread and sample size; do not summarize a distribution with a categorical bar. |
| Relationship | Scatter plot | State units on both axes; distinguish observation from fitted trend or causal claim. |
| Target, threshold, or deviation | Bullet chart, dot plot, or diverging bar | Draw the target, zero, or reference explicitly. |
| Before and after | Slopegraph or dumbbell plot | Preserve entity identity and label both endpoints. |
| Uncertainty | Interval, band, whisker, or range | Show uncertainty in the geometry, not only in prose. |
| Flow | Staged table or Sankey only when conserved flow is the question | Label quantities at each transition; avoid decorative ribbons. |

Avoid gauges, radar charts, 3D charts, decorative area fills, and dual axes. Use a donut only for a
single snapshot with no more than three directly labeled parts when angle comparison is not the
main task. If a plot needs more than five simultaneous series, prefer small multiples or a table.

## Encode in a legible order

Prefer position on a common scale, then length, then shape or line style. Use area and angle only
when approximate comparison is sufficient. Treat color as a secondary channel for meaning,
grouping, or focus; never use it to compensate for weak geometry.

- Ask one primary question per plot.
- Label important evidence directly; avoid a legend when labels fit beside the marks.
- Anchor every numeric label to the mark or segment it describes. In stacked bars, place labels
  inside the segment or at its geometric center on a shared label track; never distribute labels
  into equal columns when the segments have unequal widths. Move a label outside with a leader
  only when the segment is too narrow.
- Preserve units, period, source, sample size, freshness, uncertainty, and applicable baseline.
- Keep categorical order stable across views. Sort only when the new order clarifies the question.
- Keep the same meaning in the same color across the artifact.
- Use one focal accent and quiet context instead of coloring every mark.
- Use at most one grey data encoding in a chart. Set it at full, clearly visible strength; never
  create additional data series from lighter or darker greys. Structural gridlines may remain
  faint only when they cannot be mistaken for data.
- Inspect at actual size and in grayscale. If a series distinction disappears, add a visibly
  different semantic hue, line style, marker, pattern, position, or split view.
- Do not rely on color alone. Pair status or series color with a direct label and at least one
  redundant mark, pattern, line style, sign, or position.

In a brand-neutral profile, derive color from the product or supplied brand rather than importing
Mario's palette. In `personal:mario`, apply the stable semantic map and chart recipes in
`mario-data-semantics.md`.

## Compose numbers as geometry

Treat alignment as part of meaning, especially on landing pages, dashboards, tables, and slides.

- Use tabular lining numerals for compared values:
  `font-variant-numeric: tabular-nums lining-nums`.
- Verify the actual glyphs. If the selected display face still produces old-style figures with
  different heights or descenders, set analytical numbers in a lining-capable sans or mono face;
  do not manually nudge individual digits.
- Right-align values in columns. Align decimals when decimal comparison matters.
- Put repeated metric blocks on shared grid tracks with the same label / value / unit order.
- Align large KPIs and their deltas or qualifiers on a deliberate baseline. Do not position them
  with arbitrary margins that vary by digit count.
- Keep signs, currency symbols, percentages, and units consistently attached or in a dedicated
  column. Do not mix both treatments in one comparison.
- Keep each ISO date token unbroken. At a narrow viewport, stack the whole range or move it to its
  own row instead of breaking `2026-W22` across lines.
- Do not rotate containers that hold axes, metrics, tables, or analytical figures.
- Reserve a stable width for values that update so the layout does not jump.

Test with short and long values such as `9`, `88.8%`, `1,165`, and `10,000`, plus the longest
expected period and unit. Inspect the narrow and wide target sizes; confirm shared baselines,
unbroken dates, decimal alignment where applicable, and no clipping.
