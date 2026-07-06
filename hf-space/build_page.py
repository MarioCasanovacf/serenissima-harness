"""Local build tool (not run on HF): reads the real harness snapshots in data/
and emits a single static index.html in Mario Casanova's portfolio design system,
with hand-authored SVG diagrams + client-side-interactive plotly figures.

Run:  python3 build_page.py   ->  writes index.html
"""
import html
import json
from collections import defaultdict
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go

HERE = Path(__file__).parent
BLACKBOARD = json.loads((HERE / "data" / "blackboard.json").read_text())
STATE = json.loads((HERE / "data" / "state.json").read_text())
TASKS = BLACKBOARD["tasks"]
EVOLUTION = STATE.get("evolution", {})

PAPER, PAPER_DEEP, PAPER_HI = "#F4EFE6", "#EBE4D6", "#FAF6EE"
INK, INK_2, INK_3, INK_4 = "#1A1814", "#3C3833", "#6B655C", "#948D82"
OXBLOOD, OCHRE, FOREST = "#6E1F1F", "#A87333", "#2E4A3F"
RULE_SOFT = "rgba(26,24,20,0.16)"
SANS = '"IBM Plex Sans","Helvetica Neue",Arial,sans-serif'
MONO = '"IBM Plex Mono","SF Mono",Menlo,monospace'
STATUS_COLOR = {"done": INK, "failed": INK_4, "open": OCHRE, "in_progress": FOREST,
                "review": OXBLOOD, "claimed": "#C28A45", "blocked": "#8A2B2B"}
EPIC_LABEL = {
    "E-01": "E-01 · Bootstrap the substrate", "E-02": "E-02 · Agency tooling",
    "E-03": "E-03 · Evolution loop", "ready-for-usage": "Ready-for-usage certification",
    "mdtoc": "mdtoc · first real project", "cronsplain": "cronsplain · second real project",
    "gen-2-fixes": "Generation 2 · fixes", "gen-3-early": "Generation 3 · early",
    "gen-3": "Generation 3", "gen-4": "Generation 4",
    "scratch": "Guardrail probe", "scratch-guardrail": "Guardrail probe",
    "scratch-guardrail-v2": "Guardrail probes · producer vs approver",
    "scratch-swarm": "Swarm smoke test", "scratch-usage-doc": "Usage-doc scratch"}


# ---------------------------------------------------------------- SVG helpers
def _defs():
    return ('<defs><marker id="ah" markerWidth="9" markerHeight="9" refX="7.5" '
            'refY="4" orient="auto"><path d="M0,0 L9,4 L0,8 z" fill="#1A1814"/>'
            '</marker></defs>')


def _box(x, y, w, h, lines, accent=False):
    stroke = OXBLOOD if accent else INK
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{PAPER_HI}" '
         f'stroke="{stroke}" stroke-width="1"/>')
    cy = y + h / 2 - (len(lines) - 1) * 8
    for i, (txt, sub) in enumerate(lines):
        fs = 11 if sub else 13
        fill = INK_3 if sub else (OXBLOOD if accent and i == 0 else INK)
        s += (f'<text x="{x + w / 2}" y="{cy + i * 16}" text-anchor="middle" '
              f'dominant-baseline="middle" font-family=\'{SANS}\' font-size="{fs}" '
              f'fill="{fill}">{txt}</text>')
    return s


def _arrow(x1, y1, x2, y2, label=None, dashed=False):
    dash = ' stroke-dasharray="4 3"' if dashed else ''
    s = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{INK}" '
         f'stroke-width="1" marker-end="url(#ah)"{dash}/>')
    if label:
        s += (f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 5}" text-anchor="middle" '
              f'font-family=\'{SANS}\' font-size="11" fill="{INK_3}">{label}</text>')
    return s


def _svg(vb_w, vb_h, body):
    return (f'<svg viewBox="0 0 {vb_w} {vb_h}" role="img" '
            f'style="display:block;width:100%;height:auto">{_defs()}{body}</svg>')


