document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("table.data-table").forEach(setupTableSearch);
    document.querySelectorAll("table.data-table").forEach(setupTableSort);
    setupRowDetail();
    setupFormattingToolbars();
    setupDashboardNav();
    setupDashboardTopTabs();
    setupGenreTabs();
    setupStickyToolbar();
    setupToasts();
    setupPortalSearch();
    setupWhatsNewSlideshow();
    setupMarkdownRender();
});

/* Renders raw Markdown into HTML entirely client-side: the server only ever
   sends the source text (base64-encoded so no character in it can break out
   of the HTML attribute it sits in), and the browser converts it here with
   marked, then sanitizes the result with DOMPurify before it touches the
   DOM — the source may come from another user's blog post, so it's treated
   as untrusted regardless of how well-formed we expect it to be. */
function setupMarkdownRender() {
    document.querySelectorAll(".md-render[data-md-b64]").forEach((el) => {
        const source = new TextDecoder("utf-8").decode(
            Uint8Array.from(atob(el.dataset.mdB64), (c) => c.charCodeAt(0))
        );
        const html = marked.parse(source);
        el.innerHTML = DOMPurify.sanitize(html);
    });
}

/* Home page "What's New in RAID" slideshow: fades between blog/library
   slides on a timer, with arrow + dot controls that reset the timer. */
function setupWhatsNewSlideshow() {
    const root = document.getElementById("whatsnewSlideshow");
    if (!root) return;

    const track = root.querySelector(".whatsnew-slides");
    const slides = Array.from(track.children);

    /* Shuffle the slide order on every load so the feed doesn't always open
       on the same item — the server always renders blog posts before
       library books with the first post marked active, so that ordering
       has to be scrambled (and "active" reassigned) client-side. */
    for (let i = slides.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [slides[i], slides[j]] = [slides[j], slides[i]];
    }
    slides.forEach((slide) => {
        slide.classList.remove("active");
        track.appendChild(slide);
    });

    if (slides.length === 0) return;
    if (slides.length === 1) {
        slides[0].classList.add("active");
        root.querySelectorAll(".whatsnew-arrow, .whatsnew-dots").forEach((el) => el.remove());
        return;
    }
    slides[0].classList.add("active");

    const dotsContainer = root.querySelector(".whatsnew-dots");
    dotsContainer.innerHTML = slides
        .map((_, i) => `<button type="button" class="whatsnew-dot${i === 0 ? " active" : ""}" data-index="${i}" aria-label="Go to slide ${i + 1}"></button>`)
        .join("");
    const dots = Array.from(dotsContainer.querySelectorAll(".whatsnew-dot"));

    let current = 0;
    let timer = null;

    function show(index) {
        slides[current].classList.remove("active");
        dots[current].classList.remove("active");
        current = (index + slides.length) % slides.length;
        slides[current].classList.add("active");
        dots[current].classList.add("active");
    }

    function restart() {
        clearInterval(timer);
        timer = setInterval(() => show(current + 1), 5000);
    }

    root.querySelector(".whatsnew-prev").addEventListener("click", (e) => {
        e.preventDefault();
        show(current - 1);
        restart();
    });
    root.querySelector(".whatsnew-next").addEventListener("click", (e) => {
        e.preventDefault();
        show(current + 1);
        restart();
    });
    dots.forEach((dot) => {
        dot.addEventListener("click", () => {
            show(Number(dot.dataset.index));
            restart();
        });
    });

    root.addEventListener("mouseenter", () => clearInterval(timer));
    root.addEventListener("mouseleave", restart);

    restart();
}

/* Header-wide search box: debounced fetch to /search?q=..., grouped
   dropdown of matching blog posts, library books and people. */
