document.addEventListener("DOMContentLoaded", () => {
  // Załaduj header i footer
  loadFragment("header.html", "header-placeholder");
  loadFragment("footer.html", "footer-placeholder");

  // Zbuduj spis treści
  generateTOC();

  // Hamburger toggle
  const hamburger = document.getElementById("hamburger");
  const toc = document.getElementById("toc-container");
  hamburger.addEventListener("click", () => {
  toc.classList.toggle("toc-hidden");
  document.body.classList.toggle("toc-hidden-body");
});


  // Zamknij TOC po kliknięciu linku (na mobilkach)
  document.addEventListener("click", e => {
    if (
      window.innerWidth <= 768 &&
      e.target.tagName === "A" &&
      toc.contains(e.target)
    ) {
      toc.classList.add("toc-hidden");
    }
  });

  // 🔽 Wczytaj artykuly.html na start
  fetch("zadania.html")
    .then(res => {
      if (!res.ok) throw new Error("Błąd ładowania artykułów");
      return res.text();
    })
    .then(html => {
      document.getElementById("article-viewer").innerHTML = html;
    })
    .catch(err => {
      console.error("Błąd ładowania artykułów:", err);
      document.getElementById("article-viewer").innerHTML =
        "<p style='color:red;'>Nie udało się załadować artykułów.</p>";
    });
});

function loadFragment(path, placeholderId) {
  fetch(path)
    .then(res => {
      if (!res.ok) throw new Error(`${path} HTTP ${res.status}`);
      return res.text();
    })
    .then(html => {
      document.getElementById(placeholderId).innerHTML = html;
    })
    .catch(err => {
      console.error(`Błąd ładowania ${path}:`, err);
      document.getElementById(placeholderId).innerHTML =
        `<p style="color:red;">Błąd ładowania ${path}</p>`;
    });
}

function generateTOC() {
  fetch("zadania.html")
    .then(res => {
      if (!res.ok) throw new Error(`index.html HTTP ${res.status}`);
      return res.text();
    })
    .then(html => {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const sections = doc.querySelectorAll("section.article-section");

      const toc = document.getElementById("toc-container");
      toc.innerHTML = `<h2 id="toc-title">Spis treści</h2>`;

      // Kliknięcie "Spis treści" wczytuje artykuly.html
      const tocTitle = document.getElementById("toc-title");
      if (tocTitle) {
        tocTitle.style.cursor = "pointer";
        tocTitle.addEventListener("click", () => {
          fetch("zadania.html")
            .then(res => {
              if (!res.ok) throw new Error("Błąd ładowania artykułów");
              return res.text();
            })
            .then(html => {
              document.getElementById("article-viewer").innerHTML = html;
            })
            .catch(err => {
              console.error("Nie udało się wczytać artykułu:", err);
              document.getElementById("article-viewer").innerHTML =
                "<p>Nie udało się załadować artykułu.</p>";
            });
        });
      }

      sections.forEach(section => {
        const title = section.querySelector("h2")?.textContent.trim() || "";
        const header = document.createElement("h3");
        header.textContent = title;
        header.classList.add("toc-header", "collapsed");

        const ul = document.createElement("ul");
        ul.classList.add("collapsed");

        header.addEventListener("click", () => {
          header.classList.toggle("collapsed");
          ul.classList.toggle("collapsed");
        });

        section.querySelectorAll(".article-card").forEach(card => {
          const artTitle = card.querySelector(".article-title")?.textContent.trim();
          if (!artTitle) return;
          const slug = artTitle
            .toLowerCase()
            .replace(/\s+/g, "-")
            .replace(/[^\w-]/g, "");
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.href = "#";
          a.textContent = artTitle;
          a.dataset.file = `zadania/${slug}.html`;
          a.addEventListener("click", e => {
            e.preventDefault();
            loadArticle(a.dataset.file);
          });
          li.appendChild(a);
          ul.appendChild(li);
        });

        toc.appendChild(header);
        toc.appendChild(ul);
      });
    })
    .catch(err => {
      console.error("generateTOC error:", err);
      document.getElementById("toc-container").innerHTML =
        `<p style="color:red;">Nie udało się wygenerować spisu.</p>`;
    });
}

function loadArticle(path) {
  const viewer = document.getElementById("article-viewer");

  // Załaduj CSS jeśli nie jest jeszcze wczytany
  if (!document.getElementById("artykul-css")) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "artykul.css";
    link.id = "artykul-css";
    document.head.appendChild(link);
  }

  fetch(path)
    .then(res => {
      if (!res.ok) {
        // zamiast rzucać wyjątek → od razu wczytujemy workinprogress.html
        return fetch("workinprogress.html").then(r => r.text());
      }
      return res.text();
    })
    .then(html => {
      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = html;

      tempDiv.querySelectorAll("img").forEach(img => {
        const src = img.getAttribute("src");
        if (src && !src.startsWith("http") && !src.startsWith("/") && !src.startsWith("data:")) {
          const basePath = path.substring(0, path.lastIndexOf("/") + 1);
          img.src = basePath + src;
        }
      });

      viewer.innerHTML = tempDiv.innerHTML;

      if (window.MathJax && window.MathJax.typesetPromise) {
        MathJax.typesetClear?.();
        MathJax.typesetPromise([viewer]).catch(err =>
          console.error("MathJax error:", err)
        );
      }

      window.scrollTo({ top: 0, behavior: "smooth" });
    })
    .catch(err => {
      console.error("loadArticle error:", err);
      // tu również fallback do workinprogress.html
      fetch("workinprogress.html")
        .then(r => r.text())
        .then(html => {
          viewer.innerHTML = html;
        })
        .catch(() => {
          viewer.innerHTML = `<p style="color:red;">Nie udało się załadować strony work in progress.</p>`;
        });
    });
}
document.addEventListener("click", (e) => {
  const card = e.target.closest(".article-card");
  if (!card) return;

  const titleEl = card.querySelector(".article-title");
  if (!titleEl) return;

  const title = titleEl.textContent.trim();
  const slug = title
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^\w-]/g, "");

  const path = `zadania/${slug}.html`;
  loadArticle(path);
});