def topology_svg():
    b = ""
    b += _box(310, 14, 140, 40, [("You (human)", False)])
    b += _arrow(380, 54, 380, 86, "goal")
    b += _box(285, 86, 190, 50, [("Coordinator", False), ("the main Claude session", True)], accent=True)
    b += _arrow(380, 136, 140, 188) + _arrow(380, 136, 380, 188) + _arrow(380, 136, 620, 188)
    b += _box(38, 188, 204, 52, [("Planner", False), ("builds the task DAG", True)])
    b += _box(278, 188, 204, 52, [("Workers x N", False), ("claim · lock · build", True)])
    b += _box(518, 188, 204, 52, [("Verifiers", False), ("replay · verdict", True)])
    b += _arrow(140, 240, 200, 286) + _arrow(380, 240, 380, 286) + _arrow(620, 240, 560, 286)
    b += _box(38, 286, 684, 46, [(".harness/  ·  blackboard.json · locks · logs · state.json", False),
                                 ("the shared board — the only source of truth", True)])
    return _svg(760, 344, b)


def lifecycle_svg():
    # Boxes 104px wide with 55px gaps so the arrow labels fit BETWEEN boxes;
    # labels ride above the arrow line, clear of every box.
    xs = [8, 167, 326, 485, 644]
    W, Y, H = 104, 40, 40
    labels = ["open", "claimed", "in_progress", "review", "done"]
    b = ""
    for x, lab in zip(xs, labels):
        b += _box(x, Y, W, H, [(lab, False)], accent=(lab == "done"))
    arrow_labels = ["claim", "update", "handoff", "verdict"]
    for i, al in enumerate(arrow_labels):
        x1, x2 = xs[i] + W, xs[i + 1]
        mid = (x1 + x2) / 2
        b += (f'<line x1="{x1}" y1="{Y + H / 2}" x2="{x2}" y2="{Y + H / 2}" '
              f'stroke="{INK}" stroke-width="1" marker-end="url(#ah)"/>')
        b += (f'<text x="{mid}" y="{Y - 8}" text-anchor="middle" '
              f'font-family=\'{SANS}\' font-size="10" fill="{INK_3}">{al}</text>')
    # return path: rejected / lease expiry back to the pool — clean arc below
    b += (f'<path d="M {xs[3] + W / 2} {Y + H} C {xs[3] + W / 2} {Y + H + 46}, '
          f'{xs[0] + W / 2} {Y + H + 46}, {xs[0] + W / 2} {Y + H + 6}" '
          f'fill="none" stroke="{INK}" stroke-width="1" stroke-dasharray="4 3" '
          f'marker-end="url(#ah)"/>')
    b += (f'<text x="{(xs[0] + xs[3]) / 2 + W / 2}" y="{Y + H + 42}" text-anchor="middle" '
          f'font-family=\'{SANS}\' font-size="11" fill="{INK_3}">lease expiry / rejected'
          f'&#160;&#160;returns to the pool</text>')
    b += (f'<text x="{(xs[3] + xs[4]) / 2 + W / 2}" y="{Y + H + 66}" text-anchor="end" '
          f'font-family=\'{SANS}\' font-size="11" fill="{OXBLOOD}">verdict given by a '
          f'different agent&#160;&#160;·&#160;&#160;producer ≠ approver</text>')
    return _svg(760, 156, b)


def evolution_svg():
    xs = [8, 150, 292, 434, 576]
    nodes = [[("logs", False)], [("proposals", False), ("evidence-cited", True)],
             [("verification", False), ("adversarial", True)],
             [("human gate", False)], [("generation", False), ("bump", False)]]
    accents = [False, False, False, True, False]
    b = ""
    for x, n, ac in zip(xs, nodes, accents):
        b += _box(x, 54, 128, 46, n, accent=ac)
    for i in range(4):
        b += _arrow(xs[i] + 128, 77, xs[i + 1], 77)
    # return arc on top: the harness changes itself
    b += (f'<path d="M {xs[4] + 64} 54 C {xs[4] + 64} 14, {xs[0] + 64} 14, {xs[0] + 64} 54" '
          f'fill="none" stroke="{INK}" stroke-width="1" stroke-dasharray="4 3" '
          f'marker-end="url(#ah)"/>')
    b += (f'<text x="360" y="12" text-anchor="middle" font-family=\'{SANS}\' '
          f'font-size="11" fill="{INK_3}">the harness rewrites its own spec, one generation at a time</text>')
    return _svg(760, 118, b)


