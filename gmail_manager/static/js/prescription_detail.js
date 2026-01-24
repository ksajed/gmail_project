function openModal(id){
    const el = document.getElementById(id);
    if(!el) return;
    el.style.display = "flex";
    const focusable = el.querySelector("input, select, button");
    if(focusable) setTimeout(() => focusable.focus(), 0);
  }

  function closeModal(id){
    const el = document.getElementById(id);
    if(!el) return;
    el.style.display = "none";
  }

  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if(e.target === overlay) overlay.style.display = "none";
    });
  });

  document.addEventListener("keydown", (e) => {
    if(e.key === "Escape"){
      document.querySelectorAll(".modal-overlay").forEach(m => m.style.display = "none");
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".btn-viewer").forEach(btn => {
      btn.addEventListener("click", e => {
        e.preventDefault();
        const url = btn.dataset.viewerUrl;
        window.open(url, "viewer", "width=1100,height=760,resizable=yes,scrollbars=yes");
      });
    });
  });

  // Auto-open modals (ex: renewalDoneModal)
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll('.modal-overlay[data-auto-open="1"]').forEach((el) => {
      try {
        // messagesModal: n'ouvrir que si au moins 1 notification visible
        if (el && el.id === "messagesModal" && !el.querySelector('[data-msg-item="1"]')) {
          return;
        }
        if (el.id) {
          openModal(el.id);
        } else {
          el.style.display = "flex";
        }
      } catch (e) {
        el.style.display = "flex";
      }
    });
  });
  // CONFIRM_ACTION_MODAL:BEGIN
  let __confirmPendingForm = null;
  let __confirmPendingSubmitter = null;

  document.addEventListener("click", (e) => {
    const submitter = e.target.closest('button[type="submit"], input[type="submit"]');
    if (submitter && submitter.form) {
      __confirmPendingSubmitter = submitter;
    }
  });

  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form || form.tagName !== "FORM") return;

    const method = (form.getAttribute("method") || "").toLowerCase();
    if (method !== "post") return;

    // Confirmation pour TOUTES les actions (même dans les modales),
    // sauf si on est dans la modale de confirmation elle-même (évite boucle).
    if (form.closest("#confirmActionModal")) return;
    if (form.dataset && form.dataset.confirmSkip === "1") return;

    e.preventDefault();
    __confirmPendingForm = form;

    const btn =
      (__confirmPendingSubmitter && __confirmPendingSubmitter.form === form)
        ? __confirmPendingSubmitter
        : form.querySelector('button[type="submit"], input[type="submit"]');

    const label = btn ? ((btn.innerText || btn.value || "").trim()) : "";
    const msgEl = document.getElementById("confirmActionModalMsg");
    if (msgEl) {
      msgEl.textContent = label ? ('Confirmer : "' + label + '" ?') : "Confirmer cette action ?";
    }

    openModal("confirmActionModal");
  });

  function confirmActionCancel() {
    __confirmPendingForm = null;
    __confirmPendingSubmitter = null;
    closeModal("confirmActionModal");
  }
  function confirmActionSubmit() {
    closeModal("confirmActionModal");

    const form = __confirmPendingForm;
    const submitter = __confirmPendingSubmitter;

    __confirmPendingForm = null;
    __confirmPendingSubmitter = null;

    if (!form) return;

    // Évite la boucle de confirmation + conserve la validation HTML5 (required, email, etc.)
    try {
      form.dataset.confirmSkip = "1";

      if (typeof form.requestSubmit === "function") {
        if (submitter && submitter.form === form) {
          form.requestSubmit(submitter);
        } else {
          form.requestSubmit();
        }
      } else {
        // Fallback anciens navigateurs
        if (typeof form.reportValidity === "function") {
          if (!form.reportValidity()) return;
        } else if (typeof form.checkValidity === "function") {
          if (!form.checkValidity()) return;
        }
        form.submit();
      }
    } finally {
      try {
        delete form.dataset.confirmSkip;
      } catch (_) {
        // ignore
      }
    }
  }
  // CONFIRM_ACTION_MODAL:END
