
document.addEventListener("DOMContentLoaded", function () {
  console.log("DOM wczytany");

  fetch("header.html")
    .then(res => {
      console.log("Header pobrany:", res.status);
      return res.text();
    })
    .then(data => {
      document.getElementById("header-placeholder").innerHTML = data;
      console.log("Header wstawiony do DOM");

      setTimeout(() => {
        console.log("Próba znalezienia elementów .nav-toggle i .nav-links");
        const navToggle = document.querySelector(".nav-toggle");
        const navLinks = document.querySelector(".nav-links");

        if (!navToggle) {
          console.error("Brak przycisku .nav-toggle!");
          alert("DEBUG: Brak przycisku .nav-toggle!");
          return;
        }
        if (!navLinks) {
          console.error("Brak listy .nav-links!");
          alert("DEBUG: Brak listy .nav-links!");
          return;
        }

        console.log("Znaleziono elementy. Dodaję event listener do hamburgera.");

        navToggle.addEventListener("click", () => {
          console.log("Hamburger kliknięty!");
          navLinks.classList.toggle("active");
          console.log("Toggle klasy 'active' na .nav-links");
        });

      }, 100);
    })
    .catch(err => {
      console.error("Błąd przy pobieraniu headera:", err);
      alert("DEBUG: Błąd przy pobieraniu headera: " + err);
    });

  fetch("footer.html")
    .then(res => res.text())
    .then(data => {
      document.getElementById("footer-placeholder").innerHTML = data;
    });
});