# ---------------------------------------------------------------- plotly
def _levels(nodes, edges):
    g = nx.DiGraph()
    g.add_nodes_from(nodes)
    for a, c in edges:
        if a in nodes and c in nodes:
            g.add_edge(a, c)
    lvl = {}
    order = list(nx.topological_sort(g)) if nx.is_directed_acyclic_graph(g) else list(nodes)
    for n in order:
        preds = list(g.predecessors(n))
        lvl[n] = 0 if not preds else 1 + max(lvl.get(p, 0) for p in preds)
    return lvl


def _positions(sub, edges):
    lvl = _levels(list(sub), edges)
    by = defaultdict(list)
    for tid, l in sorted(lvl.items()):
        by[l].append(tid)
    pos = {}
    for l, ids in by.items():
        for i, tid in enumerate(sorted(ids)):
            pos[tid] = (l, -(i - (len(ids) - 1) / 2))
    return pos


def dag_figure():
    order = ["E-01", "E-02", "E-03", "mdtoc", "cronsplain", "ready-for-usage",
             "gen-2-fixes", "gen-3-early", "gen-3", "gen-4", "scratch-swarm",
             "scratch-guardrail-v2", "scratch-guardrail", "scratch-usage-doc", "scratch"]
    present = [e for e in order if any(t.get("epic") == e for t in TASKS.values())]
    fig = go.Figure()
    trace_epic = []
    default = present[0]
    for e in present:
        sub = {tid: t for tid, t in TASKS.items() if t.get("epic") == e}
        edges = [(d, tid) for tid, t in sub.items()
                 for d in (t.get("depends_on") or []) if d in sub]
        pos = _positions(sub, edges)
        ex, ey = [], []
        for a, c in edges:
            ex += [pos[a][0], pos[c][0], None]
            ey += [pos[a][1], pos[c][1], None]
        fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", hoverinfo="skip",
                                 line=dict(color=RULE_SOFT, width=1.1),
                                 visible=(e == default), showlegend=False))
        trace_epic.append(e)
        ids = list(sub)
        fig.add_trace(go.Scatter(
            x=[pos[t][0] for t in ids], y=[pos[t][1] for t in ids], mode="markers+text",
            marker=dict(size=24, line=dict(color=PAPER, width=1.3),
                        color=[STATUS_COLOR.get(sub[t].get("status"), INK_4) for t in ids]),
            text=ids, textposition="middle center",
            textfont=dict(size=7.5, color=PAPER_HI, family=MONO),
            customdata=[[sub[t].get("title", ""), sub[t].get("status", ""), sub[t].get("role", ""),
                         sub[t].get("completed_by") or sub[t].get("claimed_by") or "—"] for t in ids],
            hovertemplate="<b>%{text}</b> · %{customdata[1]}<br>%{customdata[0]}"
                          "<br>role: %{customdata[2]} · by: %{customdata[3]}<extra></extra>",
            visible=(e == default), showlegend=False))
        trace_epic.append(e)
    buttons = [dict(label=EPIC_LABEL.get(e, e), method="update",
                    args=[{"visible": [te == e for te in trace_epic]}]) for e in present]
    fig.update_layout(
        updatemenus=[dict(buttons=buttons, direction="down", showactive=True, x=0,
                          xanchor="left", y=1.14, yanchor="top", bgcolor=PAPER_HI,
                          bordercolor=RULE_SOFT, font=dict(family=SANS, size=13, color=INK))],
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        plot_bgcolor=PAPER, paper_bgcolor=PAPER, height=520, margin=dict(l=8, r=8, t=64, b=8),
        font=dict(family=SANS, color=INK),
        hoverlabel=dict(bgcolor=PAPER_HI, bordercolor=RULE_SOFT, font=dict(family=SANS, color=INK)),
        dragmode=False)
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displayModeBar": False})


