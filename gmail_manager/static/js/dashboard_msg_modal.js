(function () {
      const modal = document.getElementById("dashMsgModal");
      if (!modal) return;

      const closeBtn = document.getElementById("dashMsgCloseBtn");

      function openDashMsgModal() {
        modal.style.display = "flex";
      }

      function closeDashMsgModal() {
        modal.style.display = "none";
      }

      if (closeBtn) {
        closeBtn.addEventListener("click", closeDashMsgModal);
      }

      // Click = close
      modal.addEventListener("click", function(e) {
        if (e.target === modal) closeDashMsgModal();
      });

      // ESC = close
      document.addEventListener("keydown", function(e) {
        if (e.key === "Escape" && modal.style.display !== "none") {
          closeDashMsgModal();
        }
      });

      // Auto-open si messages موجودة
      document.addEventListener("DOMContentLoaded", function () {
        const show = (modal.getAttribute("data-show") || "0") === "1";
        if (show) openDashMsgModal();
      });
    })();
