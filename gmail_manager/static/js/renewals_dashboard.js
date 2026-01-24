(function () {
      const modal = document.getElementById("renewalsModal");
      if (!modal) return;

      const titleEl = document.getElementById("renewalsModalTitle");
      const bodyEl = document.getElementById("renewalsModalBody");
      const actionsEl = document.getElementById("renewalsModalActions");
      const btnOk = document.getElementById("renewalsModalOkBtn");
      const btnCancel = document.getElementById("renewalsModalCancelBtn");
      const btnClose = document.getElementById("renewalsModalCloseBtn");

      let pendingForm = null;

      function rxOpenModal(title, html, withActions) {
        if (titleEl) titleEl.textContent = title || "Information";
        if (bodyEl) bodyEl.innerHTML = html || "";
        if (actionsEl) actionsEl.style.display = withActions ? "flex" : "none";
        modal.style.display = "flex";
      }

      function rxCloseModal() {
        modal.style.display = "none";
        pendingForm = null;
      }

      // Confirmation envoi Email/SMS
      document.addEventListener("click", function (e) {
        const btn = e.target.closest(".js-confirm-send");
        if (!btn) return;

        const form = btn.closest("form");
        if (!form) return;

        const channel = (btn.getAttribute("data-channel") || "ACTION").toUpperCase();
        const days = String(btn.getAttribute("data-days") || "");
        const pid = String(btn.getAttribute("data-prescription") || "");
        const when = (days === "0") ? "RETARD" : ("J-" + days);

        pendingForm = form;
        rxOpenModal(
          "Confirmation",
          `<div style="font-weight:900; margin-bottom:6px;">Confirmer l’envoi</div>
           <div>Envoyer <b>${channel}</b> au patient — Ordonnance #${pid} (${when}) ?</div>`,
          true
        );
      });

      if (btnOk) {
        btnOk.addEventListener("click", function () {
          if (pendingForm) pendingForm.submit();
          rxCloseModal();
        });
      }
      if (btnCancel) btnCancel.addEventListener("click", rxCloseModal);
      if (btnClose) btnClose.addEventListener("click", rxCloseModal);

      modal.addEventListener("click", function (e) {
        if (e.target === modal) rxCloseModal();
      });

      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && modal.style.display !== "none") rxCloseModal();
      });

      // Notifications Django messages => même modal, sans actions
      const hasMessages = (modal.getAttribute("data-has-messages") || "0") === "1";
      if (hasMessages) {
        const tpl = document.getElementById("renewalsMessagesTpl");
        const html = tpl
          ? tpl.innerHTML
          : '<div style="font-weight:900; margin-bottom:10px;">Notifications</div>';
        rxOpenModal("Notifications", html, false);
      }
})();