def tests_figure():
    fig = go.Figure(go.Bar(
        x=[63, 93], y=["mdtoc (Python)", "cronsplain (Node.js)"], orientation="h",
        marker_color=[INK, OXBLOOD], text=["63 tests", "93 tests"], textposition="outside",
        textfont=dict(family=SANS, size=13, color=INK), width=0.5, hoverinfo="skip"))
    fig.update_layout(
        plot_bgcolor=PAPER, paper_bgcolor=PAPER, height=200, margin=dict(l=8, r=48, t=10, b=10),
        font=dict(family=SANS, color=INK, size=13),
        xaxis=dict(visible=False, range=[0, 108]),
        yaxis=dict(tickfont=dict(family=SANS, size=13, color=INK)))
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})


def ledger_rows():
    out = []
    for m in EVOLUTION.get("accepted_mutations", []):
        tgt = m.get("target", [])
        out.append((m.get("id", ""), "applied",
                    ", ".join(tgt) if isinstance(tgt, list) else str(tgt), m.get("summary", "")))
    for p in EVOLUTION.get("pending_proposals", []):
        tgt = p.get("target", [])
        st = "rejected" if "reject" in p.get("status", "") else p.get("status", "pending")
        out.append((p.get("id", ""), st,
                    ", ".join(tgt) if isinstance(tgt, list) else str(tgt), p.get("summary", "")))
    rows = []
    for pid, st, tgt, summ in out:
        cls = "st-rej" if st == "rejected" else "st-ok"
        rows.append(f"<tr><td><code>{html.escape(pid)}</code></td>"
                    f"<td><span class='pill {cls}'>{html.escape(st)}</span></td>"
                    f"<td><code>{html.escape(tgt)}</code></td><td>{html.escape(summ)}</td></tr>")
    return "\n".join(rows)


def counts():
    tasks = list(TASKS.values())
    return dict(tasks=len(tasks), done=sum(1 for t in tasks if t.get("status") == "done"),
                epics=len({t.get("epic") for t in tasks}), gen=EVOLUTION.get("generation", "?"),
                accepted=len(EVOLUTION.get("accepted_mutations", [])))


C = counts()
TOPOLOGY, LIFECYCLE, EVOLOOP = topology_svg(), lifecycle_svg(), evolution_svg()
DAG_HTML, TESTS_HTML, LEDGER = dag_figure(), tests_figure(), ledger_rows()

SUBSTRATE = """.harness/
 ├── blackboard.json   the task DAG — only blackboard.py may write it
 ├── bin/              nine stdlib-only CLIs: blackboard, lock, session,
 │                     goal_mode, ast_index, notify, recontext, log hooks,
 │                     and migrate_project.py (one-command transplant)
 ├── locks/  logs/     TTL write-locks · append-only evidence (events + transcript)
 └── state.json        limits, human gates, agent registry, evolution memory
.claude/agents/        the bench: planner / worker / verifier / evolution-analyst
ORCHESTRATION.md       the topology contract (DAG, lifecycle, invariants)"""

PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Serenissima Harness</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<style>
@import url('https://fonts.googleapis.com/css2?family=GFS+Didot&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root {{
  --paper:#F4EFE6; --paper-deep:#EBE4D6; --paper-hi:#FAF6EE;
  --ink:#1A1814; --ink-2:#3C3833; --ink-3:#6B655C; --ink-4:#948D82;
  --oxblood:#6E1F1F; --oxblood-2:#8A2B2B; --oxblood-tint:rgba(110,31,31,0.08);
  --ochre:#A87333; --rule-soft:rgba(26,24,20,0.16);
  --font-display:'GFS Didot','Didot',Georgia,serif;
  --font-serif:'EB Garamond','Garamond',Georgia,serif;
  --font-sans:'IBM Plex Sans','Helvetica Neue',Arial,sans-serif;
  --font-mono:'IBM Plex Mono','SF Mono',Menlo,monospace;
  --measure:32rem; --wide:44rem; --full:min(960px,100vw - 48px);
}}
* {{ box-sizing:border-box; }}
html,body {{ margin:0; background:var(--paper); color:var(--ink);
  font-family:var(--font-serif); font-size:16px; line-height:24px;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; }}
