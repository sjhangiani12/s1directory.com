(() => {
  // ---------- light / dark toggle (follows the system until clicked) ----------
  const themeBtn = document.querySelector(".theme");
  if (themeBtn) {
    const sys = matchMedia("(prefers-color-scheme: dark)");
    const isDark = () => (document.documentElement.dataset.theme || (sys.matches ? "dark" : "light")) === "dark";
    const label = () => themeBtn.setAttribute("aria-label", isDark() ? "Switch to light mode" : "Switch to dark mode");
    themeBtn.addEventListener("click", () => {
      const next = isDark() ? "light" : "dark";
      const swap = () => {
        document.documentElement.dataset.theme = next;
        try { localStorage.setItem("theme", next); } catch (e) {}
        label();
      };
      if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return swap();
      const r = themeBtn.getBoundingClientRect(), root = document.documentElement;
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      root.style.setProperty("--tx", x + "px");
      root.style.setProperty("--ty", y + "px");
      root.style.setProperty("--tr", Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y)) + "px");
      root.classList.add("theme-swap");
      document.startViewTransition(swap).finished.finally(() => root.classList.remove("theme-swap"));
    });
    sys.addEventListener("change", label);
    label();
  }

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
    // hover label: name and IPO above the book under the pointer, following it as the shelf drifts
    const cap = track.closest(".shelf").querySelector(".shelf-cap");
    let hovered = null;
    const showCap = (b) => {
      hovered = b;
      if (!b) { cap.classList.remove("on"); return; }
      cap.querySelector("b").textContent = b.dataset.name;
      cap.querySelector("span").textContent = b.dataset.meta;
      cap.classList.add("on");
      placeCap();
    };
    const placeCap = () => {
      if (!hovered) return;
      const s = track.closest(".shelf").getBoundingClientRect(), r = hovered.getBoundingClientRect();
      cap.style.left = `${r.left + r.width * 0.52 - s.left}px`;
      cap.style.top = `${r.top - s.top - 4}px`;
    };
    if (matchMedia("(hover: hover)").matches) {
      books.forEach((b) => {
        b.addEventListener("pointerenter", () => showCap(b));
        b.addEventListener("pointerleave", () => { if (hovered === b) showCap(null); });
      });
    }
    books.forEach((b) => {
      b.addEventListener("focus", () => showCap(b));
      b.addEventListener("blur", () => showCap(null));
    });
    const tick = (t) => {
      const dt = last ? Math.min(t - last, 50) : 16;
      last = t;
      speed += (target - speed) * 0.06;
      offset += speed * dt * 0.06;
      place();
      placeCap();
      requestAnimationFrame(tick);
    };
    const shelf = track.closest(".shelf");
    shelf.addEventListener("mouseenter", () => { if (!reduce) target = 0.04; });
    shelf.addEventListener("mouseleave", () => { if (!reduce) target = 0.35; });
    // drag / wheel to scrub
    let dragX = null, moved = 0;
    shelf.addEventListener("pointerdown", (e) => { dragX = e.clientX; moved = 0; });
    shelf.addEventListener("pointermove", (e) => {
      if (dragX === null) return;
      const dx = e.clientX - dragX; dragX = e.clientX; moved += Math.abs(dx);
      if (moved > 6 && !shelf.hasPointerCapture(e.pointerId)) shelf.setPointerCapture(e.pointerId);
      offset -= dx * 1.4;
    });
    const endDrag = () => { dragX = null; };
    shelf.addEventListener("pointerup", endDrag);
    shelf.addEventListener("pointercancel", endDrag);
    shelf.addEventListener("click", (e) => { if (moved > 6) { e.preventDefault(); e.stopPropagation(); } }, true);
    addEventListener("book-open", () => { target = speed = 0; });
    addEventListener("pageshow", (e) => { if (e.persisted && !reduce) target = 0.35; });
    addEventListener("resize", layout);
    layout();
    offset = -spacing * 1.25;  // the first slot sits in the faded edge; start the lead book fully in view
    place();
    requestAnimationFrame(tick);
  }

  // ---------- books swing open, then the page turns ----------
  document.addEventListener("click", (e) => {
    const link = e.target.closest("a.card, a.book3d");
    if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (reduce) return;
    const book = link.classList.contains("book3d") ? link : link.querySelector(".bk");
    if (!book || book.classList.contains("open")) return;
    e.preventDefault();
    book.classList.add("open");
    dispatchEvent(new Event("book-open"));
    setTimeout(() => { location.href = link.href; }, 420);
  });
  addEventListener("pageshow", (e) => {
    if (e.persisted) document.querySelectorAll(".open").forEach((el) => el.classList.remove("open"));
  });

  // ---------- S-1 reader: unpack the filing, contents, progress ----------
  const reader = document.querySelector(".reader");
  if (reader) {
    const doc = reader.querySelector(".rdoc"), list = reader.querySelector(".rtoc-list");
    const toc = reader.querySelector(".rtoc"), tocBtn = reader.querySelector(".rtoc-btn");
    const prog = reader.querySelector(".rprog"), top = reader.querySelector(".rtop");
    const key = "pos:" + location.pathname;
    const unpack = async (res) => {
      const buf = new Uint8Array(await res.arrayBuffer());
      if (buf[0] !== 0x1f || buf[1] !== 0x8b) return JSON.parse(new TextDecoder().decode(buf));  // server already unzipped it
      const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));
      return JSON.parse(await new Response(stream).text());
    };
    const NUM = /^[\s$()\u2014\u2013\-.,%\d]+$/;
    fetch(reader.dataset.src).then(unpack).then((d) => {
      doc.innerHTML = d.html;
      doc.querySelectorAll("table").forEach((t) => {
        const w = document.createElement("div"); w.className = "tw";
        t.replaceWith(w); w.appendChild(t);
        t.querySelectorAll("td").forEach((td) => { const x = td.textContent.trim(); if (x && NUM.test(x)) td.classList.add("num"); });
      });
      doc.querySelectorAll('a[href^="/"]').forEach((a) => { a.href = "https://www.sec.gov" + a.getAttribute("href"); a.target = "_blank"; });
      const heads = (d.toc && d.toc.length ? d.toc.map(([id]) => document.getElementById(id)) : [...doc.querySelectorAll("h2")]).filter(Boolean);
      heads.forEach((h, i) => { if (!h.id) h.id = "s" + (i + 1); });
      // group the filing into sections at each contents heading; flag the legal boilerplate
      const LEGAL = /forward-looking|where you can find|legal matters|^experts|underwriting|plan of distribution|description of (capital stock|share capital|securities)|shares eligible|tax consequences|taxation|enforce|change in (the )?(independent )?account|power of attorney|signatures|exhibit|information not required|indemnification|undertakings|unregistered securities|expenses of issuance|industry,? market|market,? industry|defined terms|notice to investors|about this prospectus|presentation of (financial|information)|basis of presentation|conventions|trademarks|table of contents|dealer prospectus|until .* all dealers/i;
      const topHeads = heads.filter((h) => h.parentElement === doc);
      if (topHeads.length) {
        const wrap = (nodes, legal, title) => {
          const sec = document.createElement("section");
          sec.className = "rsec" + (legal ? " legal" : "");
          if (title) sec.dataset.title = title;
          nodes[0].before(sec); nodes.forEach((n) => sec.appendChild(n));
          return sec;
        };
        const kids = [...doc.childNodes], starts = new Set(topHeads);
        let group = [], cur = null;
        const flush = () => { if (group.length) wrap(group, cur ? LEGAL.test(cur.textContent) : true, cur?.textContent || "Cover page"); group = []; };
        for (const n of kids) { if (starts.has(n)) { flush(); cur = n; } group.push(n); }
        flush();
      }
      const legalCount = doc.querySelectorAll(".rsec.legal").length;
      const tog = reader.querySelector(".rlegal");
      if (legalCount && tog) {
        tog.hidden = false;
        const setLegal = (hide) => {
          reader.classList.toggle("hide-legal", hide);
          tog.setAttribute("aria-pressed", String(hide));
          tog.textContent = hide ? `Show legal boilerplate (${legalCount})` : "Hide legal boilerplate";
          try { localStorage.setItem("hideLegal", hide ? "1" : "0"); } catch (e) {}
        };
        let pref = "1"; try { pref = localStorage.getItem("hideLegal") ?? "1"; } catch (e) {}
        setLegal(pref === "1");
        tog.addEventListener("click", () => setLegal(!reader.classList.contains("hide-legal")));
      }
      list.innerHTML = heads.map((h) => `<a href="#${h.id}"${h.closest(".rsec.legal") ? ' class="legal"' : ""}>${h.textContent}</a>`).join("") || "<span>No sections found</span>";
      list.addEventListener("click", (e) => {
        const a = e.target.closest("a.legal");
        if (a) document.getElementById(a.hash.slice(1))?.closest(".rsec")?.classList.add("open");
      });
      const links = new Map([...list.querySelectorAll("a")].map((a) => [a.hash.slice(1), a]));
      let current;
      const spy = new IntersectionObserver((es) => {
        for (const en of es) if (en.isIntersecting) {
          current?.removeAttribute("aria-current");
          current = links.get(en.target.id);
          current?.setAttribute("aria-current", "true");
          if (current && !toc.classList.contains("open")) current.scrollIntoView({ block: "nearest" });
        }
      }, { rootMargin: "0px 0px -75% 0px" });
      heads.forEach((h) => spy.observe(h));
      list.addEventListener("click", (e) => { if (e.target.closest("a")) toc.classList.remove("open"); });
      try { const y = Number(localStorage.getItem(key)); if (y > 400 && !location.hash) scrollTo(0, y); } catch (e) {}
      if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
    }).catch(() => {
      doc.innerHTML = `<p>This filing could not be opened here. <a href="${reader.querySelector(".rmeta a").href}">Read it on SEC EDGAR</a>.</p>`;
    });
    let ticking = false, saveT;
    addEventListener("scroll", () => {
      if (ticking) return; ticking = true;
      requestAnimationFrame(() => {
        const h = document.documentElement.scrollHeight - innerHeight;
        prog.style.transform = `scaleX(${h > 0 ? scrollY / h : 0})`;
        top.classList.toggle("on", scrollY > 1200);
        ticking = false;
      });
      clearTimeout(saveT); saveT = setTimeout(() => { try { localStorage.setItem(key, String(Math.round(scrollY))); } catch (e) {} }, 400);
    }, { passive: true });
    tocBtn.addEventListener("click", () => toc.classList.toggle("open"));
    top.addEventListener("click", () => scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" }));
    addEventListener("keydown", (e) => { if (e.key === "Escape") toc.classList.remove("open"); });
  }

  // ---------- search for grid and list ----------
  // Every word in the query must appear in the item's index (data-q), in any order.
  const items = [...document.querySelectorAll("[data-filter-item]")];
  const search = document.querySelector(".search");
  if (items.length && search) {
    const norm = (t) => t.toLowerCase().replace(/[-.]/g, "").replace(/[^a-z0-9 ]+/g, "").replace(/\s+/g, " ").trim();
    const index = items.map((el) => el.dataset.q);
    const empty = document.querySelector(".empty");
    const moreBtn = document.querySelector(".more");
    const pageSize = Number(document.body.dataset.pageSize || 0);
    let words = [], limit = pageSize || Infinity;

    const apply = () => {
      let matches = 0;
      for (let i = 0; i < items.length; i++) {
        const ok = words.every((w) => index[i].includes(w));
        if (ok) matches++;
        items[i].hidden = !ok || matches > limit;
      }
      if (empty) empty.style.display = matches ? "none" : "block";
      if (moreBtn) moreBtn.hidden = matches <= limit;
    };
    search.addEventListener("input", () => {
      const q = norm(search.value);
      words = q ? q.split(" ") : [];
      limit = pageSize || Infinity;
      apply();
    });
    if (moreBtn) moreBtn.addEventListener("click", () => {
      const before = new Set(items.filter((el) => !el.hidden));
      limit += pageSize;
      apply();
      let k = 0;
      for (const el of items) {
        if (el.hidden || before.has(el)) continue;
        el.style.setProperty("--k", k++);
        el.classList.remove("in"); void el.offsetWidth; el.classList.add("in");
      }
    });
    addEventListener("keydown", (e) => {
      if (e.key === "/" && document.activeElement !== search) { e.preventDefault(); search.focus(); }
      if (e.key === "Escape" && document.activeElement === search) { search.value = ""; search.dispatchEvent(new Event("input")); }
    });
    apply();
  }
})();
