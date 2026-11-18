# Decision cards

One file per pending decision, `D-NNN.json`. The operator rules a card through
`python3 .harness/bin/operator_desk.py rule D-NNN --choice C [--note N]` (or the console),
never by editing the file. Shape (design T-484, section 3):

```json
{"id": "D-001", "title": "short", "question": "plain words",
 "recommendation": "yes", "if_yes": "what happens", "if_no": "what happens",
 "options": ["yes", "no"], "blocks": ["T-123"], "status": "open",
 "created": "2026-11-17"}
```

`status` is `open` until a ruling exists, then `ruled` (set by `operator_desk.py`, which
also adds `"ruling": "R-NNN"`). A card is never deleted; the ruling stays beside it in
`.harness/rulings/`. Dated records (`operator-rulings-*.md`, `coordinator-decisions-*`)
are separate and are never touched by this directory's tooling.
