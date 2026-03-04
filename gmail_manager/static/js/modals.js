(function () {
  // Flag debug (tu peux tester: window.__MODALS_OK)
  window.__MODALS_OK = true;

  const MODAL_ID = "createPrescriptionModal";

  // --- Modal open/close ---
  function openModal() {
    const overlay = document.getElementById(MODAL_ID);
    if (!overlay) return;

    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  }

  function closeModal() {
    const overlay = document.getElementById(MODAL_ID);
    if (!overlay) return;

    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }

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
    

    // ✅ Ordo: ce modal ne doit exister QUE sur les pages qui ont le bouton.
    // Sur les pages détail (ex: /prescription/<id>/), on le retire du DOM pour éviter tout artefact UI.
    if (!btn && overlay) {
      overlay.remove();
      return;
    }
const closeBtn = document.getElementById("modalCloseBtn");
    const cancelBtn = document.getElementById("modalCancelBtn");

    if (btn) {
      btn.addEventListener("click", function () {
        openModal();
        initDropzone(); // init quand on ouvre
      });
    }

    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

    if (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) closeModal();
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeModal();
    });

    // init au chargement (si modal déjà dans le DOM)
    initDropzone();
  });
})();
