#!/usr/bin/env python3
"""Genera el artifact de perfil de gasto desde usage_report.py --json."""
import json, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / ".harness/logs/perfil_gasto_2026-08-15.html"

d = json.loads(subprocess.run(
    [sys.executable, ".harness/bin/usage_report.py", "--json"],
    cwd=ROOT, capture_output=True, text=True, check=True).stdout)

runs = []
for r in d["runs"]:
    sa, co = r["subagents"], r["coordinator"]
    fr = sum(m["raw"] for m in r["models"].values() if m["tier"] == "frontier")
    tot = sum(m["raw"] for m in r["models"].values())
    runs.append(dict(
        lbl=r["start"][5:16].replace("T", " "),
        agents=r["agents"], tasks=len(r["tasks"]),
        raw=sa["raw"] + co["raw"], out=sa["out"] + co["out"],
        billable=sa["cache_write"] + co["cache_write"] + sa["in"] + co["in"] + sa["out"] + co["out"],
        wall=r["wall_minutes"], conc=r["concurrency"]["mean"],
        serial=r["concurrency"]["serial_pct"], frontier=round(100 * fr / tot, 1)))

roles, models = {}, {}
for r in d["runs"]:
    for k, v in r["roles"].items():
        a = roles.setdefault(k, dict(agents=0, raw=0, out=0))
        a["agents"] += v["agents"]; a["raw"] += v["raw"]; a["out"] += v["out"]
    for k, v in r["models"].items():
        a = models.setdefault(k, dict(agents=0, raw=0, out=0, tier=v["tier"]))
        a["agents"] += v["agents"]; a["raw"] += v["raw"]; a["out"] += v["out"]

cache, ctx, tail, comp = d["cache"], d["context_payload"], d["cost_tail"], d["compaction"]
T_RAW = sum(r["raw"] for r in runs)
T_OUT = sum(r["out"] for r in runs)
T_BILL = sum(r["billable"] for r in runs)
T_AG = sum(r["agents"] for r in runs)


def sp(n):
    return f"{int(round(n)):,}".replace(",", " ")


def m(n, dec=1):
    return f"{n/1e6:.{dec}f} M"


def k(n):
    return f"{n/1e3:.0f} k"


# ---------- figura 1: raw vs facturable por corrida (barras agrupadas) ----------
def fig_raw_bill():
    W, rowh, x0, bw = 760, 34, 118, 566
    mx = max(r["raw"] for r in runs)
    H = 26 + rowh * len(runs)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" class="cv">']
    for i, r in enumerate(runs):
        y = 12 + i * rowh
        s.append(f'<text x="{x0-10}" y="{y+9}" class="ax r">{r["lbl"]}</text>')
        w1 = bw * r["raw"] / mx
        w2 = max(1.2, bw * r["billable"] / mx)
        s.append(f'<rect x="{x0}" y="{y}" width="{w1:.1f}" height="9" rx="4" fill="var(--s1)">'
                 f'<title>{r["lbl"]}: {sp(r["raw"])} tokens crudos</title></rect>')
        s.append(f'<rect x="{x0}" y="{y+13}" width="{w2:.1f}" height="9" rx="4" fill="var(--s2)">'
                 f'<title>{r["lbl"]}: {sp(r["billable"])} tokens no-cacheados</title></rect>')
        s.append(f'<text x="{x0+w1+8}" y="{y+8}" class="val">{m(r["raw"])}</text>')
        s.append(f'<text x="{x0+w2+8}" y="{y+21}" class="val" fill="var(--ink3)">'
                 f'{m(r["billable"],2)}</text>')
    s.append("</svg>")
    return "".join(s)


# ---------- figura 2: descomposicion de la entrada ----------
def fig_cache():
    W, H, x0, bw = 760, 128, 8, 744
    parts = [("lectura de cache", cache["read_pct"], "var(--s1)"),
             ("escritura de cache", cache["write_pct"], "var(--s2)"),
             ("entrada nueva", cache["uncached_pct"], "var(--s3)")]
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" class="cv">']
    x = x0
    for name, pct, col in parts:
        w = max(2.0, bw * pct / 100 - 2)
        s.append(f'<rect x="{x:.1f}" y="26" width="{w:.1f}" height="34" rx="4" fill="{col}">'
                 f'<title>{name}: {pct}%</title></rect>')
        x += bw * pct / 100
    s.append(f'<text x="{x0}" y="18" class="val">94.98% lectura de cache</text>')
    s.append(f'<text x="{x0+bw:.1f}" y="80" class="val end" fill="var(--ink3)">'
             f'{cache["write_pct"]}% escritura + {cache["uncached_pct"]}% entrada nueva</text>')
    s.append(f'<line x1="{x0}" y1="98" x2="{x0+bw:.1f}" y2="98" class="grid"/>')
    s.append(f'<text x="{x0}" y="118" class="ax">entrada total acumulada: {sp(cache["input_total"])} tokens</text>')
    s.append("</svg>")
    return "".join(s)


