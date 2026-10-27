(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- 3d shelf: books drift along the row and loop ----------
  const track = document.querySelector(".shelf-track");
  if (track) {
    const books = [...track.querySelectorAll(".book3d")];
    let spacing = 0, total = 0, offset = 0, speed = reduce ? 0 : 0.35, target = speed, last = 0;
    const layout = () => {
      const w = books[0].getBoundingClientRect().width || 200;
      spacing = w * 0.66;
      total = spacing * books.length;
    };
    const place = () => {
      books.forEach((b, i) => {
        const shift = total / 2 - innerWidth * 0.5;
        let x = (i * spacing - offset + shift) % total;
        if (x < 0) x += total;
        x -= total / 2;
        b.style.transform = `translate3d(${x}px,${x * 0.16}px,0)`;
        b.style.zIndex = Math.round(x + total);
      });
    };
    const tick = (t) => {
      const dt = last ? Math.min(t - last, 50) : 16;
      last = t;
      speed += (target - speed) * 0.06;
      offset += speed * dt * 0.06;
      place();
      requestAnimationFrame(tick);
    };
    const shelf = track.closest(".shelf");
    shelf.addEventListener("mouseenter", () => { if (!reduce) target = 0.04; });
    shelf.addEventListener("mouseleave", () => { if (!reduce) target = 0.35; });
    // drag / wheel to scrub
    let dragX = null;
    shelf.addEventListener("pointerdown", (e) => { dragX = e.clientX; shelf.setPointerCapture(e.pointerId); moved = 0; });
    let moved = 0;
    shelf.addEventListener("pointermove", (e) => {
      if (dragX === null) return;
      const dx = e.clientX - dragX; dragX = e.clientX; moved += Math.abs(dx);
      offset -= dx * 1.4;
    });
    shelf.addEventListener("pointerup", () => { dragX = null; });
    shelf.addEventListener("click", (e) => { if (moved > 6) { e.preventDefault(); e.stopPropagation(); } }, true);
    addEventListener("resize", layout);
    layout(); place();
    requestAnimationFrame(tick);
  }

  // ---------- filters + search for grid and list ----------
  const items = [...document.querySelectorAll("[data-filter-item]")];
  if (items.length) {
    const pills = [...document.querySelectorAll(".pill")];
    const search = document.querySelector(".search");
    const empty = document.querySelector(".empty");
    const moreBtn = document.querySelector(".more");
    const pageSize = Number(document.body.dataset.pageSize || 0);
    let filter = "all", q = "", limit = pageSize || Infinity;

    const apply = () => {
      let shown = 0;
      for (const el of items) {
        const okF = filter === "all" || el.dataset.tags.split(" ").includes(filter);
        const okQ = !q || el.dataset.q.includes(q);
        const ok = okF && okQ && shown < limit;
        if (okF && okQ) shown++;
        el.hidden = !ok;
      }
      const matches = items.filter((el) => (filter === "all" || el.dataset.tags.split(" ").includes(filter)) && (!q || el.dataset.q.includes(q))).length;
      if (empty) empty.style.display = matches ? "none" : "block";
      if (moreBtn) moreBtn.hidden = matches <= limit;
    };
    pills.forEach((p) => p.addEventListener("click", () => {
      pills.forEach((x) => x.setAttribute("aria-pressed", x === p));
      filter = p.dataset.f;
      limit = pageSize || Infinity;
      apply();
    }));
    if (search) search.addEventListener("input", () => { q = search.value.trim().toLowerCase(); limit = pageSize || Infinity; apply(); });
    if (moreBtn) moreBtn.addEventListener("click", () => { limit += pageSize; apply(); });
    addEventListener("keydown", (e) => {
      if (e.key === "/" && search && document.activeElement !== search) { e.preventDefault(); search.focus(); }
    });
    apply();
  }
})();
