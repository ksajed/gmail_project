/* HISTORY_TABLE_V1
   - Toggle lignes détail pour tableau historique (accessible)
*/
(function(){
  function initTable(table){
    var rows = table.querySelectorAll("tr.ht-row");
    rows.forEach(function(row){
      var btn = row.querySelector(".ht-expander");
      if(!btn) return;

      var controlsId = btn.getAttribute("aria-controls");
      if(!controlsId) return;
      var detail = document.getElementById(controlsId);
      if(!detail) return;

      function setOpen(open){
        btn.setAttribute("aria-expanded", open ? "true" : "false");
        row.classList.toggle("is-open", open);
        detail.hidden = !open;
      }

      // click sur bouton
      btn.addEventListener("click", function(e){
        e.preventDefault();
        var open = btn.getAttribute("aria-expanded") === "true";
        setOpen(!open);
      });

      // click sur ligne (sauf liens / boutons)
      row.addEventListener("click", function(e){
        var t = e.target;
        if(!t) return;
        if(t.closest("a,button,input,select,textarea,label")) return;
        var open = btn.getAttribute("aria-expanded") === "true";
        setOpen(!open);
      });

      // état initial: fermé
      setOpen(false);
    });
  }

  document.addEventListener("DOMContentLoaded", function(){
    document.querySelectorAll("table.ht-table").forEach(initTable);
  });
})();