::selection {{ background:var(--oxblood-tint); }}
.col {{ max-width:var(--measure); margin:0 auto; padding:0 24px; }}
.eyebrow {{ font-family:var(--font-sans); font-size:11px; font-weight:600;
  letter-spacing:.18em; text-transform:uppercase; color:var(--ink-3); }}
.hero {{ padding:112px 24px 72px; border-bottom:1px solid var(--rule-soft); }}
.hero-inner {{ max-width:var(--wide); margin:0 auto; }}
.hero .eyebrow {{ margin-bottom:32px; }}
.hero h1 {{ font-family:var(--font-display); font-weight:400; font-size:72px;
  line-height:.99; letter-spacing:-.02em; margin:0; color:var(--ink); max-width:16ch; }}
.hero h1 em {{ font-style:italic; }}
.hero .lede {{ font-family:var(--font-serif); font-size:21px; line-height:1.55;
  color:var(--ink-2); max-width:38rem; margin:40px 0 0; }}
@media (max-width:760px) {{ .hero {{ padding:64px 24px 48px; }} .hero h1 {{ font-size:44px; line-height:1.05; }} }}
.sec-head {{ margin:80px auto 16px; max-width:var(--measure); padding:0 24px; }}
.sec-head h2 {{ font-family:var(--font-sans); font-weight:500; font-size:22px;
  line-height:32px; color:var(--ink); margin:0; }}
.sec-num {{ font-family:var(--font-mono); color:var(--ink-3); margin-right:12px; }}
p {{ font-family:var(--font-serif); font-size:16px; line-height:24px; margin:0 0 16px;
  max-width:var(--measure); text-align:justify; hyphens:auto; -webkit-hyphens:auto; }}
strong {{ font-weight:600; }} em {{ font-style:italic; }}
a {{ color:var(--oxblood); text-decoration:underline; text-decoration-thickness:1px; text-underline-offset:3px; }}
a:hover {{ color:var(--oxblood-2); text-decoration-thickness:2px; }}
code {{ font-family:var(--font-mono); font-size:13px; background:var(--paper-deep); padding:2px 6px; border-radius:2px; }}
table {{ border-collapse:collapse; width:100%; margin:16px 0; }}
th,td {{ border:1px solid var(--rule-soft); padding:8px 10px; text-align:left; vertical-align:top; }}
th {{ background:var(--paper-deep); font-family:var(--font-sans); font-size:11px; font-weight:600;
  letter-spacing:.08em; text-transform:uppercase; color:var(--ink-2); }}
td {{ font-family:var(--font-sans); font-size:13px; line-height:20px; color:var(--ink-2); }}
.callout {{ max-width:var(--measure); margin:40px auto; padding:24px; background:var(--paper-deep); border-top:1px solid var(--ink); }}
.callout--limits {{ border-top-color:var(--oxblood); }}
.callout .head {{ font-family:var(--font-sans); font-size:11px; font-weight:600; letter-spacing:.18em;
  text-transform:uppercase; color:var(--ink-2); margin-bottom:12px; }}
.callout--limits .head {{ color:var(--oxblood); }}
.callout .body {{ font-family:var(--font-serif); font-size:13px; line-height:20px; color:var(--ink-2); }}
.callout .body p {{ text-align:justify; margin-bottom:0; }}
pre.code {{ max-width:var(--wide); margin:32px auto; background:var(--paper-deep); padding:16px 24px;
  border-radius:2px; overflow-x:auto; font-family:var(--font-mono); font-size:12.5px; line-height:20px;
  color:var(--ink); }}
