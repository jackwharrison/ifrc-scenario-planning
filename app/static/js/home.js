/* Home page: sort the list of trees, and confirm before deleting one. */
(function sortTrees(){
  const table = document.getElementById("treeTable");
  if(!table) return;
  const body = table.tBodies[0], keySel = document.getElementById("sortKey"), dirBtn = document.getElementById("sortDir");
  const NUM = {events: true};
  let st = {key: "updated", desc: true};
  try { Object.assign(st, JSON.parse(localStorage.getItem("ptHomeSort") || "{}")); } catch(e) {}

  function apply(){
    const rows = [...body.rows], k = st.key;
    rows.sort((a, b) => {
      let x = a.dataset[k] || "", y = b.dataset[k] || "", c;
      if(NUM[k]) c = Number(x) - Number(y);
      else {
        // Empty values always last, whatever the direction
        if(!x !== !y) return x ? -1 : 1;
        c = x.localeCompare(y, undefined, {sensitivity: "base", numeric: true});
      }
      return st.desc ? -c : c;
    });
    rows.forEach(r => body.appendChild(r));
    table.querySelectorAll("th[aria-sort]").forEach(th => {
      const on = th.querySelector(".th-sort").dataset.key === k;
      th.setAttribute("aria-sort", on ? (st.desc ? "descending" : "ascending") : "none");
    });
    keySel.value = k;
    // Say the order in words on the phone button: A to Z, newest first, most first
    const words = k === "updated" ? ["Oldest first", "Newest first"] : k === "events" ? ["Fewest first", "Most first"] : ["A to Z", "Z to A"];
    dirBtn.textContent = (st.desc ? "↓ " : "↑ ") + words[st.desc ? 1 : 0];
    dirBtn.setAttribute("aria-label", "Order: " + words[st.desc ? 1 : 0] + ". Click to reverse.");
    try { localStorage.setItem("ptHomeSort", JSON.stringify(st)); } catch(e) {}
  }
  // Click a heading: sort by it; click it again to reverse. Text sorts A to Z first, numbers and dates newest first.
  table.querySelectorAll(".th-sort").forEach(b => b.addEventListener("click", () => {
    const k = b.dataset.key;
    if(st.key === k) st.desc = !st.desc; else st = {key: k, desc: k === "events" || k === "updated"};
    apply();
  }));
  keySel.addEventListener("change", () => { const k = keySel.value; st = {key: k, desc: k === "events" || k === "updated"}; apply(); });
  dirBtn.addEventListener("click", () => { st.desc = !st.desc; apply(); });
  apply();
})();

(function confirmDelete(){
  const dlg = document.getElementById("delDialog");
  document.querySelectorAll("form.del-form").forEach(f => f.addEventListener("submit", ev => {
    if(f.dataset.confirmed) return;
    ev.preventDefault();
    const name = f.dataset.country;
    if(!dlg || typeof dlg.showModal !== "function"){
      if(confirm(`Delete ${name}? This deletes the tree and every workbook uploaded to it. This can't be undone.`)){ f.dataset.confirmed = "1"; f.submit(); }
      return;
    }
    dlg.querySelectorAll("[data-name]").forEach(s => s.textContent = name);
    dlg.returnValue = "";
    dlg.onclose = () => { if(dlg.returnValue === "delete"){ f.dataset.confirmed = "1"; f.submit(); } else f.querySelector("button").focus(); };
    dlg.showModal();
  }));
})();
