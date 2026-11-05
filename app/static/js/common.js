/* Shared helpers: toast messages, remembered help notes, JSON posts with the CSRF token. */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt = n => Number(n).toLocaleString("en-GB");
const plural = (n, a, b) => `${fmt(n)} ${n === 1 ? a : (b || a + "s")}`;
const split = s => String(s || "").split(";").map(x => x.trim()).filter(Boolean);
let toastTimer;
function toast(msg){ const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 3200); }
async function postJSON(url, body){
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json","X-CSRF-Token":document.querySelector('meta[name="csrf-token"]').content}, body:JSON.stringify(body)});
  if(!r.ok) throw new Error("Saving failed (" + r.status + ")");
  return r.json();
}
(function rememberHelp(){
  let closed = {};
  try { closed = JSON.parse(localStorage.getItem("ptHelpClosed") || "{}") || {}; } catch(e) {}
  document.querySelectorAll("details.help").forEach(d => {
    if(closed[d.dataset.help]) d.open = false;
    d.addEventListener("toggle", () => { closed[d.dataset.help] = !d.open; try { localStorage.setItem("ptHelpClosed", JSON.stringify(closed)); } catch(e) {} });
  });
})();

(function stepIntoView(){
  const cur = document.querySelector(".steps [aria-current]");
  if(cur && cur.scrollIntoView && window.matchMedia("(max-width:720px)").matches) cur.scrollIntoView({block:"nearest", inline:"center"});
})();