function setupPortalSearch() {
    const input = document.getElementById("portalSearchInput");
    const results = document.getElementById("portalSearchResults");
    if (!input || !results) return;

    let debounceTimer = null;
    let activeRequest = 0;

    function closeResults() {
        results.hidden = true;
        results.innerHTML = "";
    }

    function escapeHtml(str) {
        return (str || "").replace(/[&<>"']/g, (c) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        }[c]));
    }

    function renderGroup(label, items, toHtml) {
        if (!items.length) return "";
        return `<div class="portal-search-group">
            <div class="portal-search-group-label">${label}</div>
            ${items.map(toHtml).join("")}
        </div>`;
    }

    function render(data) {
        const html = [
            renderGroup("Blog", data.posts, (p) => `<a class="portal-search-item" href="/blog/${p.id}"><span class="portal-search-item-title">${escapeHtml(p.title)}</span></a>`),
            renderGroup("Library", data.books, (b) => `<a class="portal-search-item" href="/library#book-${b.id}"><span class="portal-search-item-title">${escapeHtml(b.title)}</span><span class="portal-search-item-sub">${escapeHtml(b.author || "")}</span></a>`),
            renderGroup("People", data.people, (p) => `<a class="portal-search-item" href="mailto:${escapeHtml(p.email)}"><span class="portal-search-item-title">${escapeHtml(p.name || p.email)}</span><span class="portal-search-item-sub">${escapeHtml(p.email)}</span></a>`),
        ].join("");

        if (!html) {
            results.innerHTML = '<div class="portal-search-empty">No matches</div>';
        } else {
            results.innerHTML = html;
        }
        results.hidden = false;
    }

    input.addEventListener("input", () => {
        const q = input.value.trim();
        clearTimeout(debounceTimer);
        if (q.length < 2) {
            closeResults();
            return;
        }
        debounceTimer = setTimeout(() => {
            const requestId = ++activeRequest;
            fetch(`/search?q=${encodeURIComponent(q)}`)
                .then((r) => r.json())
                .then((data) => {
                    if (requestId === activeRequest) render(data);
                })
                .catch(() => {});
        }, 200);
    });

    input.addEventListener("focus", () => {
        if (results.innerHTML) results.hidden = false;
    });

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".portal-search")) closeResults();
    });

    input.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeResults();
            input.blur();
        }
    });
}

/* Uniform warning/notice popup: every flashed message (login errors, form
   confirmations, "not allowed" notices, etc.) shows the same way — a toast
   that fades in, sits for 3s, then fades out and removes itself. */
function setupToasts() {
    const messages = window.__flashMessages || [];
    if (!messages.length) return;

    const container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);

    messages.forEach(([category, message], i) => {
        setTimeout(() => showToast(container, message, category), i * 150);
    });
}

function showToast(container, message, category) {
    const toast = document.createElement("div");
    toast.className = `toast toast-${category || "info"}`;
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add("toast-visible"));

    setTimeout(() => {
        toast.classList.remove("toast-visible");
        toast.addEventListener("transitionend", () => toast.remove(), { once: true });
    }, 3000);
}

function setupDashboardNav() {
    const sidebar = document.querySelector(".dashboard-sidebar");
    if (!sidebar) return;

    const buttons = sidebar.querySelectorAll(".dashboard-nav-item");
    const sections = document.querySelectorAll(".dashboard-section");

    buttons.forEach((btn) => {
        btn.addEventListener("click", () => {
            buttons.forEach((b) => b.classList.toggle("active", b === btn));
            sections.forEach((section) => {
                section.hidden = section.dataset.section !== btn.dataset.target;
            });
        });
    });
}

/* Admin Dashboard's top-level split: "raid-system" (the app itself --
   Access Requests, Users, Guide, Audit Log) vs. "raid-server" (the
   machine it runs on -- Server Status, Terminal, File Explorer). No-op
   wherever the markup isn't present (every other dashboard page keeps
   its single flat sidebar via setupDashboardNav() above, untouched).
   Delegates actual section switching to that same function's click
   handlers -- this only decides which group of sidebar buttons is
   visible and clicks the first one in the newly-shown group. */
function setupDashboardTopTabs() {
    const tabs = document.querySelectorAll(".dashboard-top-tab");
    if (!tabs.length) return;

    const groups = document.querySelectorAll(".dashboard-nav-group");

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            tabs.forEach((t) => t.classList.toggle("active", t === tab));
            groups.forEach((group) => {
                group.hidden = group.dataset.navGroup !== tab.dataset.tab;
            });
            const firstButton = document.querySelector(
                '.dashboard-nav-group[data-nav-group="' + tab.dataset.tab + '"] .dashboard-nav-item'
            );
            if (firstButton) firstButton.click();
        });
    });
}

function setupFormattingToolbars() {
    document.querySelectorAll(".format-toolbar").forEach((toolbar) => {
        const textarea = document.getElementById(toolbar.dataset.target);
        if (!textarea) return;

        toolbar.querySelectorAll("button[data-wrap]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const [prefix, suffix] = btn.dataset.wrap.split("|");
                wrapSelection(textarea, prefix, suffix === undefined ? prefix : suffix);
            });
        });

        toolbar.querySelectorAll("button[data-prefix-line]").forEach((btn) => {
            btn.addEventListener("click", () => {
                prefixLines(textarea, btn.dataset.prefixLine);
            });
        });
    });
}

