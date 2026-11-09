(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var track = document.getElementById("route-track");
  var truck = document.getElementById("data-truck");

  if (track && truck && window.gsap && !reduceMotion) {
    var length = track.getTotalLength();
    var progress = { distance: 0 };
    gsap.to(progress, {
      distance: length,
      duration: 23,
      repeat: -1,
      ease: "none",
      onUpdate: function () {
        var point = track.getPointAtLength(progress.distance);
        var next = track.getPointAtLength(Math.min(length, progress.distance + 1));
        var angle = Math.atan2(next.y - point.y, next.x - point.x) * (180 / Math.PI);
        truck.setAttribute("transform", "translate(" + point.x + " " + point.y + ") rotate(" + angle + ")");
      }
    });
    gsap.fromTo(".route-track", { strokeDasharray: "4 20", strokeDashoffset: 24 }, {
      strokeDashoffset: -24,
      duration: 1.2,
      repeat: -1,
      ease: "none"
    });
  } else if (track && truck) {
    var startPoint = track.getPointAtLength(0);
    truck.setAttribute("transform", "translate(" + startPoint.x + " " + startPoint.y + ")");
  }

  var progressBar = document.getElementById("reading-progress-bar");
  function updateProgress() {
    if (!progressBar) return;
    var scrollable = document.documentElement.scrollHeight - window.innerHeight;
    var amount = scrollable > 0 ? (window.scrollY / scrollable) * 100 : 0;
    progressBar.style.width = Math.min(100, Math.max(0, amount)) + "%";
  }
  window.addEventListener("scroll", updateProgress, { passive: true });
  updateProgress();

  var article = document.querySelector(".article-copy");
  var toc = document.getElementById("article-toc");
  if (article && toc) {
    var headings = Array.prototype.slice.call(article.querySelectorAll("h2, h3"));
    var topLevelIndex = 0;
    var list = document.createElement("ul");
    list.className = "article-toc-list";

    headings.forEach(function (heading) {
      if (!heading.id) {
        heading.id = heading.textContent.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
      }
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = "#" + heading.id;
      link.textContent = heading.textContent.replace(/^\d+(\.\d+)*\.\s*/, "");
      if (heading.tagName === "H3") item.className = "toc-sub";
      else topLevelIndex += 1;
      link.setAttribute("data-heading", heading.id);
      item.appendChild(link);
      list.appendChild(item);
    });
    toc.appendChild(list);

    if ("IntersectionObserver" in window && !reduceMotion) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          toc.querySelectorAll("a").forEach(function (link) { link.classList.remove("is-active"); });
          var active = toc.querySelector('[data-heading="' + entry.target.id + '"]');
          if (active) active.classList.add("is-active");
        });
      }, { rootMargin: "-18% 0px -72% 0px" });
      headings.forEach(function (heading) { observer.observe(heading); });
    }
  }

  if (window.mermaid) {
    document.querySelectorAll("pre code.language-mermaid").forEach(function (code) {
      var diagram = document.createElement("div");
      diagram.className = "mermaid";
      diagram.textContent = code.textContent;
      code.parentElement.replaceWith(diagram);
    });
    mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
    mermaid.run({ querySelector: ".mermaid" });
  }
})();
