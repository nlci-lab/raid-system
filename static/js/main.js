document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("table.data-table").forEach(setupTableSearch);
    document.querySelectorAll("table.data-table").forEach(setupTableSort);
    setupRowDetail();
    setupFormattingToolbars();
    setupChatPopovers();
    setupChatThread();
    setupDashboardNav();
    setupGenreTabs();
});

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