function wrapSelection(textarea, prefix, suffix) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const value = textarea.value;
    const selected = value.slice(start, end) || "text";
    textarea.value = value.slice(0, start) + prefix + selected + suffix + value.slice(end);
    textarea.focus();
    textarea.selectionStart = start + prefix.length;
    textarea.selectionEnd = start + prefix.length + selected.length;
}

function prefixLines(textarea, prefix) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const value = textarea.value;
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    let lineEnd = value.indexOf("\n", end);
    if (lineEnd === -1) lineEnd = value.length;
    const block = value.slice(lineStart, lineEnd);
    const updated = block
        .split("\n")
        .map((line) => (line ? prefix + line : line))
        .join("\n");
    textarea.value = value.slice(0, lineStart) + updated + value.slice(lineEnd);
    textarea.focus();
}

function setupRowDetail() {
    const modal = document.getElementById("detail-modal");
    if (!modal) return;

    const titleEl = modal.querySelector(".modal-title");
    const bodyEl = modal.querySelector(".modal-body");
    const actionsEl = modal.querySelector(".modal-actions");
    const closeBtn = modal.querySelector(".modal-close");

    const openModal = (data, row) => {
        titleEl.textContent = data.Title || Object.values(data)[0] || "Details";
        bodyEl.innerHTML = "";
        Object.entries(data).forEach(([key, value]) => {
            if (!value && value !== 0) return;
            const dt = document.createElement("dt");
            dt.textContent = key;
            const dd = document.createElement("dd");
            if (key === "TOC Link") {
                const link = document.createElement("a");
                link.href = value;
                link.target = "_blank";
                link.rel = "noopener";
                link.textContent = "View TOC";
                dd.append(link);
            } else {
                dd.textContent = value;
            }
            bodyEl.append(dt, dd);
        });

        if (actionsEl) {
            actionsEl.innerHTML = "";
            const requestUrl = row && row.dataset.requestUrl;
            if (requestUrl) {
                const form = document.createElement("form");
                form.method = "post";
                form.action = requestUrl;
                const btn = document.createElement("button");
                btn.type = "submit";
                btn.className = "modal-request-btn";
                if (row.dataset.requested === "1") {
                    btn.textContent = "Request pending";
                    btn.disabled = true;
                } else {
                    btn.textContent = "Request this book";
                }
                form.append(btn);
                actionsEl.append(form);
            }
        }

        modal.hidden = false;
    };

    const closeModal = () => {
        modal.hidden = true;
    };

    document.querySelectorAll("tr[data-detail]").forEach((row) => {
        row.addEventListener("click", () => {
            openModal(JSON.parse(row.dataset.detail), row);
        });
    });

    closeBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", (event) => {
        if (event.target === modal) closeModal();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) closeModal();
    });
}

function setupTableSearch(table) {
    if (table.dataset.noSearch !== undefined) return;

    const wrap = table.closest(".table-wrap") || table.parentElement;
    const rows = Array.from(table.tBodies[0] ? table.tBodies[0].rows : []);
    if (rows.length === 0) return;

    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = `Search ${rows.length} rows...`;
    search.className = "table-search";
    wrap.parentElement.insertBefore(search, wrap);

    const count = document.createElement("p");
    count.className = "row-count";
    wrap.parentElement.insertBefore(count, wrap.nextSibling);

    let term = "";
    let genre = "all";

    const applyFilters = () => {
        let visible = 0;
        rows.forEach((row) => {
            const matchesTerm = !term || row.textContent.toLowerCase().includes(term);
            const matchesGenre = genre === "all" || row.dataset.genre === genre;
            const match = matchesTerm && matchesGenre;
            row.style.display = match ? "" : "none";
            if (match) visible += 1;
        });
        count.textContent = `Showing ${visible} of ${rows.length}`;
    };

    search.addEventListener("input", () => {
        term = search.value.trim().toLowerCase();
        applyFilters();
    });

    table.tableFilter = {
        setGenre(value) {
            genre = value;
            applyFilters();
        },
    };

    applyFilters();
}

