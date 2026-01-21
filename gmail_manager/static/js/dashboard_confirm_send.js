(function () {
      const modal = document.getElementById("confirmSendModal");
      if (!modal) return;

      const txt = document.getElementById("confirmSendText");
      const titleEl = document.getElementById("confirmSendTitle");
      const btnOk = document.getElementById("confirmSendOk");
      const btnCancel = document.getElementById("confirmSendCancel");
      const btnClose = document.getElementById("confirmSendClose");

      const loadingBox = document.getElementById("confirmSendLoading");
      const loadingText = document.getElementById("confirmSendLoadingText");

      // Progress UI
      const pctEl = document.getElementById("confirmSendProgressPct");
      const fillEl = document.getElementById("confirmSendProgressFill");
      const stepsEl = document.getElementById("confirmSendProgressSteps");
      const barWrap = loadingBox ? loadingBox.querySelector(".sync-progress__bar") : null;

      let isLoading = false;

      let pendingForm = null;
      let pendingHref = null;


        let postSuccessAction = null;
      let pendingProgress = false;
      let pendingProgressTitle = "";
      let pendingProgressText = "";

      let progressTimeouts = [];

      const defaultOkLabel = btnOk ? (btnOk.textContent || "Valider") : "Valider";
      const defaultTitle = titleEl ? (titleEl.textContent || "Confirmation") : "Confirmation";

      function safeClosest(node, selector) {
        const el = (node instanceof Element) ? node : (node && node.parentElement ? node.parentElement : null);
        return el ? el.closest(selector) : null;
      }

      function clearProgressTimers() {
        try { progressTimeouts.forEach(t => clearTimeout(t)); } catch(e) {}
        progressTimeouts = [];
      }

      function setProgress(stepIndex, pct, label) {
        const p = Math.max(0, Math.min(100, Math.round(pct || 0)));

        if (loadingText && label) loadingText.textContent = label;

        if (pctEl) pctEl.textContent = p + "%";
        if (fillEl) fillEl.style.width = p + "%";
        if (barWrap) barWrap.setAttribute("aria-valuenow", String(p));

        if (stepsEl) {
          const items = stepsEl.querySelectorAll("li[data-step]");
          items.forEach(li => {
            const s = parseInt(li.getAttribute("data-step") || "0", 10);
            li.classList.remove("is-active", "is-done");
            if (s < stepIndex) li.classList.add("is-done");
            else if (s === stepIndex) li.classList.add("is-active");
          });
        }
      }

      function resetProgressUI() {
        clearProgressTimers();
        setProgress(0, 0, "");
      }

      function scheduleProgress() {
        clearProgressTimers();

        const plan = [
          { ms: 0,    step: 0, pct: 10, label: "Connexion au serveur…" },
          { ms: 900,  step: 1, pct: 35, label: "Lecture des nouveaux emails…" },
          { ms: 1800, step: 2, pct: 55, label: "Analyse des pièces jointes…" },
          { ms: 2700, step: 3, pct: 75, label: "Création / mise à jour des ordonnances…" },
          { ms: 3600, step: 4, pct: 90, label: "Mise à jour du tableau…" },
        ];

        plan.forEach(p => {
          progressTimeouts.push(setTimeout(() => setProgress(p.step, p.pct, p.label), p.ms));
        });
      }

      function setLoading(state, text) {
        isLoading = !!state;

        // show/hide progress box
        if (loadingBox) loadingBox.style.display = isLoading ? "flex" : "none";

        if (text && loadingText) loadingText.textContent = text;

        // Bloquer fermeture pendant chargement
        if (btnClose) btnClose.disabled = isLoading;

        // Boutons
        if (btnCancel) {
          btnCancel.style.display = isLoading ? "none" : "";
          if (!isLoading && btnCancel.textContent.trim() === "Fermer") {
            btnCancel.textContent = "Annuler";
          }
        }
        if (btnOk) btnOk.disabled = isLoading;
      }

      function openConfirm(message, okLabel, title) {
        resetProgressUI();
        setLoading(false);

        if (titleEl) titleEl.textContent = title || defaultTitle;
        if (txt) txt.textContent = message || "";

        if (btnOk) {
          btnOk.textContent = okLabel || defaultOkLabel;
          btnOk.style.display = "";
          btnOk.disabled = false;
        }
        if (btnCancel) btnCancel.style.display = "";

        modal.style.display = "flex";
        modal.setAttribute("aria-hidden", "false");
      }

      function closeConfirm() {
        if (isLoading) return;

        modal.style.display = "none";
        modal.setAttribute("aria-hidden", "true");

        pendingForm = null;
        pendingHref = null;

        pendingProgress = false;
        pendingProgressTitle = "";
        pendingProgressText = "";

        if (btnOk) {
          btnOk.textContent = defaultOkLabel;
          btnOk.style.display = "";
          btnOk.disabled = false;
        }
        if (btnCancel) btnCancel.textContent = "Annuler";
        if (titleEl) titleEl.textContent = defaultTitle;

        resetProgressUI();
        setLoading(false);
      }

      async function startProgressFetch(href, title, text) {
        resetProgressUI();


          postSuccessAction = null;
        if (titleEl) titleEl.textContent = title || defaultTitle;
        if (txt) txt.textContent = text || "Veuillez patienter…";
        if (btnOk) btnOk.style.display = "none";

        setLoading(true, text || "Synchronisation Gmail en cours… Recherche des nouveaux emails…");
        scheduleProgress();

        try {
          const resp = await fetch(href, {
            method: "GET",
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" }
          });

          // (no redirect) target non utilisé

          // fin UI avant redirection
          clearProgressTimers();
          setProgress(5, 100, "Synchronisation Gmail terminée ✅");

          // Fin (pas de redirection) : on garde la popup ouverte (mode SaaS)

          isLoading = false;

          if (loadingBox) loadingBox.style.display = "block";

          if (btnClose) btnClose.disabled = false;

          if (btnCancel) { btnCancel.style.display = ""; btnCancel.textContent = "Fermer"; }

if (btnOk) { btnOk.style.display = "none"; btnOk.disabled = false; btnOk.textContent = defaultOkLabel; }

postSuccessAction = null;

          pendingHref = null;

          pendingForm = null;

          pendingProgress = false;
            // Auto-refresh après sync Gmail (pour voir les nouvelles ordonnances)
            const __shouldReload = (String(title||"").toLowerCase().includes("synchron") || String(href||"").toLowerCase().includes("sync"));
            if (__shouldReload) {
              try { if (txt) txt.textContent = (txt.textContent || "") + " Rafraîchissement…"; } catch (_) {}
              setTimeout(() => { try { window.location.reload(); } catch (_) {} }, 650);
            }
            // (no redirect) redirection désactivée

        } catch (e) {
          clearProgressTimers();
          setLoading(false);
          
          // Auto-refresh après sync Gmail (pour voir les nouvelles ordonnances)
          const __shouldReload = (String(title||'').toLowerCase().includes('synchron') || String(href||'').toLowerCase().includes('sync'));
          if (__shouldReload) {
            setTimeout(() => { try { window.location.reload(); } catch (_) {} }, 400);
          }
if (btnCancel) btnCancel.textContent = "Fermer";
          if (btnOk) btnOk.style.display = "none";
          if (titleEl) titleEl.textContent = "Erreur";
          if (txt) txt.textContent = "Erreur: synchronisation Gmail impossible. Vérifie la connexion et réessaie.";
        }
      }

      // Fermeture
      if (btnCancel) btnCancel.addEventListener("click", closeConfirm);
      if (btnClose) btnClose.addEventListener("click", closeConfirm);

      modal.addEventListener("click", function (e) {
        if (e.target === modal) closeConfirm();
      });

      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeConfirm();
      });

      // 1) Confirmation navigation (sync/logout)
      document.addEventListener("click", function (e) {
        const link = safeClosest(e.target, "a.js-confirm-nav");
        if (!link) return;

        e.preventDefault();

        const href = link.getAttribute("href");
        if (!href) return;

        pendingHref = href;
        pendingForm = null;

        pendingProgress = (link.getAttribute("data-progress") === "1");
        pendingProgressTitle = link.getAttribute("data-progress-title") || "Traitement";
        pendingProgressText = link.getAttribute("data-progress-text") || "Veuillez patienter…";

        const msg = link.getAttribute("data-confirm") || "Confirmer cette action ?";
        const okText = link.getAttribute("data-ok-text") || "Valider";

        openConfirm(msg, okText, defaultTitle);
      }, true);

      // 2) Confirmation envoi Email/SMS (forms)
      document.addEventListener("click", function (e) {
        const btn = safeClosest(e.target, ".js-confirm-send");
        if (!btn) return;

        const form = btn.closest("form");
        if (!form) return;

        e.preventDefault();

        pendingForm = form;
        pendingHref = null;
        pendingProgress = false;

        const msg = btn.getAttribute("data-confirm") || "Confirmer cet envoi ?";
        const okText = btn.getAttribute("data-ok-text") || defaultOkLabel;

        openConfirm(msg, okText, defaultTitle);
      }, true);

      // OK -> exécuter l’action
      if (btnOk) {
        btnOk.addEventListener("click", function () {
          if (isLoading) return;

          if (pendingForm) {
            setLoading(true, "Envoi en cours…");
            pendingForm.submit();
            return;
          }

          if (pendingHref) {
            if (pendingProgress) {
              startProgressFetch(pendingHref, pendingProgressTitle, pendingProgressText);
              return;
            } else {
              // (no redirect) redirection désactivée
            }
          }
        });
      }
    })();