# ---------- figura 3: output por corrida ----------
def fig_out():
    W, rowh, x0, bw = 760, 26, 118, 430
    mx = max(r["out"] for r in runs)
    H = 20 + rowh * len(runs)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" class="cv">']
    for i, r in enumerate(runs):
        y = 10 + i * rowh
        w = bw * r["out"] / mx
        s.append(f'<text x="{x0-10}" y="{y+11}" class="ax r">{r["lbl"]}</text>')
        s.append(f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="14" rx="4" fill="var(--s2)">'
                 f'<title>{r["lbl"]}: {sp(r["out"])} tokens de salida en {r["agents"]} agentes</title></rect>')
        s.append(f'<text x="{x0+w+8}" y="{y+12}" class="val">{k(r["out"])}</text>')
        s.append(f'<text x="752" y="{y+12}" class="ax end sm">{r["agents"]} agts &middot; {r["tasks"]} tareas</text>')
    s.append("</svg>")
    return "".join(s)


# ---------- figura 4: concurrencia ----------
def fig_conc():
    W, H, pad, x0 = 760, 250, 40, 118
    plotw = 600
    lo, hi = 1.0, 2.0
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" class="cv">']
    rowh = (H - 60) / len(runs)
    for gv in [1.0, 1.25, 1.5, 1.75, 2.0]:
        gx = x0 + plotw * (gv - lo) / (hi - lo)
        s.append(f'<line x1="{gx:.1f}" y1="14" x2="{gx:.1f}" y2="{H-42:.1f}" class="grid dash"/>')
        s.append(f'<text x="{gx:.1f}" y="{H-26:.0f}" class="ax mid sm">{gv:.2f}x</text>')
    for i, r in enumerate(runs):
        y = 22 + i * rowh
        cx = x0 + plotw * (r["conc"] - lo) / (hi - lo)
        s.append(f'<text x="{x0-10}" y="{y+4}" class="ax r sm">{r["lbl"]}</text>')
        s.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{cx:.1f}" y2="{y:.1f}" '
                 f'stroke="var(--rule)" stroke-width="2"/>')
        s.append(f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="5" fill="var(--s4)" '
                 f'stroke="var(--panel)" stroke-width="2">'
                 f'<title>{r["lbl"]}: concurrencia media {r["conc"]}x, {r["serial"]}% del tiempo en serie</title></circle>')
        s.append(f'<text x="{x0+plotw+16}" y="{y+4}" class="val">{r["serial"]:.0f}% serial</text>')
    s.append(f'<text x="{x0}" y="{H-6}" class="ax sm">concurrencia media = agentes activos por minuto ocupado; '
             f'1.00x = un agente a la vez</text>')
    s.append("</svg>")
    return "".join(s)


# ---------- figura 5: roles ----------
def fig_roles():
    order = sorted(roles.items(), key=lambda kv: -kv[1]["raw"])
    W, rowh, x0, bw = 760, 44, 100, 420
    mxr = max(v["raw"] for v in roles.values())
    mxo = max(v["out"] for v in roles.values())
    H = 20 + rowh * len(order)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" class="cv">']
    for i, (name, v) in enumerate(order):
        y = 12 + i * rowh
        w1 = max(1.5, bw * v["raw"] / mxr)
        w2 = max(1.5, bw * v["out"] / mxo)
        s.append(f'<text x="{x0-10}" y="{y+10}" class="ax r">{name}</text>')
        s.append(f'<text x="{x0-10}" y="{y+24}" class="ax r sm">{v["agents"]} agentes</text>')
        s.append(f'<rect x="{x0}" y="{y}" width="{w1:.1f}" height="10" rx="4" fill="var(--s1)">'
                 f'<title>{name}: {sp(v["raw"])} tokens crudos</title></rect>')
        s.append(f'<rect x="{x0}" y="{y+14}" width="{w2:.1f}" height="10" rx="4" fill="var(--s2)">'
                 f'<title>{name}: {sp(v["out"])} tokens de salida</title></rect>')
        s.append(f'<text x="{x0+w1+8}" y="{y+9}" class="val">{m(v["raw"])}</text>')
        s.append(f'<text x="{x0+w2+8}" y="{y+23}" class="val" fill="var(--ink3)">{sp(v["out"])}</text>')
    s.append("</svg>")
    return "".join(s)


