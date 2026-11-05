/* Upload page: submit as soon as a file is chosen or dropped. */
(function(){
  const form = $("#uploadForm"), input = $("#fileInput"), drop = $("#drop");
  if(!form) return;
  input.addEventListener("change", () => { if(input.files.length){ drop.querySelector("h2").textContent = "Reading " + input.files[0].name; form.submit(); } });
  ["dragenter","dragover"].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.add("over"); }));
  ["dragleave","drop"].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", ev => { if(ev.dataTransfer.files.length){ input.files = ev.dataTransfer.files; input.dispatchEvent(new Event("change")); } });
})();
/* "Use the example" is a separate form: carry the typed name across. */
(function(){
  const sample = document.querySelector("form.sample"), name = document.getElementById("yourName");
  if(!sample || !name) return;
  sample.addEventListener("submit", () => { const h = document.createElement("input"); h.type = "hidden"; h.name = "your_name"; h.value = name.value; sample.appendChild(h); });
})();