.ledger {{ max-width:var(--wide); margin:16px auto; padding:0 24px; }}
.ledger-wrap {{ max-height:420px; overflow-y:auto; border:1px solid var(--rule-soft); background:var(--paper-hi); }}
.ledger-wrap table {{ margin:0; }} .ledger-wrap th {{ position:sticky; top:0; }}
.pill {{ font-family:var(--font-sans); font-size:10px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; padding:2px 7px; }}
.st-ok {{ color:var(--ink-3); }} .st-rej {{ color:var(--oxblood); background:var(--oxblood-tint); }}
.figure {{ max-width:var(--full); margin:40px auto; padding:0 24px; }}
.figure--wide {{ max-width:var(--wide); }}
.figure .rule {{ border-top:1px solid var(--ink); border-bottom:1px solid var(--ink); height:4px; margin-bottom:24px; }}
.figure .canvas {{ background:var(--paper); }}
.figure .canvas svg {{ display:block; width:100%; height:auto; }}
.figure .caption {{ margin-top:16px; display:flex; gap:12px; align-items:baseline; max-width:var(--measure);
  font-family:var(--font-sans); font-size:13px; line-height:20px; }}
.figure .label {{ font-weight:600; letter-spacing:.04em; color:var(--ink); flex:none; white-space:nowrap; }}
.figure .desc {{ color:var(--ink-2); }}
.key {{ max-width:var(--measure); margin:8px auto 0; padding:0 24px; display:flex; flex-wrap:wrap; gap:14px;
  font-family:var(--font-sans); font-size:12px; color:var(--ink-3); }}
.key i {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; vertical-align:middle; }}
.stats {{ max-width:var(--wide); margin:24px auto; padding:20px 24px; border-top:1px solid var(--rule-soft);
  border-bottom:1px solid var(--rule-soft); display:flex; flex-wrap:wrap; gap:32px; }}
.stat b {{ display:block; font-family:var(--font-display); font-size:40px; line-height:1; color:var(--ink); }}
.stat span {{ font-family:var(--font-sans); font-size:11px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3); }}
footer {{ max-width:var(--measure); margin:80px auto 0; padding:24px 24px 0; border-top:1px solid var(--rule-soft); }}
footer p {{ font-family:var(--font-sans); font-size:13px; line-height:20px; color:var(--ink-3); text-align:left; max-width:none; }}
</style>
</head>
<body>

<div class="hero"><div class="hero-inner">
  <p class="eyebrow">A society of agents</p>
  <h1>Serenissima<br><em>Harness</em></h1>
  <p class="lede">A file-based coordination substrate that lets several AI agents work on one
  real codebase in parallel &mdash; without stepping on each other, without approving their own
  work, and leaving an auditable trail behind every decision.</p>
</div></div>

<main>

<section>
  <div class="sec-head"><h2><span class="sec-num">01</span>The load-bearing layer</h2></div>
  <div class="col">
    <p>No database. No external APIs. No framework to buy into. Plain files, nine stdlib-only
    Python CLIs, and a set of rules that are <strong>programs for agents to really work</strong>
    &mdash; an agent can&rsquo;t claim a blocked task or edit a file someone else is holding
    because the command refuses it, not because it agreed to behave.</p>
    <p>It was built for Claude Code, but nothing in the contract is Claude-specific. Any agent
    &mdash; or human &mdash; that can run a CLI can join the board. What it is <em>not</em>: an
    agent framework, a runtime, or a prompt library. It is the boring layer underneath that
    decides who does what, who is allowed to say it is done, and how you would ever reconstruct
    what happened.</p>
  </div>
</section>