# ---------- figura 6: frontier share por corrida vs banda ----------
def fig_frontier():
    W, H, x0, plotw = 760, 300, 118, 560
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" class="cv">']
    rowh = (H - 56) / len(runs)
    ytop, ybot = 16, H - 44
    bx1 = x0 + plotw * 53 / 100
    bx2 = x0 + plotw * 65 / 100
    s.append(f'<rect x="{bx1:.1f}" y="{ytop}" width="{bx2-bx1:.1f}" height="{ybot-ytop:.1f}" '
             f'fill="var(--s3)" opacity="0.10"/>')
    s.append(f'<text x="{(bx1+bx2)/2:.1f}" y="{H-26}" class="ax mid sm">banda 53&ndash;65%</text>')
    for gv in [0, 25, 50, 75, 100]:
        gx = x0 + plotw * gv / 100
        s.append(f'<line x1="{gx:.1f}" y1="{ytop}" x2="{gx:.1f}" y2="{ybot:.1f}" class="grid dash"/>')
        s.append(f'<text x="{gx:.1f}" y="{H-8}" class="ax mid sm">{gv}%</text>')
    for i, r in enumerate(runs):
        y = ytop + 10 + i * rowh
        cx = x0 + plotw * r["frontier"] / 100
        inband = 53 <= r["frontier"] <= 65
        col = "var(--s3)" if inband else "var(--s5)"
        s.append(f'<text x="{x0-10}" y="{y+4}" class="ax r sm">{r["lbl"]}</text>')
        s.append(f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="5.5" fill="{col}" '
                 f'stroke="var(--panel)" stroke-width="2">'
                 f'<title>{r["lbl"]}: {r["frontier"]}% del raw en modelos frontera</title></circle>')
        anchor = "end" if r["frontier"] > 85 else "start"
        dx = -12 if anchor == "end" else 12
        s.append(f'<text x="{cx+dx:.1f}" y="{y+4}" class="val" text-anchor="{anchor}">{r["frontier"]:.0f}%</text>')
    s.append("</svg>")
    return "".join(s)


# ---------- figura 7: cola de costo ----------
def fig_tail():
    W, H, x0, bw = 760, 168, 74, 560
    pts = [("p50", tail["p50"]), ("p90", tail["p90"]), ("p95", tail["p95"]),
           ("max", ctx["max"] * 0 + tail["p95"])]
    pts = pts[:3]
    mx = tail["p95"]
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" class="cv">']
    for i, (lab, v) in enumerate(pts):
        y = 16 + i * 40
        w = bw * v / mx
        s.append(f'<text x="{x0-10}" y="{y+16}" class="ax r">{lab}</text>')
        s.append(f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="20" rx="4" fill="var(--s1)">'
                 f'<title>{lab}: {sp(v)} tokens crudos por agente</title></rect>')
        s.append(f'<text x="{x0+w+10}" y="{y+15}" class="val">{m(v,2)}</text>')
    s.append(f'<text x="{x0}" y="{H-8}" class="ax sm">el decil superior de agentes concentra '
             f'{tail["top_decile_share_pct"]}% del costo total</text>')
    s.append("</svg>")
    return "".join(s)


def table(headers, rows):
    h = "".join(f"<th>{c}</th>" for c in headers)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="tv"><details><summary>ver tabla</summary><div class="tw">'
            f'<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div></details></div>')


STYLE = (ROOT / ".harness/logs/audit_telemetry_2026-08-14.html").read_text(encoding="utf-8")
STYLE = STYLE[STYLE.index("<style>"):STYLE.index("</style>") + 8]

