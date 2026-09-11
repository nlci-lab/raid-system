document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("table.data-table").forEach(setupTableSearch);
    document.querySelectorAll("table.data-table").forEach(setupTableSort);
    setupRowDetail();
    setupFormattingToolbars();
    setupChatPopovers();
    setupChatThread();
    setupDashboardNav();
    setupGenreTabs();
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
            renderGroup("Blog", data.posts, (p) => `<a class="portal-search-item" href="/blog/${p.id}">${escapeHtml(p.title)}</a>`),
            renderGroup("Library", data.books, (b) => `<a class="portal-search-item" href="/library#book-${b.id}">${escapeHtml(b.title)}<span class="portal-search-item-sub">${escapeHtml(b.author || "")}</span></a>`),
            renderGroup("People", data.people, (p) => `<a class="portal-search-item" href="mailto:${escapeHtml(p.email)}">${escapeHtml(p.name || p.email)}<span class="portal-search-item-sub">${escapeHtml(p.email)}</span></a>`),
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

function setupChatPopovers() {
    const popovers = document.querySelectorAll(".chat-popover");
    if (!popovers.length) return;

    document.addEventListener("click", (event) => {
        popovers.forEach((popover) => {
            if (popover.open && !popover.contains(event.target)) {
                popover.open = false;
            }
        });
    });

    popovers.forEach((popover) => {
        popover.addEventListener("toggle", () => {
            if (!popover.open) return;
            popovers.forEach((other) => {
                if (other !== popover) other.open = false;
            });
        });
    });
}

function setupChatThread() {
    const thread = document.getElementById("chat-thread");
    if (thread) thread.scrollTop = thread.scrollHeight;

    const fileInput = document.querySelector(".chat-attach-btn input[type=file]");
    const count = document.querySelector(".chat-attach-count");
    if (fileInput && count) {
        fileInput.addEventListener("change", () => {
            count.textContent = fileInput.files.length ? String(fileInput.files.length) : "";
        });
    }
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

function setupGenreTabs() {
    document.querySelectorAll(".genre-tabs").forEach((tabs) => {
        const table = (tabs.nextElementSibling && tabs.nextElementSibling.querySelector("table.data-table"))
            || tabs.parentElement.querySelector("table.data-table");
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
