/* Start page: searchable country box, type of tree, and what you'll need. */
(function(){
  const S = window.START, READY = new Set(S.ready);
  const NAMES = S.countries.map(c => c.name), ALIASES = Object.fromEntries(S.countries.map(c => [c.name, c.aliases || ""]));
  const inp = $("#countryInput"), list = $("#countryList"), hidden = $("#countryValue");
  const norm = s => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[’']/g, "").toLowerCase();
  let items = [], active = -1;

  function search(q){
    const n = norm(q.trim());
    if(!n) return [...NAMES.filter(c => READY.has(c)), ...NAMES.filter(c => !READY.has(c))].slice(0, 8);
    const scored = [];
    NAMES.forEach(c => { const name = norm(c), al = norm(ALIASES[c]); let s = -1;
      if(name.startsWith(n)) s = 0; else if(name.split(/[\s-]+/).some(w => w.startsWith(n))) s = 1;
      else if(al.split(/[\s-]+/).some(w => w.startsWith(n))) s = 2; else if(name.includes(n)) s = 3;
      if(s >= 0) scored.push([s, c]); });
    return scored.sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1])).slice(0, 8).map(x => x[1]);
  }
  function open(){
    items = search(inp.value === hidden.value ? "" : inp.value); active = items.indexOf(hidden.value);
    list.innerHTML = items.length ? items.map((c, i) => `<li role="option" id="opt-${i}" data-c="${esc(c)}" aria-selected="${i === active}" class="${i === active ? "active" : ""}"><span>${esc(c)}</span>${READY.has(c) ? '<span class="tag auto">Ready</span>' : ""}</li>`).join("") : `<li class="none">No country matches “${esc(inp.value)}”</li>`;
    list.hidden = false; inp.setAttribute("aria-expanded", "true");
    if(active >= 0) inp.setAttribute("aria-activedescendant", "opt-" + active); else inp.removeAttribute("aria-activedescendant");
    list.querySelectorAll("li[data-c]").forEach(li => li.onmousedown = e => { e.preventDefault(); pick(li.dataset.c); });
  }
  function close(){ list.hidden = true; inp.setAttribute("aria-expanded", "false"); inp.removeAttribute("aria-activedescendant"); }
  function move(d){ if(list.hidden) open(); if(!items.length) return; active = (active + d + items.length) % items.length;
    list.querySelectorAll("li[data-c]").forEach((li, i) => { li.classList.toggle("active", i === active); li.setAttribute("aria-selected", i === active); });
    inp.setAttribute("aria-activedescendant", "opt-" + active); list.querySelector(".active")?.scrollIntoView({block:"nearest"}); }
  function pick(c){ hidden.value = c; inp.value = c; close(); update(); inp.select(); }

  inp.addEventListener("focus", () => { inp.select(); open(); });
  inp.addEventListener("mouseup", e => { if(inp.value === hidden.value){ e.preventDefault(); inp.select(); } if(list.hidden) open(); });
  inp.addEventListener("input", open);
  inp.addEventListener("keydown", e => {
    if(e.key === "ArrowDown"){ e.preventDefault(); move(1); }
    else if(e.key === "ArrowUp"){ e.preventDefault(); move(-1); }
    else if(e.key === "Enter"){ e.preventDefault(); if(items[active]) pick(items[active]); else if(items.length === 1) pick(items[0]); }
    else if(e.key === "Escape"){ inp.value = hidden.value; close(); }
  });
  inp.addEventListener("blur", () => setTimeout(() => { if(!list.hidden){ inp.value = hidden.value; close(); } }, 120));

  function update(){
    const c = hidden.value, type = document.querySelector('input[name="tree_type"]:checked').value;
    $("#countryStatus").innerHTML = !c ? "" : READY.has(c) ? `<span class="tag auto">Ready</span> Area list and template set up` : `<span class="tag man">Not set up</span> No area list or boundaries loaded yet`;
    document.querySelectorAll(".needs-card").forEach(el => el.classList.toggle("hidden", el.dataset.type !== type));
    const typeOk = type === "risk";
    let msg = "";
    if(!c) msg = "Choose a country.";
    else if(!READY.has(c)) msg = `${c} isn’t set up yet. Setting up a country means adding a file with its areas and P-codes to app/lists/areas (see the README).`;
    else if(!typeOk) msg = "Crisis analysis is not built yet. Choose Risk profile.";
    const ok = !msg;
    $("#startBtn").disabled = !ok;
    $("#blocker").textContent = msg; $("#blocker").classList.toggle("hidden", ok);
    const t = $("#templateLink");
    if(READY.has(c)){ t.href = S.templateBase.replace("__C__", encodeURIComponent(c)); t.removeAttribute("aria-disabled"); t.style.pointerEvents = ""; t.style.opacity = ""; }
    else { t.href = "#"; t.setAttribute("aria-disabled", "true"); t.style.pointerEvents = "none"; t.style.opacity = ".45"; }
  }
  document.querySelectorAll('input[name="tree_type"]').forEach(r => r.addEventListener("change", update));
  update();
})();