frontier_raw = sum(v["raw"] for v in models.values() if v["tier"] == "frontier")
frontier_pct = 100 * frontier_raw / sum(v["raw"] for v in models.values())
frontier_ag = sum(v["agents"] for v in models.values() if v["tier"] == "frontier")

html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Perfil de gasto del Universal Agent Harness &mdash; corte 15-08-2026</title>
{STYLE}
</head>
<body>
<div class="wrap">
<header>
  <span class="eyebrow">Perfil de gasto &nbsp;/&nbsp; corte 15-08-2026</span>
  <h1>Donde se va el consumo,<br>y por que el numero grande miente</h1>
  <p class="lede">Doce corridas reconstruidas desde los transcripts del runner. El harness sigue sin
  escribir un solo contador propio: cada cifra de este documento la deriva
  <code>usage_report.py</code> del mismo material que Claude Code genera por su cuenta.</p>
  <div class="meta">
    <span>{T_AG} agentes</span><span>{len(runs)} corridas</span>
    <span>{sum(r['tasks'] for r in runs)} tareas</span>
    <span>{sum(r['wall'] for r in runs)/60:.0f} horas de reloj</span>
    <span>corte 15-08-2026</span>
  </div>
</header>

<div class="tiles">
  <div class="tile"><span class="n">{m(T_RAW,0)}</span><span class="k">tokens crudos acumulados</span></div>
  <div class="tile"><span class="n">{cache['read_pct']}%</span><span class="k">de la entrada es re-lectura de cache</span></div>
  <div class="tile"><span class="n">{m(T_OUT,2)}</span><span class="k">tokens de salida &mdash; la generacion real</span></div>
  <div class="tile"><span class="n">{frontier_pct:.0f}%</span><span class="k">del raw en modelos frontera</span></div>
  <div class="tile"><span class="n">{tail['top_decile_share_pct']}%</span><span class="k">del costo vive en el decil superior de agentes</span></div>
</div>

<section>
<span class="eyebrow">01 &nbsp;/&nbsp; La cifra que no hay que usar</span>
<h2>{m(T_RAW,0)} de tokens crudos, y casi ninguno se factura.</h2>
<p class="a">El total crudo suma entrada nueva, escritura de cache, lectura de cache y salida.
<strong>El 94.98% de esa entrada es re-lectura de cache</strong>, que en la practica se cobra a una
fraccion del precio de entrada. Leer el numero crudo como costo infla el gasto por un factor cercano
a veinte. La barra naranja de abajo es lo unico que se genera o se escribe de nuevo en cada corrida.</p>

<figure>
<figcaption><span class="t">Tokens crudos contra tokens no-cacheados, por corrida</span>
<span class="d">Azul: total crudo. Naranja: entrada nueva + escritura de cache + salida, es decir todo
lo que no es re-lectura. Misma escala en ambas series.</span></figcaption>
{fig_raw_bill()}
<div class="lg"><span class="lgi"><i style="background:var(--s1)"></i>tokens crudos</span>
<span class="lgi"><i style="background:var(--s2)"></i>no-cacheado</span></div>
{table(["corrida","agentes","tareas","crudos","no-cacheado","salida","reloj"],
       [[r["lbl"], r["agents"], r["tasks"], sp(r["raw"]), sp(r["billable"]), sp(r["out"]),
         f'{r["wall"]:.0f} min'] for r in runs])}
</figure>

<figure>
<figcaption><span class="t">Composicion de la entrada acumulada</span>
<span class="d">Una sola barra al 100%. La entrada nueva &mdash; contenido que el modelo jamas habia
visto &mdash; es 0.018% del total.</span></figcaption>
{fig_cache()}
<div class="lg"><span class="lgi"><i style="background:var(--s1)"></i>lectura de cache {cache['read_pct']}%</span>
<span class="lgi"><i style="background:var(--s2)"></i>escritura de cache {cache['write_pct']}%</span>
<span class="lgi"><i style="background:var(--s3)"></i>entrada nueva {cache['uncached_pct']}%</span></div>
</figure>
</section>

<section>
<span class="eyebrow">02 &nbsp;/&nbsp; Generacion</span>
<h2>El orden por salida no es el orden por crudo.</h2>
<p class="a">La corrida 5 gasto 33 M crudos y produjo 102 k de salida; la corrida 3 gasto los mismos
33 M y produjo 30 k. <strong>El crudo mide cuanto contexto se arrastro, la salida mide cuanto se
penso.</strong> Las corridas del 14 de agosto son las mas productivas por token arrastrado: 29 y 22
agentes generando arriba de 220 k cada una.</p>

