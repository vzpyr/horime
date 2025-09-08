document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("anime-search");
  const cards = document.querySelectorAll("#anime-results .anime-card");

  if (!searchInput) return;

  searchInput.addEventListener("input", () => {
    const q = searchInput.value.toLowerCase();
    let anyVisible = false;

    cards.forEach(card => {
      const name = card.dataset.name;
      const year = card.dataset.year.toLowerCase();
      if (!q || name.includes(q) || year.includes(q)) {
        card.style.display = "";
        anyVisible = true;
      } else {
        card.style.display = "none";
      }
    });

    let emptyEl = document.querySelector("#anime-results .empty");
    if (!anyVisible) {
      if (!emptyEl) {
        emptyEl = document.createElement("div");
        emptyEl.className = "empty";
        emptyEl.textContent = "No results.";
        document.getElementById("anime-results").appendChild(emptyEl);
      }
    } else if (emptyEl) {
      emptyEl.remove();
    }
  });
});
