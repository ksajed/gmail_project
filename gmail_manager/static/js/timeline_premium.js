// static/js/timeline_premium.js
(function () {
  function qsa(sel) { return Array.from(document.querySelectorAll(sel)); }

  function setAll(open) {
    qsa(".tlp__details").forEach(d => { d.open = open; });
  }

  document.addEventListener("click", function (ev) {
    const exp = ev.target.closest("[data-tlp-expand-all]");
    if (exp) { setAll(true); return; }

    const col = ev.target.closest("[data-tlp-collapse-all]");
    if (col) { setAll(false); return; }
  });
})();