<figure>
<figcaption><span class="t">Tokens de salida por corrida</span>
<span class="d">Coordinador y subagentes sumados. La etiqueta derecha da el tamano del abanico.</span></figcaption>
{fig_out()}
</figure>
</section>

<section>
<span class="eyebrow">03 &nbsp;/&nbsp; Paralelismo</span>
<h2>El DAG dice paralelo. El reloj dice {min(r['serial'] for r in runs):.0f}&ndash;{max(r['serial'] for r in runs):.0f}% en serie.</h2>
<p class="a">La concurrencia media nunca llega a 2x. Con picos de hasta 8 agentes simultaneos, el
promedio ponderado por minuto ocupado se queda entre 1.11x y 1.81x, y la fraccion de tiempo con un
solo agente activo va del 54% al 89%. <strong>El harness paga latencia de topologia paralela y
cobra rendimiento casi secuencial.</strong> Las dos corridas con mas abanico &mdash; 48 y 29
agentes &mdash; son tambien las unicas arriba de 1.6x, lo que sugiere que el cuello no es el DAG
sino el tamano del lote que se despacha por vez.</p>

<figure>
<figcaption><span class="t">Concurrencia media por corrida</span>
<span class="d">Eje forzado de 1.00x a 2.00x, el rango real de variacion. La linea gris mide la
distancia contra ejecucion estrictamente secuencial.</span></figcaption>
{fig_conc()}
{table(["corrida","agentes","concurrencia media","% serial","reloj"],
       [[r["lbl"], r["agents"], f'{r["conc"]:.2f}x', f'{r["serial"]:.1f}%', f'{r["wall"]:.0f} min'] for r in runs])}
</figure>
</section>

<section>
<span class="eyebrow">04 &nbsp;/&nbsp; Roles</span>
<h2>Verificar cuesta poco contexto y mucha generacion.</h2>
<p class="a">El worker domina el arrastre de contexto: {sp(roles['worker']['raw'])} crudos en
{roles['worker']['agents']} agentes. Pero el verifier, con {roles['verifier']['agents']} agentes
&mdash; el rol mas numeroso del harness &mdash; produce {sp(roles['verifier']['out'])} tokens de
salida, <strong>60% mas generacion que el worker con menos contexto por agente</strong>. La
proporcion de {roles['verifier']['agents']} verifiers contra {roles['worker']['agents']} workers
tampoco es gratuita: es el precio del guardarrail de que ningun productor cierra su propia tarea.</p>

<figure>
<figcaption><span class="t">Contexto arrastrado contra generacion, por rol</span>
<span class="d">Cada serie normalizada a su propio maximo &mdash; las dos barras de una fila no son
comparables entre si, solo contra las de su color.</span></figcaption>
{fig_roles()}
<div class="lg"><span class="lgi"><i style="background:var(--s1)"></i>tokens crudos</span>
<span class="lgi"><i style="background:var(--s2)"></i>tokens de salida</span></div>
{table(["rol","agentes","crudos","% del crudo","salida"],
       [[nm, v["agents"], sp(v["raw"]), f'{100*v["raw"]/T_RAW:.1f}%', sp(v["out"])]
        for nm, v in sorted(roles.items(), key=lambda kv: -kv[1]["raw"])])}
</figure>
</section>

<section>
<span class="eyebrow">05 &nbsp;/&nbsp; Mezcla de modelos</span>
<h2>{frontier_pct:.1f}% frontera acumulado, contra una banda operativa de 53&ndash;65%.</h2>
<p class="a">Sonnet-5 atendio {models['claude-sonnet-5']['agents']} agentes y
{100*models['claude-sonnet-5']['raw']/T_RAW:.1f}% del crudo. Los modelos frontera juntos
&mdash; opus-5, fable-5 y un residuo de opus-4.8 &mdash; suman {frontier_ag} agentes y
{frontier_pct:.1f}%. <strong>El acumulado queda por debajo de la banda, pero el acumulado no es la
unidad de decision: la corrida si.</strong> Solo dos de doce corridas caen dentro de 53&ndash;65%.
El resto se reparte entre corridas casi enteramente baratas y corridas casi enteramente frontera.
La banda no se esta violando de forma sostenida, se esta oscilando alrededor de ella.</p>

