/* Review page: the tree with its editor panel, and the map view with slicers. Data comes from window.TREE. */
(function(){
  let T = window.TREE;
  const st = { view:"tree", sel:"shock:hz", editing:null, mType:"all", mSub:"all", mArea:null };
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
    host.innerHTML = `<div class="tree-grid"><div><div class="tree" id="tree"></div>
      <p class="reading">Read from the bottom up: context and shocks lead to impacts, impacts shape conditions, and conditions set priorities.</p></div>
      <aside class="editor" id="editor" aria-live="polite"></aside></div>`;
    drawTree(); drawEditor();
  }
  function drawTree(){
    let h = "";
    T.view.layers.forEach((L, li) => {
      h += `<section class="layer" style="--c:${L.color}" aria-label="${esc(L.name)}"><div class="layer-head"><h2>${esc(L.name)}</h2><p>${esc(L.hint)}</p></div>
        <div class="boxes" style="grid-template-columns:repeat(${L.boxes.length},minmax(0,1fr))">`;
      L.boxes.forEach(b => {
        const key = L.key + ":" + b.id, kept = b.lines.filter(x => !x.out).map(x => x.text).concat(b.mine.map(m => m.text));
        const prev = kept.length ? kept.map(t => t.replace(/\.$/, "")).join("; ") : (b.kind === "manual" ? "To be written" : "Nothing yet");
        const chips = (b.kind !== "manual" ? `<span class="chip auto">Automatic</span>` : "") + (b.kind !== "auto" ? `<span class="chip man">Needs you</span>` : "");
        h += `<button type="button" class="box" data-key="${key}" aria-pressed="${st.sel === key}"><span class="box-title">${esc(b.title)}</span>
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
    let h = `<div class="ed-head" style="--c:${L.color}"><p class="ed-layer">${esc(L.name)}</p><h2>${esc(b.title)}</h2>${b.note ? `<p class="ed-note">${esc(b.note)}</p>` : ""}</div><div class="ed-body">`;
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

  /* ---------- map (schematic tiles until real boundaries are added) ---------- */
  function evLine(e){
    const f = []; if(e.killed) f.push(`${fmt(e.killed)} killed`); if(e.affected) f.push(`${fmt(e.affected)} affected`); if(e.displaced) f.push(`${fmt(e.displaced)} displaced`); if(e.houses) f.push(`${fmt(e.houses)} houses damaged`);
    const others = split(e.areas).filter(o => o !== st.mArea && o !== "National");
    return `<li><span class="ev-y">${e.year}</span><span><b>${esc(e.sub)}</b>${st.mArea && others.length ? ` <span class="multi">also ${esc(others.join(", "))}</span>` : ""}${f.length ? `<br><span class="figs">${f.join(", ")}</span>` : ""}</span></li>`;
  }
  function drawMap(){
    const ev = T.events.filter(e => (st.mType === "all" || e.type === st.mType) && (st.mSub === "all" || e.sub === st.mSub));
    const types = countBy(T.events, e => e.type);
    const subs = st.mType === "all" ? [] : countBy(T.events.filter(e => e.type === st.mType), e => e.sub);
    const per = {}; T.tiles.forEach(t => per[t.name] = []);
    ev.forEach(e => split(e.areas).forEach(o => { if(per[o]) per[o].push(e); }));
    const nat = ev.filter(e => split(e.areas).includes("National")), none = ev.filter(e => !split(e.areas).length);
    const max = Math.max(1, ...Object.values(per).map(l => l.length));
    const shade = n => n ? Math.round(18 + (n / max) * 72) : 0;
    const label = st.mSub !== "all" ? st.mSub : st.mType !== "all" ? st.mType : "All events";
    const area = T.areaLabel, Area = area[0].toUpperCase() + area.slice(1);
    const chip = (k, v, l, n, cur) => `<button type="button" class="slice" data-${k}="${esc(v)}" aria-pressed="${cur === v}">${esc(l)}<span>${n}</span></button>`;
    const list = l => `<ul class="evlist">${[...l].sort((a, b) => b.year - a.year).map(evLine).join("")}</ul>`;
    host.innerHTML = `<div class="map-grid"><section class="card">
      <div class="card-head"><h2>Events by ${esc(area)}</h2><p>${esc(label)}: ${plural(ev.length, "event")}</p></div>
      <div class="card-body">
        <div class="slicer" role="group" aria-label="Hazard type">${chip("t", "all", "All events", T.events.length, st.mType)}${types.map(([t, l]) => chip("t", t, t, l.length, st.mType)).join("")}</div>
        ${subs.length ? `<div class="slicer sub" role="group" aria-label="Hazard sub-type">${chip("s", "all", "All " + st.mType.toLowerCase(), T.events.filter(e => e.type === st.mType).length, st.mSub)}${subs.map(([s, l]) => chip("s", s, s, l.length, st.mSub)).join("")}</div>` : ""}
        <div class="tiles" role="group" aria-label="${esc(Area)}s">${T.tiles.map(t => { const k = per[t.name].length, p = shade(k);
          return `<button type="button" class="tile ${p >= 58 ? "dark" : ""} ${st.mArea === t.name ? "sel" : ""}" style="grid-row:${t.tile[0] + 1};grid-column:${t.tile[1] + 1};--p:${p}%" data-a="${esc(t.name)}" aria-pressed="${st.mArea === t.name}"><span class="t-name">${esc(t.name)}${t.city ? " city" : ""}</span><span class="t-n">${k}</span></button>`; }).join("")}</div>
        <div class="legend"><span class="sw" style="--p:0%"></span>None<span class="sw" style="--p:25%"></span>Fewer<span class="sw" style="--p:90%"></span>More events</div>
        <p class="map-note">Schematic layout, not to scale. Real boundaries can replace it once P-codes and OCHA boundary files are added. Events covering several ${esc(area)}s count once in each, so the numbers add up to more than the total.</p>
      </div></section>
      <div class="side">
        <section class="card"><div class="card-head"><h2>${st.mArea ? esc(st.mArea) : esc(Area) + " details"}</h2><p>${st.mArea ? `${plural(per[st.mArea].length, "event")} (${esc(label)})` : `Click a ${esc(area)} on the map`}</p></div>
          <div class="card-body">${st.mArea ? (per[st.mArea].length ? list(per[st.mArea]) : `<p class="muted">Nothing recorded here for this filter.</p>`) : `<p class="muted">The list shows each event with its figures, newest first.</p>`}</div></section>
        <section class="card"><div class="card-head"><h2>Nationwide events</h2><p>${plural(nat.length, "event")} (${esc(label)}). Not shown on the map.</p></div>
          <div class="card-body">${nat.length ? list(nat) : `<p class="muted">None for this filter.</p>`}</div></section>
        ${none.length ? `<section class="card"><div class="card-head"><h2>No area recorded</h2><p>${plural(none.length, "event")}. Add an area in the workbook to map ${none.length === 1 ? "it" : "them"}.</p></div><div class="card-body">${list(none)}</div></section>` : ""}
      </div></div>`;
    host.querySelectorAll(".slice[data-t]").forEach(b => b.onclick = () => { st.mType = b.dataset.t; st.mSub = "all"; drawMap(); host.querySelector(`.slice[data-t="${CSS.escape(st.mType)}"]`)?.focus(); });
    host.querySelectorAll(".slice[data-s]").forEach(b => b.onclick = () => { st.mSub = b.dataset.s; drawMap(); host.querySelector(`.slice[data-s="${CSS.escape(st.mSub)}"]`)?.focus(); });
    host.querySelectorAll(".tile").forEach(b => b.onclick = () => { const a = b.dataset.a; st.mArea = st.mArea === a ? null : a; drawMap(); host.querySelector(`.tile[data-a="${CSS.escape(a)}"]`)?.focus(); });
  }

  document.querySelectorAll(".viewtoggle button").forEach(b => b.onclick = () => { st.view = b.dataset.v; render(); });
  render();
})();
