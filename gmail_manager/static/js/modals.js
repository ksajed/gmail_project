(function () {
  // Flag debug (tu peux tester: window.__MODALS_OK)
  window.__MODALS_OK = true;

  const MODAL_ID = "createPrescriptionModal";

  // ============================================================================
  // API MODALES UNIQUE (globale)
  // - Compatible: modales style="display:none" (prescription_detail)
  // - Compatible: modales .is-open (createPrescriptionModal)
  // - Garde body.modal-open tant qu'au moins 1 modale est ouverte
  // ============================================================================
  function isOpen(overlay) {
    if (!overlay) return false;
    try {
      if (overlay.classList && overlay.classList.contains("is-open")) return true;
      const ds = (overlay.style && overlay.style.display) ? overlay.style.display : "";
      if (ds && ds !== "none") return true;
      // fallback computed style
      return window.getComputedStyle(overlay).display !== "none";
    } catch (e) {
      return false;
    }
  }

  function setOpen(overlay, open) {
    if (!overlay) return;
    if (open) {
      overlay.classList.add("is-open");
      overlay.style.display = "flex";
      overlay.setAttribute("aria-hidden", "false");
    } else {
      overlay.classList.remove("is-open");
      overlay.style.display = "none";
      overlay.setAttribute("aria-hidden", "true");
    }
  }

  function anyModalOpen() {
    const overlays = document.querySelectorAll(".modal-overlay");
    for (const ov of overlays) {
      if (isOpen(ov)) return true;
    }
    return false;
  }

  // window.openModal(id) / window.closeModal(id)
  window.openModal = function (id) {
    const targetId = (typeof id === "string" && id) ? id : MODAL_ID;
    const overlay = document.getElementById(targetId);
    if (!overlay) return;

    setOpen(overlay, true);
    document.body.classList.add("modal-open");

    const focusable = overlay.querySelector(
      "input, select, textarea, button, a[href], [tabindex]:not([tabindex='-1'])"
    );
    if (focusable) setTimeout(() => focusable.focus(), 0);
  };

  window.closeModal = function (id) {
    const targetId = (typeof id === "string" && id) ? id : MODAL_ID;
    const overlay = document.getElementById(targetId);
    if (!overlay) return;

    setOpen(overlay, false);

    // Ne retire modal-open que si aucune modale n'est encore visible
    if (!anyModalOpen()) {
      document.body.classList.remove("modal-open");
    }
  };

  // Backdrop close (toutes les modales)
  document.addEventListener("click", function (e) {
    const target = e.target;
    if (!target || !(target instanceof HTMLElement)) return;
    if (!target.classList.contains("modal-overlay")) return;
    if (!target.id) return;
    if (e.target === target) {
      window.closeModal(target.id);
    }
  });

  // ESC close (toutes les modales)
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;

    document.querySelectorAll(".modal-overlay").forEach((ov) => {
      if (!isOpen(ov)) return;
      if (ov.id) window.closeModal(ov.id);
      else setOpen(ov, false);
    });

    if (!anyModalOpen()) document.body.classList.remove("modal-open");
  });

  // Helpers modal default (createPrescriptionModal)
  function openDefault() { window.openModal(MODAL_ID); }
  function closeDefault() { window.closeModal(MODAL_ID); }

  // --- Utils ---
  function isAllowedFile(file) {
    if (!file) return false;

    const name = (file.name || "").toLowerCase();
    const type = (file.type || "").toLowerCase();

    // PDF
    if (type === "application/pdf" || name.endsWith(".pdf")) return true;

    // Images (type parfois vide => fallback extension)
    if (type.startsWith("image/")) return true;
    if (/\.(jpg|jpeg|png|gif|webp)$/i.test(name)) return true;

    return false;
  }

  function setFilesToInput(input, files) {
    // ⚠️ Certains navigateurs peuvent bloquer l'assignation
    // => try/catch + message fallback
    const dt = new DataTransfer();
    Array.from(files).forEach((f) => dt.items.add(f));
    input.files = dt.files;
  }

  function updateFilesMeta(input, metaEl) {
    const files = Array.from(input.files || []);
    if (!files.length) {
      metaEl.textContent = "Aucun fichier sélectionné.";
      return;
    }

    if (files.length === 1) {
      metaEl.textContent = `1 fichier : ${files[0].name}`;
      return;
    }

    metaEl.textContent = `${files.length} fichiers : ${files.map((f) => f.name).join(" • ")}`;
  }

  // --- Global protection: évite que le navigateur "ouvre" le fichier quand tu lâches ---
  function bindGlobalDnDGuardsOnce() {
    if (window.__RX_DND_GUARDS_BOUND) return;
    window.__RX_DND_GUARDS_BOUND = true;

    const guard = (e) => {
      // seulement quand modal ouvert
      if (!document.body.classList.contains("modal-open")) return;
      e.preventDefault();
    };

    window.addEventListener("dragover", guard);
    window.addEventListener("drop", guard);
  }

  function initDropzone() {
    const dropzone = document.getElementById("rxDropzone");
    const pickBtn = document.getElementById("rxPickBtn");
    const input = document.getElementById("attachments");
    const meta = document.getElementById("rxFilesMeta");

    if (!dropzone || !pickBtn || !input || !meta) return;

    // Init une seule fois
    if (dropzone.dataset.inited === "1") return;
    dropzone.dataset.inited = "1";

    bindGlobalDnDGuardsOnce();

    // Click sur bouton "Choisir"
    pickBtn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation(); // évite double click bubble
      input.click();
    });

    // Click sur toute la dropzone
    dropzone.addEventListener("click", function () {
      input.click();
    });

    // Accessibilité clavier
    dropzone.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        input.click();
      }
    });

    // Quand on choisit via le file picker
    input.addEventListener("change", function () {
      updateFilesMeta(input, meta);
    });

    // Drag enter/over
    const onDragOver = function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("is-dragover");
    };
    dropzone.addEventListener("dragenter", onDragOver);
    dropzone.addEventListener("dragover", onDragOver);

    // Drag leave
    dropzone.addEventListener("dragleave", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (e.target === dropzone) dropzone.classList.remove("is-dragover");
    });

    // Drop
    dropzone.addEventListener("drop", function (e) {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("is-dragover");

      const dropped = (e.dataTransfer && e.dataTransfer.files) ? Array.from(e.dataTransfer.files) : [];
      if (!dropped.length) return;

      const filtered = dropped.filter(isAllowedFile);
      if (!filtered.length) {
        meta.textContent = "Formats acceptés : PDF ou images (JPG/PNG/WebP).";
        return;
      }

      // Merge avec fichiers existants (si l'utilisateur ajoute en plusieurs fois)
      const existing = Array.from(input.files || []);
      const merged = existing.concat(filtered);

      // Option: enlever doublons (nom+taille)
      const uniq = [];
      const seen = new Set();
      for (const f of merged) {
        const key = `${f.name}__${f.size}`;
        if (seen.has(key)) continue;
        seen.add(key);
        uniq.push(f);
      }

      try {
        setFilesToInput(input, uniq);
        updateFilesMeta(input, meta);
      } catch (err) {
        console.error("Impossible d'affecter les fichiers via DataTransfer:", err);
        meta.textContent = "Votre navigateur bloque le drag & drop : utilisez le bouton “Choisir”.";
      }
    });

    // Affichage initial
    updateFilesMeta(input, meta);
  }

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("btnNewPrescription");
    const overlay = document.getElementById(MODAL_ID);
    const closeBtn = document.getElementById("modalCloseBtn");
    const cancelBtn = document.getElementById("modalCancelBtn");

    if (btn) {
      btn.addEventListener("click", function () {
        openDefault();
        initDropzone(); // init quand on ouvre
      });
    }

    if (closeBtn) closeBtn.addEventListener("click", closeDefault);
    if (cancelBtn) cancelBtn.addEventListener("click", closeDefault);

    if (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) closeDefault();
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDefault();
    });

    // init au chargement (si modal déjà dans le DOM)
    initDropzone();
  });
})();