function setupTableSort(table) {
    if (table.dataset.noSort !== undefined) return;

    const headRow = table.tHead && table.tHead.rows[0];
    const tbody = table.tBodies[0];
    if (!headRow || !tbody) return;

    let sortCol = -1;
    let sortAsc = true;

    Array.from(headRow.cells).forEach((th, colIndex) => {
        th.classList.add("sortable");
        th.addEventListener("click", () => {
            sortAsc = sortCol === colIndex ? !sortAsc : true;
            sortCol = colIndex;

            Array.from(headRow.cells).forEach((cell, i) => {
                cell.classList.remove("sort-asc", "sort-desc");
                if (i === colIndex) cell.classList.add(sortAsc ? "sort-asc" : "sort-desc");
            });

            const rows = Array.from(tbody.rows);
            const cellText = (row) => (row.cells[colIndex] ? row.cells[colIndex].textContent.trim() : "");
            const allNumeric = rows.every((row) => cellText(row) === "" || !isNaN(parseFloat(cellText(row))));

            rows.sort((a, b) => {
                const av = cellText(a);
                const bv = cellText(b);
                let cmp;
                if (allNumeric) {
                    cmp = (parseFloat(av) || 0) - (parseFloat(bv) || 0);
                } else {
                    cmp = av.localeCompare(bv, undefined, { sensitivity: "base", numeric: true });
                }
                return sortAsc ? cmp : -cmp;
            });

            rows.forEach((row) => tbody.appendChild(row));
        });
    });
}

/* Library catalog: keeps the genre-tabs/search toolbar pinned to the top
   of the viewport while scrolling the (currently 591-row) table, and pins
   the table's own header row directly beneath it. Offsets are measured at
   runtime with getBoundingClientRect rather than hardcoded, since the
   toolbar's real height depends on font rendering/browser zoom — a fixed
   guess would leave a gap or overlap the header the moment that's off by
   even a couple of pixels. Recomputed on resize (e.g. rotating a tablet)
   since the search box and sync button can still reflow width even though
   the genre-tab strip itself no longer wraps (see .genre-tabs overflow-x
   in style.css). */
function setupStickyToolbar() {
    const toolbar = document.querySelector(".catalog-toolbar");
    const wrap = document.querySelector(".table-wrap-bleed");
    if (!toolbar || !wrap) return;

    const table = wrap.querySelector("table.data-table");
    const headRow = table && table.tHead && table.tHead.rows[0];
    if (!headRow) return;

    // setupTableSearch() inserts the search input as wrap's previous
    // sibling (after the toolbar), once per table — grab it if present.
    // It's only max-width:320px itself, so sticky-positioning the input
    // directly would leave everything to its right in that band
    // unoccluded (tall wrapped rows would show through above the table
    // header) — wrap it in a full-width bar and stick that instead.
    const search = wrap.previousElementSibling;
    const hasSearch = search && search !== toolbar && search.classList.contains("table-search");
    let searchBar = null;
    if (hasSearch) {
        searchBar = document.createElement("div");
        searchBar.className = "catalog-search-bar";
        search.classList.add("catalog-sticky-search");
        search.parentElement.insertBefore(searchBar, search);
        searchBar.appendChild(search);
    }

    const applyOffsets = () => {
        let stackHeight = toolbar.getBoundingClientRect().height;
        if (searchBar) {
            searchBar.style.top = `${stackHeight}px`;
            stackHeight += searchBar.getBoundingClientRect().height;
        }
        Array.from(headRow.cells).forEach((th) => {
            th.style.top = `${stackHeight}px`;
        });
    };

    applyOffsets();
    window.addEventListener("resize", applyOffsets);
}

function setupGenreTabs() {
    document.querySelectorAll(".genre-tabs").forEach((tabs) => {
        // The table isn't always a direct sibling of .genre-tabs itself, or
        // inside its immediate parent — on the library catalog page,
        // .genre-tabs sits inside a flex header row, and the table lives in
        // a *sibling* of that row (.table-wrap), not inside it. Walk
        // forward through .genre-tabs' own siblings, then its parent's
        // siblings, until a table.data-table turns up — works whether the
        // table is a near sibling of the tabs or one level further out.
        let table = null;
        for (let node = tabs; node && !table; node = node.parentElement) {
            for (let sib = node.nextElementSibling; sib && !table; sib = sib.nextElementSibling) {
                table = sib.matches("table.data-table") ? sib : sib.querySelector("table.data-table");
            }
        }
        if (!table) return;

        const buttons = tabs.querySelectorAll(".genre-tab");
        buttons.forEach((btn) => {
            btn.addEventListener("click", () => {
                buttons.forEach((b) => b.classList.toggle("active", b === btn));
                if (table.tableFilter) table.tableFilter.setGenre(btn.dataset.genre);
            });
        });
    });
}
