document.addEventListener("DOMContentLoaded", () => {

    /* =========================
       THEME TOGGLE (Dark / Light)
    ========================= */
    const toggleBtn = document.getElementById("theme-toggle");
    const body = document.body;

    if (toggleBtn) {
        if (localStorage.getItem("theme") === "dark") {
            body.classList.add("dark");
            toggleBtn.textContent = "☀️";
        }

        toggleBtn.addEventListener("click", () => {
            body.classList.toggle("dark");

            if (body.classList.contains("dark")) {
                localStorage.setItem("theme", "dark");
                toggleBtn.textContent = "☀️";
            } else {
                localStorage.setItem("theme", "light");
                toggleBtn.textContent = "🌙";
            }
        });
    }

    /* =========================
       LOADER ON FORM SUBMIT
    ========================= */
    document.querySelectorAll("form").forEach(form => {
        form.addEventListener("submit", () => {
            const loader = document.getElementById("loader-overlay");
            const button = form.querySelector("button");
            const originalText = button ? button.textContent : "";

            if (loader) loader.style.display = "flex";

            if (button) {
                button.disabled = true;
                button.textContent = "Processing...";
            }

            // UX fallback (auto-hide)
            setTimeout(() => {
                if (loader) loader.style.display = "none";
                if (button) {
                    button.disabled = false;
                    button.textContent = originalText;
                }
            }, 3000);
        });
    });

    /* =========================
       TOOL SEARCH (HOME PAGE)
    ========================= */
    const searchInput = document.getElementById("toolSearch");
    const cards = document.querySelectorAll(".card");

    if (searchInput) {
        searchInput.addEventListener("input", () => {
            const query = searchInput.value.toLowerCase().trim();

            cards.forEach(card => {
                const keywords = card.dataset.tool || "";
                card.style.display = keywords.includes(query)
                    ? "block"
                    : "none";
            });
        });
    }

    /* =========================
       GLOBAL FILE UPLOAD LABEL
    ========================= */
    document.querySelectorAll(".file-input").forEach(input => {
        const uploadBox = input.closest(".upload-box");
        if (!uploadBox) return;

        const text = uploadBox.querySelector(".upload-text");
        const hint = uploadBox.querySelector(".upload-hint");

        input.addEventListener("change", () => {
            if (input.files.length > 0) {
                text.textContent = "📄 " + input.files[0].name;
                hint.textContent = "File selected successfully";
            }
        });
    });

});

/* =========================
   SAFETY: HIDE LOADER ON PAGE LOAD
========================= */
window.addEventListener("load", () => {
    const loader = document.getElementById("loader-overlay");
    if (loader) loader.style.display = "none";
});