(function () {

  function openModal(id) {
    const modal = document.getElementById(id);
    if (!modal) {
      console.error("❌ Modal introuvable :", id);
      return;
    }
    modal.style.display = "flex";
  }

  function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.style.display = "none";
  }

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("btnNewPrescription");
    const overlay = document.getElementById("createPrescriptionModal");
    const closeBtn = document.getElementById("modalCloseBtn");
    const cancelBtn = document.getElementById("modalCancelBtn");

    if (btn) {
      btn.addEventListener("click", function () {
        openModal("createPrescriptionModal");
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        closeModal("createPrescriptionModal");
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        closeModal("createPrescriptionModal");
      });
    }

    if (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target === overlay) {
          closeModal("createPrescriptionModal");
        }
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeModal("createPrescriptionModal");
      }
    });
  });

})();
