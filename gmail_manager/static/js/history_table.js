/* HISTORY_TABLE_V2
   - Table compacte + Drawer (panneau latéral) de détails
   - Au clic sur une ligne ou sur "Détails", ouvre le drawer et injecte le contenu de .ht-detailbox
*/
(function(){
  function qs(sel, root){ return (root || document).querySelector(sel); }
  function qsa(sel, root){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function getDetailHtmlFromRow(row){
    if(!row) return "";
    // priorité: aria-controls sur le bouton
    var btn = row.querySelector(".ht-expander");
    var controlsId = btn ? btn.getAttribute("aria-controls") : null;
    if(!controlsId) return "";
    var detailRow = document.getElementById(controlsId);
    if(!detailRow) return "";
    var box = detailRow.querySelector(".ht-detailbox");
    if(!box) return "";
    var html = box.innerHTML || "";
    // vide "visuellement" ?
    if(!html.replace(/\s+/g,"").length) return "";
    return html;
  }


  function getDrawer(){
    return {
      drawer: qs("#historyDrawer"),
      backdrop: qs("#historyDrawerBackdrop"),
      title: qs("#historyDrawerTitle"),
      eyebrow: qs("#historyDrawerEyebrow"),
      body: qs("#historyDrawerBody"),
      closeBtn: qs("#historyDrawer [data-hd-close]")
    };
  }

  function openDrawer(opts){
    var d = getDrawer();
    if(!d.drawer || !d.backdrop) return;

    if(opts && opts.title) d.title.textContent = opts.title;
    if(opts && opts.eyebrow) d.eyebrow.textContent = opts.eyebrow;
    if(opts && typeof opts.html === "string") d.body.innerHTML = opts.html;

    d.backdrop.hidden = false;
    d.drawer.hidden = false;

    document.documentElement.classList.add("hd-open");
    document.body.classList.add("hd-open");

    // focus
    try{
      (d.closeBtn || d.drawer).focus();
    }catch(e){}
  }

  function closeDrawer(){
    var d = getDrawer();
    if(!d.drawer || !d.backdrop) return;

    d.drawer.hidden = true;
    d.backdrop.hidden = true;

    document.documentElement.classList.remove("hd-open");
    document.body.classList.remove("hd-open");
  }

  function rowTitle(row){
    // Ex: badge + strong + "par X"
    var badge = qs(".history-badge", row);
    var strong = qs(".ht-strong", row);
    var muted = qs(".ht-muted", row);

    var t = "";
    if(badge) t += badge.textContent.trim() + " — ";
    if(strong) t += strong.textContent.trim();
    if(!t && strong) t = strong.textContent.trim();

    // fallback
    if(!t) t = "Détails";
    return { title: t, eyebrow: badge ? badge.textContent.trim() : "Détails" };
  }

  function initTable(table){
    var rows = qsa("tr.ht-row", table);

    rows.forEach(function(row){
      var btn = qs(".ht-expander", row);
      if(!btn) return;

      var controlsId = btn.getAttribute("aria-controls");
      if(!controlsId) return;

      var detailRow = document.getElementById(controlsId);
      if(!detailRow) return;

      var detailBox = qs(".ht-detailbox", detailRow);
      if(!detailBox) return;

      function openFromRow(){
        var ttl = rowTitle(row);
        openDrawer({
          title: ttl.title,
          eyebrow: ttl.eyebrow,
          html: detailBox.innerHTML
        });
      }

      // bouton "Détails"
      btn.addEventListener("click", function(e){
        e.preventDefault();
      var html = getDetailHtmlFromRow(row);
      if(!html) return;

        openFromRow();
      });

      // clic sur ligne (sauf liens / boutons / inputs)
      row.addEventListener("click", function(e){
        var t = e.target;
        if(!t) return;
        if(t.closest("a,button,input,select,textarea,label")) return;
      var html = getDetailHtmlFromRow(row);
      if(!html) return;

        openFromRow();
      });

      // On garde les <tr.ht-detail> invisibles (drawer only)
      btn.setAttribute("aria-expanded", "false");
      row.classList.remove("is-open");
      detailRow.hidden = true;
    });
  }

  function bindGlobalClose(){
    var d = getDrawer();
    if(d.backdrop){
      d.backdrop.addEventListener("click", function(){ closeDrawer(); });
    }
    if(d.closeBtn){
      d.closeBtn.addEventListener("click", function(e){
        e.preventDefault();
        closeDrawer();
      });
    }
    document.addEventListener("keydown", function(e){
      if(e.key === "Escape"){
        var dd = getDrawer();
        if(dd.drawer && !dd.drawer.hidden){
          closeDrawer();
        }
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function(){
    closeDrawer(); // init

    qsa("table.ht-table").forEach(initTable);
    bindGlobalClose();
  });
})();