<section>
  <div class="sec-head"><h2><span class="sec-num">02</span>Why it exists, and who does the work</h2></div>
  <div class="col">
    <p>Two failure modes show up the moment you run more than one coding agent at once:
    <strong>unmanaged parallelism</strong> &mdash; no shared index, no ownership, so agents
    duplicate work and overwrite each other &mdash; and <strong>the giant cascade</strong>, one
    long A&rarr;B&rarr;C chain where every hop loses context and one stalled link freezes the
    pipeline. The resolution is a simple idea: <strong>delegation is a property of the task
    graph.</strong> A cascade exists <em>exactly</em> where one task consumes another&rsquo;s
    artifact and nowhere else; everything else runs in parallel under leased claims and locks.</p>
    <p>The name comes from how I pictured it: the whole city of Venice in the Renaissance
    working toward your goal &mdash; a society of agents coordinated by institutions, not by a
    single brain. Venice lasted roughly eleven centuries because its procedures governed it. The
    intelligence lives in the agents; the substrate that coordinates them is deliberately dumb,
    deterministic, and auditable.</p>
  </div>
  <div class="figure figure--wide">
    <div class="canvas">{TOPOLOGY}</div>
    <div class="caption"><span class="label">Fig. 1</span><span class="desc">A human states a
    goal; the coordinator decomposes it and dispatches a planner, a pool of workers, and
    verifiers, all coordinating through one shared board on disk.</span></div>
  </div>
</section>

<section>
  <div class="sec-head"><h2><span class="sec-num">03</span>Three layers on plain files</h2></div>
  <div class="col">
    <p>The design follows a three-layer split &mdash; <strong>Control</strong> (the rules and
    personas, written as natural-language documents an agent reads), <strong>Agency</strong>
    (the CLI tools that enforce those rules), and <strong>Runtime</strong> (the file substrate
    that holds all shared state). Nothing lives in a hidden service; every layer is a file you
    can open, diff, and version.</p>
  </div>
  <pre class="code">{html.escape(SUBSTRATE)}</pre>
</section>

<section>
  <div class="sec-head"><h2><span class="sec-num">04</span>The rules, and what enforces them</h2></div>
  <div class="col">
    <p>Each rule is backed by a mechanism, not a good intention. The task lifecycle is a small
    state machine, and the one rule that matters most &mdash; nobody approves their own work
    &mdash; is enforced at the transition into <code>done</code>.</p>
    <table>
      <tr><th>Rule</th><th>Mechanism</th></tr>
      <tr><td>No claiming a blocked task</td><td><code>blackboard.py claim</code> refuses any task whose <code>depends_on</code> aren&rsquo;t <code>done</code></td></tr>
      <tr><td>No editing a file someone else holds</td><td>TTL write-locks and a hook that blocks the edit before it lands</td></tr>
      <tr><td>No agent can freeze the swarm</td><td>Claims carry leases, locks carry TTLs; a crashed agent&rsquo;s work expires back to the pool</td></tr>
      <tr><td>No one approves their own work</td><td><code>--status done</code> is refused unless the task was reviewed and the actor differs from the producer of record</td></tr>
      <tr><td>No silent self-modification</td><td>The harness changes itself only through an audit loop with a human gate; git is the undo button</td></tr>
    </table>
  </div>
  <div class="figure figure--wide">
    <div class="canvas">{LIFECYCLE}</div>
    <div class="caption"><span class="label">Fig. 2</span><span class="desc">The task lifecycle.
    A worker claims, works, and hands off; a different agent gives the verdict. Stalled or
    rejected work returns to the pool automatically.</span></div>
  </div>
</section>

<section>
  <div class="sec-head"><h2><span class="sec-num">05</span>The evolution ledger</h2></div>
  <div class="col">
    <p>The harness rewrites its own natural-language spec through an audit loop: logs, then
    evidence-cited proposals, adversarial verification, a human gate, and a generation bump.
    <strong>{C['gen']} generations</strong> so far, with <strong>{C['accepted']} accepted
    mutations</strong> &mdash; and the audits have caught themselves, once rejecting a proposal
    for a wrong evidence count and once catching the coordinator&rsquo;s own arithmetic error.</p>
  </div>
  <div class="figure figure--wide">
    <div class="canvas">{EVOLOOP}</div>
    <div class="caption"><span class="label">Fig. 3</span><span class="desc">The evolution loop.
    Frictions become audit inputs; audits become generations. Every change is gated by a human
    and reversible through git.</span></div>
  </div>
  <aside class="callout callout--limits">
    <div class="head">Limits</div>
    <div class="body"><p>The newest decision was a rejection. Two external ideas were evaluated
    for generation 5 &mdash; a Git-for-agent-runs checkpointer and a self-correcting
    trace&rarr;fix&rarr;regression loop &mdash; and both were declined: the failure modes they
    solve have not occurred in this harness&rsquo;s own trajectories, so they were logged with
    falsifiable revisit triggers rather than adopted on theory. A well-argued reject beats an
    enthusiastic adopt.</p></div>
  </aside>
  <div class="ledger"><div class="ledger-wrap"><table>
    <tr><th>ID</th><th>Status</th><th>Target</th><th>Summary</th></tr>
    {LEDGER}
  </table></div></div>
