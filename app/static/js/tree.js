/* Review page: the tree with its editor panel, and the by-area table with slicers. Data comes from window.TREE. */
(function(){
  let T = window.TREE;
  const st = { view:"tree", sel:"shock:hz", editing:null, mType:"all", mSub:"all", mArea:null, q:"", showAll:false };
  const lc = s => /^[A-Z][a-z]/.test(s) ? s[0].toLowerCase() + s.slice(1) : s;
  const layer = k => T.view.layers.find(l => l.key === k);
  const findBox = key => { const [lk, bid] = key.split(":"); const L = layer(lk); return { L, b: L.boxes.find(x => x.id === bid) }; };
  const host = $("#view4");

  function countBy(list, keyFn){ const m = new Map(); list.forEach(e => [].concat(keyFn(e)).forEach(k => { if(!k) return; if(!m.has(k)) m.set(k, []); m.get(k).push(e); })); return [...m.entries()].sort((a, b) => b[1].length - a[1].length); }

  async function act(body){
    try { T = await postJSON(T.editUrl, body); st.editing = null; render(); }
    catch(e){ toast("That change was not saved. Check your connection and try again."); }
  }

  /* ---------- tree ---------- */
  function render(){
    document.querySelectorAll(".viewtoggle button").forEach(b => b.setAttribute("aria-pressed", b.dataset.v === st.view));
    if(st.view === "map"){ drawMap(); return; }
    host.innerHTML = `<div id="todo" aria-live="polite"></div><div class="tree-grid"><div><div class="tree" id="tree"></div>
      <p class="reading">Read from the bottom up: context and shocks lead to impacts, impacts shape conditions, and conditions set priorities.</p></div>
      <aside class="editor" id="editor" aria-live="polite"></aside></div>`;
    drawTree(); drawEditor();
  }
  /* A box needs you when it has an analyst part (manual or mixed) and nothing has been added by hand yet. */
  const needsYou = b => b.kind !== "auto" && !b.mine.length;
  const PEN = `<svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true"><path d="M8.5 1.5l2 2-6.5 6.5H2v-2z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
  function drawTodo(){
    const todo = T.view.layers.flatMap(L => L.boxes.filter(needsYou).map(b => ({L, b})));
    const el = $("#todo");
    if(!todo.length){ el.innerHTML = `<p class="todo-done">Every box marked Needs you has your input. Check the wording, then continue to export.</p>`; return; }
    el.innerHTML = `<div class="todo-bar"><p><b>${plural(todo.length, "box", "boxes")} need${todo.length === 1 ? "s" : ""} you.</b> These parts can’t be counted from the workbook: write them from your own analysis and the National Society’s knowledge.</p>
      <div class="todo-list">${todo.map(({L, b}) => `<button type="button" class="todo-chip" data-key="${L.key}:${b.id}" style="--c:${L.color}">${PEN}${esc(b.title)}</button>`).join("")}</div></div>`;
    el.querySelectorAll(".todo-chip").forEach(c => c.onclick = () => {
      st.sel = c.dataset.key; st.editing = null; drawTree(); drawEditor();
      document.querySelector(`.box[data-key="${c.dataset.key}"]`)?.scrollIntoView({behavior:"smooth", block:"center"});
    });
  }
  function drawTree(){
    drawTodo();
    let h = "";
    T.view.layers.forEach((L, li) => {
      h += `<section class="layer" style="--c:${L.color}" aria-label="${esc(L.name)}"><div class="layer-head"><h2>${esc(L.name)}</h2><p>${esc(L.hint)}</p></div>
        <div class="boxes" style="grid-template-columns:repeat(${L.boxes.length},minmax(0,1fr))">`;
      L.boxes.forEach(b => {
        const key = L.key + ":" + b.id, kept = b.lines.filter(x => !x.out).map(x => x.text).concat(b.mine.map(m => m.text));
        const todo = needsYou(b);
        const prev = kept.length ? kept.map(t => t.replace(/\.$/, "")).join("; ") : (b.kind === "manual" ? "To be written by you" : "Nothing yet");
        const chips = (todo ? `<span class="chip man">${PEN}Needs you</span>` : b.kind !== "auto" ? `<span class="chip mine">✓ Your input added</span>` : "")
          + (b.kind !== "manual" ? `<span class="chip auto">Automatic</span>` : "");
        h += `<button type="button" class="box ${todo ? "todo" : ""}" data-key="${key}" aria-pressed="${st.sel === key}"><span class="box-title">${esc(b.title)}</span>
          <span class="box-preview ${kept.length ? "" : "none"}">${esc(prev)}</span><span class="box-meta">${chips}${kept.length ? `<span class="chip">${plural(kept.length, "line")}</span>` : ""}</span></button>`;
      });
      h += `</div></section>`;
      if(li < T.view.layers.length - 1) h += `<div class="arrow" aria-hidden="true"><svg width="16" height="20" viewBox="0 0 16 20"><path d="M8 19V3M3 8l5-5 5 5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>`;
    });
    $("#tree").innerHTML = h;
    document.querySelectorAll(".box").forEach(b => b.onclick = () => {
      st.sel = b.dataset.key; st.editing = null; drawTree(); drawEditor();
      if(matchMedia("(max-width:1050px)").matches) $("#editor").scrollIntoView({behavior:"smooth"});
    });
  }
  function seasonChart(){
    const wet = T.events.filter(e => e.type === "Hydrological" || e.sub === "Landslide"), m = Array(12).fill(0);
    wet.forEach(e => m[T.months.indexOf(e.start)]++);
    const mx = Math.max(1, ...m); let s = `<svg viewBox="0 0 300 120" role="img" aria-label="Floods, mudflows and landslides by start month">`;
    m.forEach((v, i) => { const x = 8 + i * 24, h = v / mx * 80; s += `<rect class="bar" x="${x}" y="${96 - h}" width="16" height="${h}" rx="2"/>${v ? `<text x="${x + 8}" y="${92 - h}" text-anchor="middle">${v}</text>` : ""}<text x="${x + 8}" y="113" text-anchor="middle">${T.months[i][0]}</text>`; });
    return `<div class="season">${s}<line class="base" x1="4" x2="296" y1="96.5" y2="96.5"/></svg></div>`;
  }
  function drawEditor(){
    const { L, b } = findBox(st.sel);
    let h = `<div class="ed-head" style="--c:${L.color}"><p class="ed-layer">${esc(L.name)}</p><h2>${esc(b.title)}</h2>${b.note ? `<p class="ed-note">${esc(b.note)}</p>` : ""}
      ${needsYou(b) ? `<p class="ed-needs">${PEN}Needs you: ${b.kind === "manual" ? "nothing can be counted for this box, so it is empty until you add a line below." : "the counts above are a start; add your analysis below."}</p>` : ""}</div><div class="ed-body">`;
    if(b.chart) h += `<h3>Floods, mudflows and landslides by start month</h3>${seasonChart()}`;
    if(b.kind !== "manual"){
      h += `<h3>Written from the workbook</h3>`;
      if(!b.lines.length) h += `<p class="empty">${b.needs_scores ? `No hazard scores High yet. <a class="act go" href="${T.scoresUrl}">Go to scoring</a>` : "Nothing to show. Check that the related columns are filled in."}</p>`;
      b.lines.forEach(x => {
        h += `<div class="bul ${x.out ? "out" : ""}">`;
        if(st.editing === x.id){
          h += `<label class="ed-note" for="edt">Wording</label><textarea id="edt">${esc(x.text)}</textarea>
            <div class="actions"><button class="act go" data-a="save" data-id="${x.id}">Save</button><button class="act" data-a="cancel">Cancel</button>${x.edited ? `<button class="act" data-a="reset" data-id="${x.id}">Back to generated text</button>` : ""}</div>
            ${x.edited ? `<p class="how">Generated text: ${esc(x.generated)}</p>` : ""}`;
        } else {
          h += `<p class="b-text">${esc(x.text)}</p><p class="how">How: ${esc(x.rule)}${x.edited ? " Wording edited." : ""}</p>
            <details><summary>Based on ${plural(x.rows.length, "row")}</summary><ul>${x.rows.map(r => `<li>Row ${r.row}: ${r.year}, ${esc(r.sub)}${r.areas ? `, ${esc(r.areas)}` : ""}${r.verified ? "" : " (not verified)"}</li>`).join("")}</ul></details>
            <div class="actions"><button class="act" data-a="edit" data-id="${x.id}">Edit wording</button><button class="act" data-a="toggle" data-id="${x.id}">${x.out ? "Include again" : "Leave out"}</button></div>`;
        }
        h += `</div>`;
      });
    }
    h += `<h3>${b.kind === "manual" ? "Written by you" : "Added by you"}</h3>`;
    if(b.mine.length) b.mine.forEach(m => { h += `<div class="bul"><p class="b-text">${esc(m.text)}</p>${m.by ? `<p class="how">Added by ${esc(m.by)}</p>` : ""}<div class="actions"><button class="act" data-a="remove" data-id="${m.id}">Remove</button></div></div>`; });
    else if(b.kind === "manual") h += `<p class="empty">Nothing here yet.</p>`;
    h += `<div style="margin-top:10px"><label class="ed-note" for="newLine">Add a line</label><textarea id="newLine" placeholder="One finding, with a source if you have one"></textarea><div class="actions"><button class="act go" data-a="add">Add line</button></div></div></div>`;
    $("#editor").innerHTML = h;
    $("#edt")?.focus();
    $("#editor").querySelectorAll("[data-a]").forEach(el => el.onclick = () => {
      const a = el.dataset.a, id = el.dataset.id;
      if(a === "edit"){ st.editing = id; drawEditor(); }
      else if(a === "cancel"){ st.editing = null; drawEditor(); }
      else if(a === "save"){ const v = $("#edt").value.trim(); if(v) act({action:"save", line:id, text:v}); }
      else if(a === "reset") act({action:"reset", line:id});
      else if(a === "toggle") act({action:"toggle", line:id});
      else if(a === "remove") act({action:"remove", box:b.id, id});
      else if(a === "add"){ const v = $("#newLine").value.trim(); if(!v){ $("#newLine").focus(); return; } act({action:"add", box:b.id, text:v}); }
    });
  }

  /* ---------- by-area table: works from the area names alone, for any country ---------- */
  const pluralWord = w => /[^aeiou]y$/i.test(w) ? w.slice(0, -1) + "ies" : /(s|sh|ch|x|z)$/i.test(w) ? w + "es" : w + "s";
  const FOLD_AT = 15, TOP_ROWS = 20;
  function evLine(e){
    const f = []; if(e.killed) f.push(`${fmt(e.killed)} killed`); if(e.affected) f.push(`${fmt(e.affected)} affected`); if(e.displaced) f.push(`${fmt(e.displaced)} displaced`); if(e.houses) f.push(`${fmt(e.houses)} houses damaged`);
    const others = split(e.areas).filter(o => o !== st.mArea && o !== "National");
    return `<li><span class="ev-y">${e.year}</span><span><b>${esc(e.sub)}</b>${st.mArea && others.length ? ` <span class="multi">also ${esc(others.join(", "))}</span>` : ""}${f.length ? `<br><span class="figs">${f.join(", ")}</span>` : ""}</span></li>`;
  }
  function drawMap(){
    const ev = T.events.filter(e => (st.mType === "all" || e.type === st.mType) && (st.mSub === "all" || e.sub === st.mSub));
    const types = countBy(T.events, e => e.type);
    const subs = st.mType === "all" ? [] : countBy(T.events.filter(e => e.type === st.mType), e => e.sub);
    const per = {}; T.areas.forEach(a => per[a] = []);
    ev.forEach(e => split(e.areas).forEach(o => { if(per[o]) per[o].push(e); }));
    const nat = ev.filter(e => split(e.areas).includes("National")), none = ev.filter(e => !split(e.areas).length);
    const colKey = st.mType === "all" ? (e => e.type) : (e => e.sub);
    const cols = countBy(Object.values(per).flat(), colKey).map(([c]) => c);
    const cnt = (a, c) => per[a].filter(e => colKey(e) === c).length;
    const cellMax = Math.max(1, ...T.areas.flatMap(a => cols.map(c => cnt(a, c))));
    const shade = n => n ? Math.round(15 + (n / cellMax) * 70) : 0;
    const label = st.mSub !== "all" ? st.mSub : st.mType !== "all" ? st.mType : "All events";
    const area = T.areaLabel, areas = pluralWord(area), Area = area[0].toUpperCase() + area.slice(1), aArea = (/^[aeiou]/i.test(area) ? "an " : "a ") + area;
    const long = T.areas.length > FOLD_AT, q = (st.q || "").trim().toLowerCase();
    const match = a => !q || a.toLowerCase().includes(q);
    const sorted = T.areas.map(a => ({a, l: per[a]})).sort((x, y) => y.l.length - x.l.length || x.a.localeCompare(y.a));
    const withEv = sorted.filter(r => r.l.length && match(r.a)), zero = sorted.filter(r => !r.l.length && match(r.a));
    let rows = long ? withEv : withEv.concat(zero);
    const hidden = long && !st.showAll && !q && rows.length > TOP_ROWS ? rows.length - TOP_ROWS : 0;
    if(hidden) rows = rows.slice(0, TOP_ROWS);
    const chip = (k, v, l, n, cur) => `<button type="button" class="slice" data-${k}="${esc(v)}" aria-pressed="${cur === v}">${esc(l)}<span>${n}</span></button>`;
    const list = l => `<ul class="evlist">${[...l].sort((a, b) => b.year - a.year).map(evLine).join("")}</ul>`;
    const row = r => `<tr class="orow ${st.mArea === r.a ? "sel" : ""}" data-a="${esc(r.a)}"><th scope="row"><button type="button" class="oname" data-a="${esc(r.a)}" aria-pressed="${st.mArea === r.a}">${esc(r.a)}${T.cities.includes(r.a) ? " city" : ""}</button></th>${cols.map(c => { const n = cnt(r.a, c), p = shade(n); return `<td class="c ${n ? "" : "z"} ${p >= 55 ? "dark" : ""}" style="--p:${p}%">${n || "–"}</td>`; }).join("")}<td class="num"><b>${r.l.length}</b></td><td class="num">${r.l.length ? Math.max(...r.l.map(e => e.year)) : "–"}</td></tr>`;
    const table = !T.areas.length ? `<p class="muted" style="margin-top:12px">No ${esc(areas)} recorded. List them in tab Lists of the workbook, or fill in the ${esc(area)} column in tab 3, and upload again.</p>`
      : `<div class="table-wrap otab-wrap"><table class="otab">
        <thead><tr><th>${esc(Area)}</th>${cols.map(c => `<th class="c">${esc(c)}</th>`).join("")}<th class="num">Total</th><th class="num">Latest</th></tr></thead>
        <tbody>${rows.map(row).join("") || `<tr><td colspan="${cols.length + 3}" class="muted">No ${esc(areas)} match “${esc(st.q)}” with events for this filter.</td></tr>`}</tbody></table></div>
        ${hidden ? `<p style="margin-top:8px"><button type="button" class="act" id="showAll">Show all ${withEv.length} ${esc(areas)} with events</button></p>` : ""}
        ${long && zero.length ? `<p class="map-note"><b>${plural(zero.length, area, areas)} with no recorded events${st.mType !== "all" ? " for this filter" : ""}:</b> ${zero.map(r => esc(r.a)).join(", ")}.</p>` : ""}`;
    host.innerHTML = `<div class="map-grid"><section class="card">
      <div class="card-head"><h2>Events by ${esc(area)}</h2><p>${esc(label)}: ${plural(ev.length, "event")}. ${st.mType === "all" ? "Columns are hazard types." : `Columns are ${esc(st.mType.toLowerCase())} sub-types.`}</p></div>
      <div class="card-body">
        <div class="slicer" role="group" aria-label="Hazard type">${chip("t", "all", "All events", T.events.length, st.mType)}${types.map(([t, l]) => chip("t", t, t, l.length, st.mType)).join("")}</div>
        ${subs.length ? `<div class="slicer sub" role="group" aria-label="Hazard sub-type">${chip("s", "all", "All " + st.mType.toLowerCase(), T.events.filter(e => e.type === st.mType).length, st.mSub)}${subs.map(([s, l]) => chip("s", s, s, l.length, st.mSub)).join("")}</div>` : ""}
        ${long ? `<div class="area-search"><label for="areaQ" class="sr-only">Find ${esc(aArea)}</label><input id="areaQ" type="search" placeholder="Find ${esc(aArea)}" value="${esc(st.q || "")}" autocomplete="off"></div>` : ""}
        ${table}
        <div class="legend" style="margin-top:10px"><span class="sw" style="--p:0%"></span>None<span class="sw" style="--p:30%"></span>Fewer<span class="sw" style="--p:85%"></span>More events</div>
        <p class="map-note">Sorted by total events. Click ${esc(aArea)} to see its events. Events covering several ${esc(areas)} count once in each, so the totals add up to more than the number of events.</p>
      </div></section>
      <div class="side">
        <section class="card"><div class="card-head"><h2>${st.mArea ? esc(st.mArea) : esc(Area) + " details"}</h2><p>${st.mArea ? `${plural(per[st.mArea].length, "event")} (${esc(label)})` : `Click ${esc(aArea)} in the table`}</p></div>
          <div class="card-body">${st.mArea ? (per[st.mArea].length ? list(per[st.mArea]) : `<p class="muted">Nothing recorded here for this filter.</p>`) : `<p class="muted">The list shows each event with its figures, newest first.</p>`}</div></section>
        <section class="card"><div class="card-head"><h2>Nationwide events</h2><p>${plural(nat.length, "event")} (${esc(label)}). Not counted per ${esc(area)}.</p></div>
          <div class="card-body">${nat.length ? list(nat) : `<p class="muted">None for this filter.</p>`}</div></section>
        ${none.length ? `<section class="card"><div class="card-head"><h2>No ${esc(area)} recorded</h2><p>${plural(none.length, "event")}. Add ${esc(aArea)} in the workbook to count ${none.length === 1 ? "it" : "them"} here.</p></div><div class="card-body">${list(none)}</div></section>` : ""}
      </div></div>`;
    host.querySelectorAll(".slice[data-t]").forEach(b => b.onclick = () => { st.mType = b.dataset.t; st.mSub = "all"; drawMap(); host.querySelector(`.slice[data-t="${CSS.escape(st.mType)}"]`)?.focus(); });
    host.querySelectorAll(".slice[data-s]").forEach(b => b.onclick = () => { st.mSub = b.dataset.s; drawMap(); host.querySelector(`.slice[data-s="${CSS.escape(st.mSub)}"]`)?.focus(); });
    host.querySelectorAll(".orow").forEach(r => r.onclick = () => { const a = r.dataset.a; st.mArea = st.mArea === a ? null : a; drawMap(); host.querySelector(`.oname[data-a="${CSS.escape(a)}"]`)?.focus(); });
    $("#showAll")?.addEventListener("click", () => { st.showAll = true; drawMap(); });
    const qi = $("#areaQ");
    if(qi) qi.addEventListener("input", () => { const pos = qi.selectionStart; st.q = qi.value; drawMap(); const n = $("#areaQ"); n.focus(); n.setSelectionRange(pos, pos); });
  }

  document.querySelectorAll(".viewtoggle button").forEach(b => b.onclick = () => { st.view = b.dataset.v; render(); });
  render();
})();
