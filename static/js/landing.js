/* Landing sahifa: ko'rinish animatsiyasi va mobil menyuni yopish. Bootstrap (scrollspy, carousel, accordion) o'zi ishlaydi. */
(function () {
  "use strict";

  /* --- Elementlar ekranga kirganda ravon paydo bo'ladi --- */
  const items = document.querySelectorAll(".reveal");
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!("IntersectionObserver" in window) || reduce) {
    items.forEach(function (el) { el.classList.add("in"); });
  } else {
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    items.forEach(function (el) { io.observe(el); });
  }

  /* --- Mobil menyu: bo'limga o'tilganda yopiladi --- */
  const nav = document.getElementById("landing-nav");
  if (nav && window.bootstrap) {
    nav.querySelectorAll("a.nav-link").forEach(function (link) {
      link.addEventListener("click", function () {
        if (nav.classList.contains("show")) window.bootstrap.Collapse.getOrCreateInstance(nav).hide();
      });
    });
  }
})();