</section>

<section>
  <div class="sec-head"><h2><span class="sec-num">06</span>The blackboard, as a dependency-DAG</h2></div>
  <div class="col">
    <p>Every unit of work is a task on a shared board. A dependency edge is declared only where
    one task literally consumes another&rsquo;s artifact. Below is the real graph. Choose a work
    stream from the dropdown. Left-to-right follows <code>depends_on</code> order, and hovering a
    node reveals its title, role, and who closed it.</p>
  </div>
  <div class="key">
    <span><i style="background:{INK}"></i>done</span>
    <span><i style="background:{INK_4}"></i>failed / probe</span>
    <span><i style="background:{OCHRE}"></i>open</span>
    <span><i style="background:{FOREST}"></i>in progress</span>
    <span><i style="background:{OXBLOOD}"></i>review</span>
  </div>
  <div class="figure">
    <div class="canvas">{DAG_HTML}</div>
    <div class="caption"><span class="label">Fig. 4</span><span class="desc">The blackboard task
    graph, {C['tasks']} tasks across {C['epics']} epics. Many <code>failed</code> tasks are
    intentional guardrail probes that verify the producer&nbsp;vs&nbsp;approver refusals actually
    fire.</span></div>
  </div>
</section>

<section>
  <div class="sec-head"><h2><span class="sec-num">07</span>Proof it works</h2></div>
  <div class="stats">
    <div class="stat"><b>{C['done']}</b><span>tasks, producer &ne; approver</span></div>
    <div class="stat"><b>2</b><span>real projects shipped</span></div>
    <div class="stat"><b>{C['gen']}</b><span>generations of self-audit</span></div>
    <div class="stat"><b>2</b><span>tournaments, byte-identical winners</span></div>
  </div>
  <div class="col">
    <p>The harness helped build itself, evolved itself across {C['gen']} generations under low
    supervision, and shipped two real projects under its own rules. <code>mdtoc</code> (a
    Markdown table-of-contents generator, Python) and <code>cronsplain</code> (a cron-expression
    explainer, zero-dependency Node.js) were each planned, built, and tested on the board &mdash;
    every task with producer&nbsp;&ne;&nbsp;approver, every verdict adversarially replayed, each
    winning implementation chosen by a tournament and promoted byte-for-byte.</p>
  </div>
  <div class="figure figure--wide">
    <div class="canvas">{TESTS_HTML}</div>
    <div class="caption"><span class="label">Fig. 5</span><span class="desc">Test suites for the
    two shipped projects. The full evidence trail, task files, verdicts, and audits ship in the
    repo; nothing here is claimed that the logs can&rsquo;t confirm.</span></div>
  </div>
</section>

</main>

<footer class="col">
  <p>Source, full spec, and evidence trail on
  <a href="https://github.com/MarioCasanovacf/serenissima-harness" target="_blank" rel="noopener">GitHub</a>. MIT &mdash;
  built to be forked, not PR&rsquo;d: drop it into your own repo and let it evolve under your
  goals. Reach me on LinkedIn, X, or Substack (Moneda 391).</p>
</footer>
</body>
</html>
"""

(HERE / "index.html").write_text(PAGE)
print("wrote index.html —", len(PAGE), "bytes;", C)
