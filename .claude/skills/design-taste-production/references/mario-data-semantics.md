# Mario data semantics

Use color sparingly and keep each meaning stable across every flagged surface.

| Meaning | Token | Value | Required non-color redundancy |
| --- | --- | --- | --- |
| Positive / success | Forest | `#2E4A3F` | Direct label plus an upward or affirmative marker |
| Warning | Ochre | `#A87333` | Direct label plus a warning marker or annotation |
| Negative / critical | Oxblood | `#6E1F1F` | Direct label plus a downward or critical marker |
| Neutral | Warm grey | `#6B655C` | Direct label plus distinct position, pattern, or line style |
| Structure / reference / total | Ink | `#1A1814` | Axis, rule, baseline, reference, or total plus a direct label |

Never ask hue to carry status alone. Add text labels and at least one redundant sign, shape,
pattern, line style, position, or annotation. Verify grayscale interpretation, contrast, and
legibility at the required viewport or slide size. Ink organizes evidence; it is not another
status series.

Prevent CTA/status collision. On a surface where oxblood communicates negative or critical state,
do not also use oxblood for a primary action, link emphasis, or decorative highlight. Use an ink
and paper action treatment or another non-status treatment instead. Likewise, do not turn forest,
ochre, or warm grey into CTA colors. One chromatic role must not imply two meanings on the same
surface, and decorative color must never compete with the evidence.

## Use semantic chart recipes

Choose the chart from the analytical question before assigning color.

| Question | Preferred Mario treatment |
| --- | --- |
| One bounded KPI | Set the value in ink unless it carries status; use forest, ochre, or oxblood only when the label states that same status. Include unit, period, and comparison. |
| Positive / neutral / negative composition | Prefer a 100% stacked bar with stable order, direct labels anchored to their actual segments, and a textual total. Use forest / warm grey / oxblood plus a redundant marker or pattern. Never place unequal segment values in equal-width label columns. |
| Status over time | Prefer small multiples when lines would overlap. If one plot is materially clearer, use direct end labels and distinct solid / dashed / dotted lines or marks in addition to semantic color. |
| Target or threshold | Prefer a bullet chart or position-on-scale plot. Draw the target or baseline in ink; color the observed value only when its status is known. |
| Ranked drivers or exceptions | Prefer sorted horizontal bars. Use ink for neutral magnitude, oxblood only for critical drivers, and ochre only for warnings requiring attention. |
| Deviation around zero | Use a diverging bar with an ink zero line, forest for favorable deviation, and oxblood for unfavorable deviation. |
| Uncertainty | Add intervals, bands, whiskers, or ranges. Never imply certainty through a saturated solid shape. |

A donut is acceptable only for a single snapshot with no more than three directly labeled parts
when exact cross-category comparison is not the main task. Otherwise use a stacked bar or table.
Do not use gauges, radar charts, 3D charts, decorative area fills, or dual axes.

For nominal categories without positive, warning, negative, or neutral meaning, do not recycle the
semantic palette as arbitrary decoration. Use ink with direct labels and clearly different
markers, line styles, positions, or small multiples. If more than three neutral series would make
those encodings hard to scan, split the view or use a table instead of introducing a rainbow.

Use no more than one grey data encoding in a chart. Render warm grey `#6B655C` at full strength
and never accompany it with a lighter, darker, or translucent grey data series. Faint structural
rules are acceptable only when they cannot be mistaken for data. If another neutral comparison is
required, change its line style, marker, position, or use small multiples instead of adding grey.