<figure>
<figcaption><span class="t">Fraccion frontera por corrida</span>
<span class="d">Verde: dentro de la banda operativa. Rosa: fuera. El sombreado marca 53&ndash;65%.</span></figcaption>
{fig_frontier()}
<div class="lg"><span class="lgi"><i style="background:var(--s3)"></i>dentro de banda</span>
<span class="lgi"><i style="background:var(--s5)"></i>fuera de banda</span></div>
{table(["modelo","tier","agentes","crudos","% del crudo","salida"],
       [[nm, v["tier"], v["agents"], sp(v["raw"]), f'{100*v["raw"]/T_RAW:.1f}%', sp(v["out"])]
        for nm, v in sorted(models.items(), key=lambda kv: -kv[1]["raw"])])}
</figure>
</section>

<section>
<span class="eyebrow">06 &nbsp;/&nbsp; Cola y fugas</span>
<h2>Un agente de cada diez se lleva un tercio del gasto.</h2>
<p class="a">La distribucion de costo por agente es fuertemente asimetrica: mediana
{m(tail['p50'],1)}, p95 {m(tail['p95'],1)} &mdash; casi cuatro veces la mediana. El decil superior
concentra {tail['top_decile_share_pct']}% del total. El payload de contexto por agente lo explica:
mediana {sp(ctx['median'])} tokens, p90 {sp(ctx['p90'])}, maximo {sp(ctx['max'])}, contra
{sp(ctx['first_turn_median'])} en el primer turno. <strong>Lo que engorda no es el prompt inicial,
es la acumulacion.</strong></p>

<figure>
<figcaption><span class="t">Costo crudo por agente: percentiles</span>
<span class="d">Distribucion sobre los {T_AG} agentes de las doce corridas.</span></figcaption>
{fig_tail()}
</figure>

<div class="flag"><span class="h">Fuera de todo total de arriba</span>
Hay consumo que el runner ejecuta sin bloque de uso, asi que no aparece en ninguna cifra de este
documento: <b>{comp['auto_titles']} llamadas de auto-titulado</b> y
<b>{len(comp['events'])} compactaciones automaticas</b> &mdash;
{sp(comp['events'][0]['pre_tokens'])} &rarr; {sp(comp['events'][0]['post_tokens'])} tokens en
{comp['events'][0]['duration_ms']/1000:.0f} s el {comp['events'][0]['ts'][:10]}, y
{sp(comp['events'][1]['pre_tokens'])} &rarr; {sp(comp['events'][1]['post_tokens'])} tokens en
{comp['events'][1]['duration_ms']/1000:.0f} s el {comp['events'][1]['ts'][:10]}. Cada compactacion
es una llamada de sintesis sobre medio millon de tokens de contexto que nadie contabiliza.
</div>
</section>

<section>
<span class="eyebrow">07 &nbsp;/&nbsp; Que hacer con esto</span>
<h2>Tres palancas, en orden de retorno.</h2>
<ul>
<li><b>Emitir un <code>run_id</code>.</b> Hoy la corrida se infiere por hueco temporal de 45
minutos. Cualquier serie de tiempo de gasto que se construya sobre esa heuristica hereda su error.</li>
<li><b>Atacar el decil superior, no el promedio.</b> Un tercio del gasto vive en agentes cuyo
payload de contexto se acerca a los {sp(ctx['max'])} tokens. Podar el contexto que se hereda al
despachar rinde mas que cambiar de modelo.</li>
<li><b>Subir el tamano del lote antes que la profundidad del DAG.</b> Las unicas corridas por
encima de 1.6x de concurrencia son las de abanico grande. La topologia ya permite el paralelismo;
lo que falta es despachar mas por vez.</li>
</ul>
</section>

<footer>
Generado por <code>.harness/bin/usage_report.py --json</code> sobre los transcripts del runner,
corte 15-08-2026. Las corridas se agrupan por hueco temporal de 45 minutos porque el harness no
emite identificador de corrida. Ninguna cifra proviene de contadores escritos por el harness.
La auditoria de instrumentacion previa, con corte 14-08-2026, sigue vigente para las preguntas de
revisiones, fallas y plano de control.
</footer>
</div>
</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"escrito: {OUT}  ({len(html):,} bytes)")
