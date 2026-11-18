# Rulings made through the desk

One file per ruling, `R-NNN.json`, append-only: a ruling is created once (with link(2), so
it cannot replace an existing file) and never edited. Shape (design T-484, section 3):

```json
{"id": "R-001", "decision": "D-001", "choice": "yes", "note": "",
 "ts": "2026-11-17T12:00:00Z", "by": "operator", "via": "console"}
```

`via` is `console` or `cli`. To change a ruling, rule a new decision that supersedes it;
do not edit or delete an R file. The decision card it answers lives in
`.harness/decisions/`. These files do not replace the dated, signed operator records
(`operator-rulings-*.md`), which this tooling never opens.
