/* Harness console page. Design T-484 section 7.
   Reads the console's JSON API, listens to its event stream, and sends every write with
   the X-Console-Token the server put in index.html. Builds the DOM with textContent only:
   no data is ever parsed as HTML. */
(function () {
  "use strict";

  var TOKEN = (document.querySelector('meta[name="console-token"]') || {}).content || "";
  var S = {
    lang: "es", dict: { es: {}, en: {} }, tab: "live", epic: null,
    board: null, activity: null, operator: null, society: null, flows: [], runs: [],
    events: [], waves: null, flow: null, flowName: null, runId: null, run: null,
    confirm: null, gitPreview: { commit: null, push: null }
  };

  // ------------------------------------------------------------ helpers

  function t(key, vars) {
    var s = (S.dict[S.lang] || {})[key];
    if (s == null) s = S.dict.en[key];
    if (s == null) s = key;
    if (vars) s = s.replace(/\{(\w+)\}/g, function (_, k) { return vars[k] == null ? "" : String(vars[k]); });
    return s;
  }

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === "text") n.textContent = v;
      else if (k === "cls") n.className = v;
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    });
    (kids || []).forEach(function (c) {
      if (c == null || c === false) return;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }

  function svg(tag, attrs, kids) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k]; else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }

  function $(id) { return document.getElementById(id); }
  function fill(node, kids) { node.textContent = ""; kids.forEach(function (k) { if (k) node.appendChild(k); }); }

  function get(path) {
    return fetch(path, { headers: { Accept: "application/json" }, cache: "no-store" }).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw j; return j; });
    });
  }

  function send(method, path, body) {
    return fetch(path, {
      method: method, cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Console-Token": TOKEN },
      body: JSON.stringify(body || {})
    }).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw j; return j.result; });
    });
  }

  function reason(err) {
    if (err && err.reason) return err.reason;
    if (err && err.message) return err.message;
    return String(err);
  }

  function parseTs(ts) { var d = ts ? new Date(ts) : null; return d && !isNaN(d) ? d : null; }

  function ago(ts) {
    var d = parseTs(ts);
    if (!d) return "";
    var s = Math.max(0, (Date.now() - d.getTime()) / 1000);
    if (s < 60) return t("time.seconds", { n: Math.round(s) });
    if (s < 3600) return t("time.minutes", { n: Math.round(s / 60) });
    if (s < 86400) return t("time.hours", { n: (s / 3600).toFixed(1) });
    return t("time.days", { n: Math.round(s / 86400) });
  }

  function clock(ts) {
    var d = parseTs(ts);
    if (!d) return "";
    return d.toLocaleTimeString(S.lang === "es" ? "es-MX" : "en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  }

  function minutesBetween(a, b) {
    var x = parseTs(a), y = parseTs(b) || new Date();
    return x ? Math.max(0, (y - x) / 60000) : null;
  }

  var STATUS_KEYS = {
    open: "st.open", claimed: "st.claimed", in_progress: "st.in_progress", review: "st.review",
    blocked: "st.blocked", done: "st.done", failed: "st.failed", running: "st.running",
    awaiting_operator: "st.awaiting_operator", approved: "st.approved", rejected: "st.rejected",
    finished: "st.finished", stopped: "st.stopped", enqueued: "st.enqueued", pending: "st.pending",
    ended: "st.ended", error: "st.error", timeout: "st.timeout", none: "st.none", ruled: "st.ruled"
  };
  function status(s) { return STATUS_KEYS[s] ? t(STATUS_KEYS[s]) : (s || ""); }
  function statusClass(s) {
    if (["done", "approved", "finished", "ended", "ruled"].indexOf(s) >= 0) return "badge ok";
    if (["failed", "rejected", "error", "timeout", "blocked", "stopped"].indexOf(s) >= 0) return "badge bad";
    if (["review", "running", "in_progress", "claimed", "awaiting_operator", "pending"].indexOf(s) >= 0) return "badge warn";
    return "badge";
  }

  var EVENT_KEYS = {
    task_claimed: "ev.task_claimed", task_updated: "ev.task_updated", task_handoff: "ev.task_handoff",
    task_added: "ev.task_added", lock_acquired: "ev.lock_acquired", lock_released: "ev.lock_released",
    lock_swept: "ev.lock_swept", tests_run: "ev.tests_run", flow_step_started: "ev.flow_step_started",
    flow_step_ended: "ev.flow_step_ended", flow_run_started: "ev.flow_run_started",
    flow_gate_ready: "ev.flow_gate_ready", flow_run_ended: "ev.flow_run_ended",
    flow_run_stopped: "ev.flow_run_stopped", flow_saved: "ev.flow_saved",
    decision_ruled: "ev.decision_ruled", operator_verdict: "ev.operator_verdict",
    wave_gate_decided: "ev.wave_gate_decided", operator_commit: "ev.operator_commit",
    operator_push: "ev.operator_push", goal_mode_start: "ev.goal_mode_start",
    goal_reached: "ev.goal_reached", claim_expired: "ev.claim_expired",
    session_holder_registered: "ev.session_holder_registered",
    session_holder_unregistered: "ev.session_holder_unregistered"
  };

  function describe(e) {
    if (!e) return "";
    var key = EVENT_KEYS[e.event];
    var vars = {
      task: e.task || e.id || e.run || "", path: e.path || "", status: status(e.status || e.state),
      role: e.role || "", to: e.to_role || "", decision: e.decision || "", choice: e.choice || "",
      outcome: e.outcome || "", flow: e.flow || "", n: e.file_count || 0,
      result: e.counts ? Object.keys(e.counts).map(function (k) { return e.counts[k] + " " + k; }).join(", ") : ""
    };
    return key ? t(key, vars) : e.event;
  }

  function actor(e) { return e.holder || e.from_agent || e.step_agent || e.agent || ""; }

  // ------------------------------------------------------------ tooltip

  var tip = null;
  function tipFor(node, build) {
    node.setAttribute("tabindex", "0");
    function show(ev) {
      var content = build();
      if (!content) return;
      fill(tip, content);
      tip.hidden = false;
      place(ev && ev.clientX != null ? ev : node.getBoundingClientRect());
    }
    function place(p) {
      var x = p.clientX != null ? p.clientX + 14 : p.left;
      var y = p.clientY != null ? p.clientY + 16 : p.bottom + 6;
      var w = tip.offsetWidth, h = tip.offsetHeight;
      if (x + w > window.innerWidth - 8) x = Math.max(8, window.innerWidth - w - 8);
      if (y + h > window.innerHeight - 8) y = Math.max(8, (p.clientY != null ? p.clientY : p.top) - h - 10);
      tip.style.left = x + "px";
      tip.style.top = y + "px";
    }
    node.addEventListener("mouseenter", show);
    node.addEventListener("mousemove", function (ev) { if (!tip.hidden) place(ev); });
    node.addEventListener("mouseleave", function () { tip.hidden = true; });
    node.addEventListener("focus", function () { show(null); });
    node.addEventListener("blur", function () { tip.hidden = true; });
  }

  function tipLines(title, rows) {
    var list = el("div", { cls: "tl" });
    rows.forEach(function (r) {
      if (r[1] == null || r[1] === "") return;
      list.appendChild(el("div", { cls: "tk", text: r[0] }));
      list.appendChild(el("div", { text: String(r[1]) }));
    });
    return [el("h4", { text: title }), list];
  }

  function agentInfo(name) {
    var list = (S.activity && S.activity.agents) || [];
    for (var i = 0; i < list.length; i++) if (list[i].name === name) return list[i];
    return null;
  }

  function taskById(id) {
    var list = (S.board && S.board.tasks) || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  }

  function agentTip(name) {
    var a = agentInfo(name);
    if (!a) return tipLines(name, [[t("tip.status"), t("tip.no_activity")]]);
    var task = a.task ? taskById(a.task) : null;
    var tr = a.tests_run;
    return tipLines(name, [
      [t("tip.task"), a.task ? a.task + (task ? "  " + task.title : "") : ""],
      [t("tip.role"), a.role],
      [t("tip.step"), a.step ? status(a.step) : ""],
      [t("tip.since"), a.since ? ago(a.since) : ""],
      [t("tip.last_action"), a.last_action ? describe(a.last_action) + "  (" + ago(a.last_action.ts) + ")" : ""],
      [t("tip.last_note"), a.last_note ? String(a.last_note.text || "").slice(0, 280) : ""],
      [t("tip.tests"), tr ? t("tip.tests_value", { n: tr.file_count, result: Object.keys(tr.counts || {}).map(function (k) { return tr.counts[k] + " " + k; }).join(", "), s: tr.seconds }) : ""],
      [t("tip.locks"), (a.locks || []).join(", ")]
    ]);
  }

  function taskTip(task) {
    var who = task.claimed_by || (task.handoff && task.handoff.from) || "";
    var a = who ? agentInfo(who) : null;
    return tipLines(task.id, [
      [t("tip.title"), task.title],
      [t("tip.status"), status(task.status)],
      [t("tip.who"), who],
      [t("tip.last_action"), a && a.last_action ? describe(a.last_action) + "  (" + ago(a.last_action.ts) + ")" : ""],
      [t("tip.depends"), (task.depends_on || []).join(", ")],
      [t("tip.last_note"), task.last_note ? String(task.last_note.text || "").slice(0, 280) :
        (task.handoff ? String(task.handoff.note || "").slice(0, 280) : "")]
    ]);
  }

  // ------------------------------------------------------------ i18n and tabs

  function applyLang() {
    document.documentElement.lang = S.lang;
    document.querySelectorAll("[data-i18n]").forEach(function (n) { n.textContent = t(n.getAttribute("data-i18n")); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (n) { n.setAttribute("placeholder", t(n.getAttribute("data-i18n-placeholder"))); });
    document.querySelectorAll(".lang-btn").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-lang") === S.lang ? "true" : "false"); });
    document.title = t("app.title");
    setLive(S.liveState || "off");
    renderAll();
  }

  function setLang(lang) {
    S.lang = lang === "en" ? "en" : "es";
    try { localStorage.setItem("harness-console-lang", S.lang); } catch (e) { /* storage may be off */ }
    applyLang();
  }

  function setTab(tab) {
    S.tab = tab;
    document.querySelectorAll(".tab").forEach(function (b) { b.setAttribute("aria-selected", b.getAttribute("data-tab") === tab ? "true" : "false"); });
    document.querySelectorAll("[data-panel]").forEach(function (p) { p.hidden = p.getAttribute("data-panel") !== tab; });
    try { localStorage.setItem("harness-console-tab", tab); } catch (e) { /* storage may be off */ }
    if (tab === "society" && !S.society) loadSociety();
  }

  function setLive(state) {
    S.liveState = state;
    var n = $("live");
    n.setAttribute("data-state", state);
    $("live-text").textContent = t(state === "on" ? "live.on" : "live.off");
  }

  // ------------------------------------------------------------ live tab

  function renderStrip() {
    var b = S.board || { counts: {} };
    var c = b.counts || {};
    var active = ((S.activity && S.activity.agents) || []).filter(function (a) { return a.task; }).length;
    var running = S.runs.filter(function (r) { return r.status === "running"; }).length;
    var waiting = ((S.operator && S.operator.review) || []).length + ((S.operator && S.operator.gates) || []).length +
      (((S.operator && S.operator.decisions) || []).filter(function (d) { return d.status === "open"; }).length);
    function stat(n, label) { return el("div", { cls: "stat" }, [el("span", { cls: "n", text: String(n) }), el("span", { cls: "l", text: label })]); }
    fill($("strip"), [
      stat(active, t("live.stat.agents")),
      stat((c.claimed || 0) + (c.in_progress || 0), t("live.stat.working")),
      stat(c.review || 0, t("live.stat.review")),
      stat(c.open || 0, t("live.stat.open")),
      stat(running, t("live.stat.runs")),
      stat(waiting, t("live.stat.waiting"))
    ]);
  }

  function renderLanes() {
    var list = ((S.activity && S.activity.agents) || []).filter(function (a) {
      if (a.task) return true;
      var d = a.last_action && parseTs(a.last_action.ts);
      return d && Date.now() - d.getTime() < 30 * 60000;
    });
    if (!list.length) return fill($("lanes"), [el("p", { cls: "empty", text: t("live.no_agents") })]);
    fill($("lanes"), list.map(function (a) {
      var task = a.task ? taskById(a.task) : null;
      var what = a.task ? a.task + (task ? "  " + task.title : "") : (a.last_action ? describe(a.last_action) : "");
      var lane = el("div", { cls: "lane" + (a.task ? "" : " idle") }, [
        el("span", { cls: "who", text: a.name }),
        el("span", { cls: "what", text: what }),
        el("span", { cls: "when", text: a.since ? ago(a.since) : (a.last_action ? ago(a.last_action.ts) : "") })
      ]);
      tipFor(lane, function () { return agentTip(a.name); });
      return lane;
    }));
  }

  function renderLiveRuns() {
    var live = S.runs.filter(function (r) { return r.status === "running" || r.status === "awaiting_operator"; });
    if (!live.length) return fill($("live-runs"), [el("p", { cls: "empty", text: t("live.no_runs") })]);
    fill($("live-runs"), live.map(function (r) {
      var m = minutesBetween(r.started, r.ended);
      return el("div", { cls: "lane" }, [
        el("span", { cls: "who", text: r.flow }),
        el("span", { cls: "what" }, [el("span", { cls: statusClass(r.status), text: status(r.status) }), " " + r.id]),
        el("span", { cls: "when", text: m == null ? "" : t("time.minutes", { n: m.toFixed(1) }) })
      ]);
    }));
  }

  function renderChart() {
    var w = S.waves || { waves: [] };
    var rows = w.waves || [];
    var target = w.target_minutes || 10;
    if (!rows.length) return fill($("chart"), [el("p", { cls: "empty", text: t("live.no_waves") })]);
    var max = Math.max(40, Math.ceil(Math.max.apply(null, rows.map(function (r) { return r.minutes || 0; })) / 10) * 10);
    var W = 560, labelW = 0, rowH = 34, top = 8, H = top + rows.length * rowH + 30;
    var x0 = 0, x1 = W - 44;
    function X(v) { return x0 + (v / max) * (x1 - x0); }
    var g = [];
    for (var v = 0; v <= max; v += 10) {
      g.push(svg("line", { x1: X(v), x2: X(v), y1: top, y2: H - 24, "class": "axis" }));
      g.push(svg("text", { x: X(v), y: H - 8, "text-anchor": v === 0 ? "start" : "middle", "class": "tick", text: v + " min" }));
    }
    rows.forEach(function (r, i) {
      var y = top + i * rowH;
      var label = S.lang === "es" ? (r.label_es || r.label) : r.label;
      var bar = svg("rect", { x: X(0), y: y + 15, width: Math.max(2, X(r.minutes) - X(0)), height: 12, rx: 2, "class": r.kind === "run" ? "bar-run" : "bar-measured" });
      var title = svg("title", { text: label + ": " + r.minutes + " min" });
      bar.appendChild(title);
      g.push(svg("text", { x: X(0), y: y + 11, text: label }));
      g.push(bar);
      g.push(svg("text", { x: X(r.minutes) + 6, y: y + 25, "class": "val", text: String(r.minutes) }));
    });
    g.push(svg("line", { x1: X(target), x2: X(target), y1: top, y2: H - 24, "class": "target" }));
    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": t("live.chart") }, g);
    var legend = el("div", { cls: "legend" }, [
      el("span", {}, [el("span", { cls: "sw sw-measured" }), t("chart.measured")]),
      el("span", {}, [el("span", { cls: "sw sw-run" }), t("chart.runs")]),
      el("span", {}, [el("span", { cls: "sw sw-target" }), t("chart.target", { n: target })])
    ]);
    fill($("chart"), [s, legend]);
    $("chart-source").textContent = t("chart.source");
  }

  function renderFeed() {
    var evs = S.events.slice(-40).reverse();
    if (!evs.length) return fill($("feed"), [el("li", { cls: "empty", text: t("live.no_events") })]);
    fill($("feed"), evs.map(function (e) {
      return el("li", {}, [
        el("span", { cls: "ts", text: clock(e.ts) }),
        el("span", { cls: "who", text: actor(e) }),
        el("span", { cls: "what", text: describe(e) })
      ]);
    }));
  }

  function epics() {
    var seen = {}, order = [];
    ((S.board && S.board.tasks) || []).slice().reverse().forEach(function (task) {
      var e = task.epic || "";
      if (!seen[e]) { seen[e] = true; order.push(e); }
    });
    return order;
  }

  function renderBoard() {
    var sel = $("epic");
    var list = epics();
    if (!S.board) return;
    if (S.epic == null) S.epic = list.length ? list[0] : "*";
    fill(sel, [el("option", { value: "*", text: t("live.epic.all_open") })].concat(list.map(function (e) {
      return el("option", { value: e, text: e || t("live.epic.none") });
    })));
    sel.value = S.epic;
    var tasks = ((S.board && S.board.tasks) || []).filter(function (task) {
      return S.epic === "*" ? task.status !== "done" : (task.epic || "") === S.epic;
    });
    var cols = [
      ["open", ["open"]], ["working", ["claimed", "in_progress"]], ["review", ["review"]],
      ["blocked", ["blocked", "failed"]], ["done", ["done"]]
    ];
    var names = { open: "board.open", working: "board.working", review: "board.review", blocked: "board.blocked", done: "board.done" };
    fill($("board"), cols.map(function (c) {
      var mine = tasks.filter(function (task) { return c[1].indexOf(task.status) >= 0; });
      if (c[0] === "done") mine = mine.slice(-10);
      return el("div", { cls: "col" }, [el("h3", { text: t(names[c[0]]) + "  " + mine.length })].concat(
        mine.length ? mine.map(function (task) {
          var card = el("div", { cls: "task", "data-status": task.status }, [
            el("div", { cls: "id", text: task.id + "  " + (task.role || "") }),
            el("div", { cls: "title", text: task.title || "" }),
            task.claimed_by ? el("div", { cls: "by", text: task.claimed_by }) : null
          ]);
          tipFor(card, function () { return taskTip(task); });
          return card;
        }) : [el("p", { cls: "empty", text: "-" })]));
    }));
  }

  function renderLive() {
    renderStrip(); renderLanes(); renderLiveRuns(); renderChart(); renderFeed(); renderBoard();
  }

  // ------------------------------------------------------------ operator tab

  function confirmRow(id, text, onYes) {
    if (S.confirm !== id) return null;
    return el("div", { cls: "confirm" }, [
      el("span", { text: text }),
      el("button", { type: "button", cls: "btn go small", text: t("common.confirm"), onclick: function () { S.confirm = null; onYes(); } }),
      el("button", { type: "button", cls: "btn small", text: t("common.cancel"), onclick: function () { S.confirm = null; renderOperator(); renderFlows(); } })
    ]);
  }

  function msgNode(id) { return el("div", { cls: "msg", id: id, role: "status" }); }
  function say(id, text, ok) { var n = $(id); if (n) { n.textContent = text; n.className = "msg " + (ok ? "ok" : "bad"); } }

  function renderDecisions() {
    var cards = ((S.operator && S.operator.decisions) || []);
    var open = cards.filter(function (d) { return d.status === "open"; });
    var ruled = cards.filter(function (d) { return d.status !== "open"; });
    var nodes = open.map(function (d) {
      var noteId = "note-" + d.id;
      var picked = S.pick && S.pick.id === d.id ? S.pick.choice : null;
      return el("div", { cls: "card" }, [
        el("div", { cls: "meta", text: d.id + "  " + (d.created || "") + (d.blocks && d.blocks.length ? "  " + t("op.blocks", { list: d.blocks.join(", ") }) : "") }),
        el("h3", { text: d.title }),
        el("div", { cls: "q", text: d.question }),
        el("dl", {}, [
          el("dt", { text: t("op.recommendation") }), el("dd", {}, [el("span", { cls: "badge ok", text: d.recommendation })]),
          el("dt", { text: t("op.if_yes") }), el("dd", { text: d.if_yes }),
          el("dt", { text: t("op.if_no") }), el("dd", { text: d.if_no })
        ]),
        el("textarea", { id: noteId, placeholder: t("op.note_optional"), rows: "2" }),
        el("div", { cls: "row" }, (d.options || []).map(function (o) {
          return el("button", { type: "button", cls: "btn" + (o === d.recommendation ? " go" : ""), text: o, onclick: function () {
            S.pick = { id: d.id, choice: o, note: $(noteId).value }; S.confirm = "rule-" + d.id; renderOperator();
          } });
        })),
        confirmRow("rule-" + d.id, t("op.confirm_rule", { choice: picked || "" }), function () {
          var p = S.pick;
          send("POST", "/api/decisions/" + d.id + "/rule", { choice: p.choice, note: p.note || "" })
            .then(function (r) { S.pick = null; say("msg-dec", t("op.ruled", { id: d.id, ruling: r.id }), true); loadOperator(); })
            .catch(function (e) { say("msg-dec", reason(e), false); renderOperator(); });
        })
      ]);
    });
    if (!open.length) nodes.push(el("p", { cls: "empty", text: t("op.no_decisions") }));
    if (ruled.length) nodes.push(el("details", {}, [el("summary", { text: t("op.ruled_list", { n: ruled.length }) })].concat(ruled.map(function (d) {
      return el("p", { text: d.id + "  " + d.title + "  -> " + ((d.ruling && d.ruling.choice) || "") });
    }))));
    nodes.push(msgNode("msg-dec"));
    fill($("op-decisions"), nodes);
  }

  function renderReview() {
    var list = (S.operator && S.operator.review) || [];
    var nodes = list.map(function (task) {
      var noteId = "vnote-" + task.id;
      var producer = task.handoff && task.handoff.from;
      function verdict(outcome) {
        send("POST", "/api/tasks/" + task.id + "/verdict", { outcome: outcome, note: $(noteId).value })
          .then(function () { say("msg-review", t("op.verdict_done", { id: task.id, outcome: status(outcome) }), true); loadOperator(); loadBoard(); })
          .catch(function (e) { say("msg-review", reason(e), false); });
      }
      var card = el("div", { cls: "card" }, [
        el("div", { cls: "meta", text: task.id + "  " + (task.epic || "") }),
        el("h3", { text: task.title }),
        el("div", { cls: "meta", text: t("op.producer", { name: producer || "?" }) }),
        task.handoff && task.handoff.note ? el("div", { cls: "note", text: task.handoff.note }) : null,
        el("textarea", { id: noteId, placeholder: t("op.verdict_note"), rows: "2" }),
        el("div", { cls: "row" }, [
          el("button", { type: "button", cls: "btn go", text: t("op.approve"), onclick: function () { verdict("done"); } }),
          el("button", { type: "button", cls: "btn stop", text: t("op.send_back"), onclick: function () { verdict("open"); } })
        ])
      ]);
      return card;
    });
    if (!list.length) nodes.push(el("p", { cls: "empty", text: t("op.no_review") }));
    nodes.push(msgNode("msg-review"));
    fill($("op-review"), nodes);
  }

  function renderGates() {
    var list = (S.operator && S.operator.gates) || [];
    var nodes = list.map(function (r) {
      var suite = (r.gate && r.gate.suite) || {};
      var noteId = "gnote-" + r.id;
      function decide(decision) {
        send("POST", "/api/runs/" + encodeURIComponent(r.id) + "/gate", { decision: decision, note: $(noteId).value })
          .then(function () { say("msg-gate", t("op.gate_done", { id: r.id, decision: status(decision === "approve" ? "approved" : "rejected") }), true); loadOperator(); loadRuns(); })
          .catch(function (e) { say("msg-gate", reason(e), false); });
      }
      return el("div", { cls: "card" }, [
        el("div", { cls: "meta", text: r.flow + "  " + r.id }),
        el("h3", { text: t("op.suite", { summary: suite.summary || "-" }) }),
        el("div", { cls: "chips" }, (r.tracks || []).map(function (tr) {
          return el("span", { cls: statusClass(tr.status === "done" ? "done" : (tr.status === "sent back" ? "review" : "failed")), text: tr.task + "  " + tr.status });
        })),
        el("textarea", { id: noteId, placeholder: t("op.gate_note"), rows: "2" }),
        el("div", { cls: "row" }, [
          el("button", { type: "button", cls: "btn go", text: t("op.gate_approve"), onclick: function () { decide("approve"); } }),
          el("button", { type: "button", cls: "btn stop", text: t("op.gate_reject"), onclick: function () { decide("reject"); } })
        ])
      ]);
    });
    if (!list.length) nodes.push(el("p", { cls: "empty", text: t("op.no_gates") }));
    nodes.push(msgNode("msg-gate"));
    fill($("op-gates"), nodes);
  }

  function copyButton(text) {
    return el("button", { type: "button", cls: "btn small", text: t("common.copy"), onclick: function (ev) {
      var b = ev.currentTarget;
      var done = function () { b.textContent = t("common.copied"); setTimeout(function () { b.textContent = t("common.copy"); }, 1500); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { selectNext(b); });
      else selectNext(b);
    } });
  }
  function selectNext(b) {
    var pre = b.parentNode.parentNode.querySelector("pre");
    if (!pre) return;
    var r = document.createRange(); r.selectNodeContents(pre);
    var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  }

  function renderSignatures() {
    var list = (S.operator && S.operator.signatures) || [];
    var nodes = list.map(function (s) {
      return el("div", { cls: "card" }, [
        el("h3", { text: s.what }),
        el("div", { cls: "meta", text: t("op.signature_note") })
      ].concat((s.commands || []).map(function (c, i) {
        return el("div", {}, [
          el("div", { cls: "row" }, [el("span", { cls: "meta", text: t("op.step_n", { n: i + 1 }) }), copyButton(c)]),
          el("pre", { cls: "note", text: c })
        ]);
      })));
    });
    if (!list.length) nodes.push(el("p", { cls: "empty", text: t("op.no_signatures") }));
    fill($("op-signatures"), nodes);
  }

  function renderClose(data) {
    if (!data) return fill($("op-close"), []);
    if (data.loading) return fill($("op-close"), [el("p", { cls: "empty", text: t("common.loading") })]);
    var r = data.report;
    if (!r) return fill($("op-close"), [el("p", { cls: "msg bad", text: data.problem || "?" })]);
    var forks = (r.forks && r.forks.parsed) || [];
    var rec = r.reconcile || {};
    var imp6 = r.imp6 || {};
    var bad = forks.length || rec.exit_code || (Array.isArray(imp6.acts_anomalous) ? imp6.acts_anomalous.length : imp6.acts_anomalous);
    fill($("op-close"), [el("div", { cls: "card" + (bad ? "" : " done") }, [
      el("dl", {}, [
        el("dt", { text: t("op.close.forks") }), el("dd", { text: String(forks.length) }),
        el("dt", { text: t("op.close.reconcile") }), el("dd", { text: rec.exit_code === 0 ? t("op.close.clean") : t("op.close.exit", { n: rec.exit_code }) }),
        el("dt", { text: t("op.close.imp6") }), el("dd", { text: t("op.close.imp6_value", { anomalous: Array.isArray(imp6.acts_anomalous) ? imp6.acts_anomalous.length : (imp6.acts_anomalous == null ? "-" : imp6.acts_anomalous), total: imp6.acts_total == null ? "-" : imp6.acts_total }) })
      ]),
      el("div", { cls: "meta", text: t("op.close.note") }),
      el("details", {}, [el("summary", { text: t("op.close.raw") }), el("pre", { cls: "note", text: JSON.stringify(r, null, 2) })])
    ])]);
  }

  function renderGit() {
    var o = S.operator || {};
    var p = o.pending || {};
    var commitMsg = $("git-msg") ? $("git-msg").value : "";
    var nodes = [
      el("div", { cls: "meta", text: t("git.summary", { branch: o.branch || "?", tracked: p.tracked || 0, untracked: p.untracked || 0 }) }),
      el("div", { cls: "stat-box" }, [el("pre", { text: p.stat || t("git.clean") })]),
      el("label", { cls: "meta", for: "git-msg", text: t("git.message") }),
      el("textarea", { id: "git-msg", rows: "4", placeholder: t("git.message_hint") }),
      el("div", { cls: "row" }, [
        el("button", { type: "button", cls: "btn", text: t("git.check_commit"), onclick: function () { gitCall("commit", true); } }),
        el("button", { type: "button", cls: "btn go", text: t("git.do_commit"), disabled: S.gitPreview.commit ? null : true, onclick: function () { S.confirm = "git-commit"; renderGit(); } }),
        el("button", { type: "button", cls: "btn", text: t("git.check_push"), onclick: function () { gitCall("push", true); } }),
        el("button", { type: "button", cls: "btn warn", text: t("git.do_push"), disabled: S.gitPreview.push ? null : true, onclick: function () { S.confirm = "git-push"; renderGit(); } })
      ]),
      confirmRow("git-commit", t("git.confirm_commit"), function () { gitCall("commit", false); }),
      confirmRow("git-push", t("git.confirm_push", { branch: o.branch || "?" }), function () { gitCall("push", false); }),
      el("p", { cls: "hint", text: t("git.rules") }),
      msgNode("msg-git")
    ];
    fill($("op-git"), nodes);
    $("git-msg").value = commitMsg;
  }

  function gitCall(kind, dry) {
    var body = { dry_run: dry };
    if (kind === "commit") body.message = $("git-msg").value;
    var keep = $("git-msg").value;
    send("POST", "/api/git/" + kind, body).then(function (r) {
      S.gitPreview[kind] = dry ? r : null;
      renderGit();
      $("git-msg").value = keep;
      say("msg-git", (dry ? t("git.preview_ok") : t("git.done", { what: kind })) + (r.stat ? "\n" + r.stat : ""), true);
      if (!dry) loadOperator();
    }).catch(function (e) {
      S.gitPreview[kind] = null;
      renderGit();
      $("git-msg").value = keep;
      say("msg-git", t("git.refused") + " " + reason(e), false);
    });
  }

  // Re-rendering on a live update must not eat what the operator is typing.
  function preserving(container, fn) {
    var keep = {}, active = document.activeElement, activeId = active && active.id, sel = null;
    container.querySelectorAll("textarea[id], input[id]").forEach(function (n) { keep[n.id] = n.value; });
    if (activeId && active.selectionStart != null) sel = [active.selectionStart, active.selectionEnd];
    fn();
    Object.keys(keep).forEach(function (id) { var n = $(id); if (n && keep[id]) n.value = keep[id]; });
    if (activeId && $(activeId) && container.contains($(activeId))) {
      $(activeId).focus();
      if (sel) try { $(activeId).setSelectionRange(sel[0], sel[1]); } catch (e) { /* not a text field */ }
    }
  }

  function renderOperator() {
    if (!S.operator) return;
    $("branch").textContent = S.operator.branch || "-";
    preserving($("panel-operator"), function () {
      renderDecisions(); renderReview(); renderGates(); renderSignatures(); renderClose(S.close); renderGit();
    });
  }

  // ------------------------------------------------------------ society tab

  function kv(rows) {
    var n = el("div", { cls: "kv" });
    rows.forEach(function (r) {
      if (r[1] == null || r[1] === "") return;
      n.appendChild(el("span", { cls: "k", text: r[0] }));
      n.appendChild(el("span", { text: String(r[1]) }));
    });
    return n;
  }

  function renderSociety() {
    var s = S.society;
    if (!s) return fill($("soc-names"), [el("p", { cls: "empty", text: t("common.loading") })]);
    var r = s.roster || {};
    var names = r.names || {};
    var cols = r.colegiados || {};
    var byCol = {};
    Object.keys(names).forEach(function (n) { var c = names[n].colegiado || "?"; (byCol[c] = byCol[c] || []).push(n); });
    var colNodes = Object.keys(cols).concat(Object.keys(byCol).filter(function (c) { return !cols[c]; })).map(function (c) {
      var members = byCol[c] || [];
      return el("details", {}, [
        el("summary", { text: c + "  (" + t("soc.members", { n: members.length }) + ")" }),
        cols[c] ? el("p", { cls: "meta", text: cols[c].incentive || "" }) : null
      ].concat(members.map(function (n) {
        var x = names[n];
        return el("details", {}, [el("summary", {}, [el("span", { cls: "mono", text: n }), x.revoked ? el("span", { cls: "badge bad", text: t("soc.revoked") }) : null]),
          kv([[t("soc.role"), x.role], [t("soc.epic"), x.epic], [t("soc.persona"), x.persona], [t("soc.issued_by"), x.issued_by], [t("soc.issued_at"), x.issued_at]])]);
      })));
    });
    var plazas = r.plazas || {};
    var plazaNodes = Object.keys(plazas).map(function (ep) {
      return el("details", {}, [el("summary", { text: t("soc.plazas_for", { epic: ep }) }),
        kv(Object.keys(plazas[ep]).map(function (seat) { return [seat, String(plazas[ep][seat].count)]; }))]);
    });
    fill($("soc-names"), colNodes.concat(plazaNodes).concat(colNodes.length ? [] : [el("p", { cls: "empty", text: t("soc.none") })]));

    fill($("soc-warrants"), (s.warrants || []).map(function (w) {
      return el("details", {}, [el("summary", {}, [w.id + "  ", el("span", { cls: w.signature_file ? "badge ok" : "badge warn", text: w.signature_file ? t("soc.signed_file") : t("soc.unsigned") })]),
        kv([[t("soc.epic"), w.epic], [t("soc.issued_at"), w.issued_at]])]);
    }).concat((s.warrants || []).length ? [] : [el("p", { cls: "empty", text: t("soc.none") })]));

    var forks = s.forks || [];
    fill($("soc-acts"), [el("p", { cls: "meta", text: t("soc.forks", { n: forks.length }) })].concat((s.acts || []).map(function (a) {
      return el("details", {}, [el("summary", { text: a.name + "  (" + t("soc.acts_n", { n: a.count }) + ")" }),
        kv([[t("soc.kinds"), Object.keys(a.kinds || {}).map(function (k) { return k + " " + a.kinds[k]; }).join(", ")],
          [t("soc.last"), (a.last_kind || "") + "  " + (a.last_ts || "")],
          [t("soc.contracts"), String(a.contracts)], [t("soc.retractions"), String(a.retractions)]])]);
    })).concat((s.acts || []).length ? [] : [el("p", { cls: "empty", text: t("soc.none") })]));

    fill($("soc-cases"), (s.cases || []).map(function (c) {
      return el("details", {}, [el("summary", {}, [c.id + "  ", el("span", { cls: statusClass(c.status === "disposed" ? "done" : "review"), text: c.status || "" }), "  " + String(c.question || "").slice(0, 90)]),
        c.in_words ? el("pre", { cls: "note", text: c.in_words }) : kv([[t("soc.question"), c.question], [t("soc.task"), c.task]])]);
    }).concat((s.cases || []).length ? [] : [el("p", { cls: "empty", text: t("soc.none") })]));
    renderPrecedents();
    if ((s.problems || []).length) $("soc-names").appendChild(el("p", { cls: "msg bad", text: s.problems.join("\n") }));
  }

  function renderPrecedents() {
    var s = S.society;
    if (!s) return;
    var q = ($("prec-filter").value || "").toLowerCase();
    var list = (s.precedents || []).filter(function (p) {
      return !q || (p.id + " " + (p.title || "") + " " + (p.subject || "")).toLowerCase().indexOf(q) >= 0;
    });
    fill($("soc-precedents"), [el("p", { cls: "meta", text: t("soc.precedents_n", { n: list.length, total: (s.precedents || []).length }) })].concat(list.slice(0, 200).map(function (p) {
      return el("details", {}, [el("summary", {}, [el("span", { cls: "mono", text: p.id }), "  " + (p.title || "")]),
        kv([[t("soc.tier"), p.authority_tier], [t("soc.status"), p.status], [t("soc.force"), p.force], [t("soc.subject"), p.subject], [t("soc.confirmation"), p.confirmation_status]])]);
    })));
  }

  // ------------------------------------------------------------ flows tab

  var BLANK_TRACK = { task: "", verify_task: "", producer: "", verifier: "", title: "", brief: "" };

  function blankRecipe() {
    return { name: "", description: "", tests: "changed", gate: true,
      defaults: { model: "sonnet", effort: "high", rounds: 2 }, tracks: [Object.assign({}, BLANK_TRACK)] };
  }

  function renderFlowList() {
    fill($("flow-list"), S.flows.length ? S.flows.map(function (f) {
      return el("button", { type: "button", cls: "flow-item", "aria-current": S.flowName === f.name ? "true" : "false", onclick: function () { openFlow(f.name); } }, [
        el("span", { text: f.name + "  " }), el("span", { cls: f.valid ? "badge ok" : "badge bad", text: f.valid ? t("flows.valid") : t("flows.invalid") }),
        el("span", { cls: "d", text: f.description || "" })
      ]);
    }) : [el("p", { cls: "empty", text: t("flows.none") })]);
  }

  function field(label, input) { return el("label", {}, [el("span", { text: label }), input]); }
  function input(name, value, extra) { return el("input", Object.assign({ name: name, value: value == null ? "" : String(value) }, extra || {})); }
  function select(name, value, options) {
    var s = el("select", { name: name }, options.map(function (o) { return el("option", { value: o[0], text: o[1] }); }));
    s.value = value == null ? "" : String(value);
    return s;
  }

  function renderFlowForm() {
    var r = S.flow;
    var form = $("flow-form");
    if (!r) { fill(form, [el("p", { cls: "empty", text: t("flows.pick") })]); return; }
    var d = r.defaults || {};
    var models = [["", t("flows.inherit")], ["sonnet", "sonnet"], ["opus", "opus"], ["haiku", "haiku"]];
    var efforts = [["", t("flows.inherit")], ["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "xhigh"], ["max", "max"]];
    var rounds = [["", t("flows.inherit")], ["1", "1"], ["2", "2"], ["3", "3"]];
    var kids = [
      el("div", { cls: "fields" }, [
        field(t("form.name"), input("name", r.name, { required: true, pattern: "[a-z0-9][a-z0-9-]{0,63}", readonly: S.flowName ? true : null })),
        field(t("form.tests"), select("tests", r.tests || "changed", [["changed", t("form.tests.changed")], ["named", t("form.tests.named")]])),
        field(t("form.model"), select("d_model", d.model || "", models.slice(1))),
        field(t("form.effort"), select("d_effort", d.effort || "", efforts.slice(1))),
        field(t("form.rounds"), select("d_rounds", d.rounds || "", rounds.slice(1))),
        field(t("form.timeout"), input("d_timeout", d.timeout || "", { type: "number", min: "60", max: "7200", step: "60", placeholder: "1800" }))
      ]),
      field(t("form.description"), input("description", r.description)),
      el("label", { cls: "check" }, [el("input", { type: "checkbox", name: "gate", checked: r.gate !== false ? true : null }), el("span", { text: t("form.gate") })]),
      d.permissions ? el("p", { cls: "hint", text: t("form.permissions", { flags: d.permissions.join(" ") }) }) : el("p", { cls: "hint", text: t("form.permissions_default") })
    ];
    (r.tracks || []).forEach(function (tr, i) {
      kids.push(el("div", { cls: "track", "data-track": String(i) }, [
        el("div", { cls: "track-head" }, [el("h3", { text: t("form.track", { n: i + 1 }) }),
          el("button", { type: "button", cls: "btn small stop", text: t("form.remove_track"), onclick: function () { readForm(); S.flow.tracks.splice(i, 1); renderFlowForm(); } })]),
        el("div", { cls: "fields" }, [
          field(t("form.task"), input("task", tr.task, { placeholder: "T-123" })),
          field(t("form.verify_task"), input("verify_task", tr.verify_task, { placeholder: "T-124" })),
          field(t("form.producer"), input("producer", tr.producer, { placeholder: "worker-x" })),
          field(t("form.verifier"), input("verifier", tr.verifier, { placeholder: "verifier-x" })),
          field(t("form.rounds"), select("rounds", tr.rounds || "", rounds)),
          field(t("form.model"), select("model", tr.model || "", models))
        ]),
        field(t("form.title"), input("title", tr.title, { placeholder: t("form.title_hint") })),
        el("label", { cls: "check" }, [el("input", { type: "checkbox", name: "verify_first", checked: tr.verify_first ? true : null }), el("span", { text: t("form.verify_first") })]),
        field(t("form.brief"), el("textarea", { name: "brief", rows: "4", text: tr.brief || "" }))
      ]));
    });
    kids.push(el("div", { cls: "row" }, [
      el("button", { type: "button", cls: "btn", text: t("form.add_track"), onclick: function () { readForm(); S.flow.tracks.push(Object.assign({}, BLANK_TRACK)); renderFlowForm(); } }),
      el("button", { type: "button", cls: "btn", text: t("form.validate"), onclick: validateFlow }),
      el("button", { type: "button", cls: "btn go", text: t("form.save"), onclick: saveFlow })
    ]));
    if (S.flowName) {
      kids.push(el("div", { cls: "row" }, [
        el("button", { type: "button", cls: "btn go", text: t("form.launch_agents"), onclick: function () { S.confirm = "launch-agents"; renderFlowForm(); } }),
        el("button", { type: "button", cls: "btn", text: t("form.launch_enqueue"), onclick: function () { S.confirm = "launch-enqueue"; renderFlowForm(); } })
      ]));
      kids.push(confirmRow("launch-agents", t("form.confirm_agents", { n: (r.tracks || []).length * 2 }), function () { launch("agents"); }));
      kids.push(confirmRow("launch-enqueue", t("form.confirm_enqueue"), function () { launch("enqueue"); }));
    }
    fill(form, kids);
  }

  function readForm() {
    var f = $("flow-form");
    if (!S.flow || !f.elements.namedItem("name")) return S.flow;
    var r = S.flow;
    function v(n, scope) { var x = (scope || f).querySelector('[name="' + n + '"]'); return x ? (x.type === "checkbox" ? x.checked : x.value.trim()) : null; }
    r.name = v("name");
    r.description = v("description");
    r.tests = v("tests");
    r.gate = v("gate");
    var d = Object.assign({}, r.defaults || {});
    d.model = v("d_model") || undefined;
    d.effort = v("d_effort") || undefined;
    d.rounds = v("d_rounds") ? parseInt(v("d_rounds"), 10) : undefined;
    d.timeout = v("d_timeout") ? parseInt(v("d_timeout"), 10) : undefined;
    Object.keys(d).forEach(function (k) { if (d[k] === undefined) delete d[k]; });
    r.defaults = d;
    r.tracks = Array.prototype.map.call(f.querySelectorAll("[data-track]"), function (node, i) {
      var old = (r.tracks || [])[i] || {};
      var tr = Object.assign({}, old);
      ["task", "verify_task", "producer", "verifier", "title", "brief"].forEach(function (k) { tr[k] = v(k, node); });
      tr.verify_first = v("verify_first", node);
      var rounds = v("rounds", node), model = v("model", node);
      if (rounds) tr.rounds = parseInt(rounds, 10); else delete tr.rounds;
      if (model) tr.model = model; else delete tr.model;
      if (!tr.title) delete tr.title;
      if (!tr.verify_first) delete tr.verify_first;
      return tr;
    });
    return r;
  }

  function flowMsg(text, ok) { var n = $("flow-msg"); n.textContent = text; n.className = "msg " + (ok ? "ok" : "bad"); }

  function validateFlow() {
    var r = readForm();
    if (!r.name) return flowMsg(t("flows.need_name"), false);
    send("POST", "/api/flows/" + encodeURIComponent(r.name) + "/validate", { recipe: r }).then(function (res) {
      if (res.problems.length) flowMsg(t("flows.problems") + "\n- " + res.problems.join("\n- "), false);
      else flowMsg(t("flows.valid_msg"), true);
    }).catch(function (e) { flowMsg(reason(e), false); });
  }

  function saveFlow() {
    var r = readForm();
    if (!r.name) return flowMsg(t("flows.need_name"), false);
    send("PUT", "/api/flows/" + encodeURIComponent(r.name), { recipe: r }).then(function () {
      S.flowName = r.name;
      flowMsg(t("flows.saved", { name: r.name }), true);
      loadFlows();
    }).catch(function (e) { flowMsg(t("flows.not_saved") + " " + reason(e), false); });
  }

  function launch(mode) {
    var name = S.flowName;
    send("POST", "/api/flows/" + encodeURIComponent(name) + "/launch", { mode: mode }).then(function (run) {
      flowMsg(t(mode === "agents" ? "flows.launched" : "flows.enqueued", { id: run.id, n: (run.created_tasks || []).length }), true);
      S.runId = run.id;
      renderFlowForm();
      loadRuns(); loadBoard();
    }).catch(function (e) { flowMsg(reason(e), false); renderFlowForm(); });
  }

  function openFlow(name) {
    get("/api/flows/" + encodeURIComponent(name)).then(function (res) {
      S.flowName = name;
      S.flow = res.recipe;
      S.dirty = false;
      $("flow-title").textContent = name;
      flowMsg(res.problems.length ? t("flows.problems") + "\n- " + res.problems.join("\n- ") : "", !res.problems.length);
      renderFlowList(); renderFlowForm();
    }).catch(function (e) { flowMsg(reason(e), false); });
  }

  function renderRuns() {
    fill($("run-list"), S.runs.length ? S.runs.map(function (r) {
      var m = minutesBetween(r.started, r.ended);
      return el("button", { type: "button", cls: "run-row", onclick: function () { S.runId = r.id; loadRun(); } }, [
        el("span", { cls: "mono", text: r.id }),
        el("span", {}, [el("span", { cls: statusClass(r.status), text: status(r.status) })]),
        el("span", { cls: "opt", text: t(r.mode === "agents" ? "flows.mode_agents" : "flows.mode_enqueue") }),
        el("span", { cls: "opt", text: (r.started || "").replace("T", " ").replace("Z", "") + (m != null ? "  " + t("time.minutes", { n: m.toFixed(1) }) : "") })
      ]);
    }) : [el("p", { cls: "empty", text: t("flows.no_runs") })]);
  }

  function renderRun() {
    var r = S.run;
    if (!r) return fill($("run-detail"), []);
    var nodes = [
      el("h3", { text: r.id }),
      el("div", { cls: "chips" }, [el("span", { cls: statusClass(r.status), text: status(r.status) })].concat((r.tracks || []).map(function (tr) {
        var chip = el("span", { cls: "badge", text: tr.task + " -> " + tr.verify_task + "  " + tr.status });
        tipFor(chip, function () { return agentTip(tr.producer).concat(agentTip(tr.verifier)); });
        return chip;
      }))),
      el("div", { cls: "steps" }, (r.steps || []).map(function (s) {
        var row = el("div", { cls: "step" }, [
          el("span", { text: t("flows.round", { n: s.round || "" }) }),
          el("span", { text: s.role || "" }),
          el("span", { cls: "mono", text: (s.agent || "") + "  " + (s.track || "") }),
          el("span", {}, [el("span", { cls: statusClass(s.status), text: status(s.status) })]),
          el("span", { text: s.seconds != null ? t("time.minutes", { n: (s.seconds / 60).toFixed(1) }) : ago(s.started) })
        ]);
        tipFor(row, function () {
          return tipLines(s.agent || "", [[t("tip.task"), s.track], [t("tip.role"), s.role], [t("tip.status"), status(s.status)],
            [t("tip.board_after"), s.verdict ? status(s.verdict) : ""], [t("tip.last_action"), s.last_action ? describe(s.last_action) + "  (" + ago(s.last_action.ts) + ")" : ""]]);
        });
        return row;
      }))
    ];
    if (r.gate && r.gate.suite) nodes.push(el("p", { cls: "meta", text: t("op.suite", { summary: r.gate.suite.summary || "-" }) }));
    if (r.status === "running") nodes.push(el("div", { cls: "row" }, [el("button", { type: "button", cls: "btn stop", text: t("flows.stop"), onclick: function () {
      send("POST", "/api/runs/" + encodeURIComponent(r.id) + "/stop", {}).then(loadRun).catch(function (e) { flowMsg(reason(e), false); });
    } })]));
    fill($("run-detail"), nodes);
  }

  function renderFlows() { renderFlowList(); renderFlowForm(); renderRuns(); renderRun(); }

  function renderAll() {
    renderLive();
    renderOperator();
    if (S.society) renderSociety();
    renderFlowList(); renderRuns(); renderRun();
    if (S.flow) { readForm(); renderFlowForm(); }
  }

  // ------------------------------------------------------------ loading and live updates

  function loadBoard() { return get("/api/board").then(function (b) { S.board = b; renderBoard(); renderStrip(); renderLanes(); }).catch(noop); }
  function loadActivity() { return get("/api/activity").then(function (a) { S.activity = a; renderLanes(); renderStrip(); }).catch(noop); }
  function loadOperator() { return get("/api/operator").then(function (o) { S.operator = o; renderOperator(); renderStrip(); }).catch(noop); }
  function loadRuns() { return get("/api/runs").then(function (r) { S.runs = r.runs || []; renderRuns(); renderLiveRuns(); renderStrip(); if (S.runId) loadRun(); }).catch(noop); }
  function loadRun() { if (!S.runId) return; get("/api/runs/" + encodeURIComponent(S.runId)).then(function (r) { S.run = r; renderRun(); }).catch(noop); }
  function loadFlows() { return get("/api/flows").then(function (f) { S.flows = f.flows || []; renderFlowList(); }).catch(noop); }
  function loadWaves() { return get("/api/charts/waves").then(function (w) { S.waves = w; renderChart(); }).catch(noop); }
  function loadEvents() { return get("/api/events").then(function (e) { S.events = e.events || []; renderFeed(); }).catch(noop); }
  function loadSociety() { return get("/api/society").then(function (s) { S.society = s; renderSociety(); }).catch(function (e) { fill($("soc-names"), [el("p", { cls: "msg bad", text: reason(e) })]); }); }
  function noop() { /* the next live update retries */ }

  var timers = {};
  function soon(key, fn) { clearTimeout(timers[key]); timers[key] = setTimeout(fn, 250); }

  function connect() {
    if (!window.EventSource) return;
    var es = new EventSource("/api/stream");
    es.addEventListener("open", function () { setLive("on"); });
    es.addEventListener("error", function () { setLive("off"); });
    es.addEventListener("events", function (m) {
      var data = JSON.parse(m.data);
      S.events = S.events.concat(data.events || []).slice(-300);
      renderFeed();
      soon("activity", loadActivity);
    });
    es.addEventListener("changed", function (m) {
      var what = JSON.parse(m.data).what || [];
      if (what.indexOf("board") >= 0) { soon("board", loadBoard); soon("operator", loadOperator); soon("activity", loadActivity); }
      if (what.indexOf("runs") >= 0) { soon("runs", loadRuns); soon("operator", loadOperator); soon("waves", loadWaves); soon("activity", loadActivity); }
      if (what.indexOf("decisions") >= 0) soon("operator", loadOperator);
      if (what.indexOf("flows") >= 0) soon("flows", loadFlows);
      if (what.indexOf("locks") >= 0) soon("activity", loadActivity);
    });
  }

  function init() {
    tip = $("tip");
    document.querySelectorAll(".lang-btn").forEach(function (b) { b.addEventListener("click", function () { setLang(b.getAttribute("data-lang")); }); });
    document.querySelectorAll(".tab").forEach(function (b) { b.addEventListener("click", function () { setTab(b.getAttribute("data-tab")); }); });
    $("epic").addEventListener("change", function (e) { S.epic = e.target.value; renderBoard(); });
    $("prec-filter").addEventListener("input", renderPrecedents);
    $("close-run").addEventListener("click", function () {
      S.close = { loading: true }; renderClose(S.close);
      get("/api/close-report").then(function (r) { S.close = r; renderClose(r); }).catch(function (e) { S.close = { problem: reason(e) }; renderClose(S.close); });
    });
    $("flow-new").addEventListener("click", function () {
      S.flowName = null; S.flow = blankRecipe(); $("flow-title").textContent = t("flows.new"); flowMsg("", true); renderFlowList(); renderFlowForm();
    });
    var lang = "es", tab = "live";
    try { lang = localStorage.getItem("harness-console-lang") || "es"; tab = localStorage.getItem("harness-console-tab") || "live"; } catch (e) { /* storage may be off */ }
    var q = /[?&]tab=(\w+)/.exec(location.search), l = /[?&]lang=(\w+)/.exec(location.search);
    if (q) tab = q[1];
    if (l) lang = l[1];
    S.lang = lang === "en" ? "en" : "es";
    Promise.all([get("/ui/i18n/es.json"), get("/ui/i18n/en.json")]).then(function (d) {
      S.dict.es = d[0]; S.dict.en = d[1];
    }).catch(noop).then(function () {
      applyLang();
      setTab(["live", "operator", "society", "flows"].indexOf(tab) >= 0 ? tab : "live");
      Promise.all([loadBoard(), loadActivity(), loadOperator(), loadRuns(), loadFlows(), loadWaves(), loadEvents()]).then(function () {
        if (S.flows.length && !S.flow) openFlow(S.flows[0].name);
      });
      if (location.hash !== "#still") connect();  // #still: no live stream, for screenshots
      setInterval(function () { if (S.tab === "live") { renderLanes(); renderLiveRuns(); } }, 10000);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
