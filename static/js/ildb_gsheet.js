// Google Sheets-style grid for the ILDB internal database viewer.
// Renders a table -> {columns, rows} map as a spreadsheet with lettered
// columns, numbered rows, a formula bar and sheet tabs. Supports multiple
// independent instances on the same page — each `.gsheet[data-sheets-var]`
// element is initialized separately, reading its data from the named
// window global and scoping all DOM lookups to itself.
(function () {
    var TRAIL_ROWS = 12;
    var TRAIL_COLS = 3;
    var DEFAULT_COL_WIDTH = 130;
    var ROWNUM_WIDTH = 46;

    function colLetter(n) {
        var s = "";
        n = n + 1;
        while (n > 0) {
            var rem = (n - 1) % 26;
            s = String.fromCharCode(65 + rem) + s;
            n = Math.floor((n - 1) / 26);
        }
        return s;
    }

    function escapeHtml(v) {
        return String(v)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function initGsheet(container) {
        var SHEETS = window[container.dataset.sheetsVar] || {};

        var grid = container.querySelector(".gsheet-grid");
        var gridWrap = container.querySelector(".gsheet-gridwrap");
        var tabsBar = container.querySelector(".gsheet-tabs");
        var cellRefEl = container.querySelector(".gsheet-cellref");
        var formulaInput = container.querySelector(".gsheet-formula-input");
        var rowCountEl = container.querySelector(".gsheet-rowcount");
        var searchInput = container.querySelector(".gsheet-search");
        var searchCountEl = container.querySelector(".gsheet-search-count");

        if (!grid) return;

        var active = window[container.dataset.activeVar];
        var selected = { r: 0, c: 0 };
        var matches = [];
        var matchIndex = -1;

        function buildGrid(tableName) {
            var sheet = SHEETS[tableName];
            if (!sheet) return;
            active = tableName;
            selected = { r: 0, c: 0 };
            matches = [];
            matchIndex = -1;
            if (searchInput) searchInput.value = "";
            updateSearchCount();

            var colCount = sheet.columns.length + TRAIL_COLS;
            var rowCount = sheet.rows.length + 1 + TRAIL_ROWS; // +1 for the header-name row

            var colgroup = '<colgroup><col style="width:' + ROWNUM_WIDTH + 'px">';
            for (var c = 0; c < colCount; c++) {
                colgroup += '<col style="width:' + DEFAULT_COL_WIDTH + 'px" data-col="' + c + '">';
            }
            colgroup += "</colgroup>";

            var thead = "<thead><tr><th class=\"gsheet-corner\"></th>";
            for (var hc = 0; hc < colCount; hc++) {
                thead += '<th class="gsheet-colhead" data-c="' + hc + '">' + colLetter(hc) +
                    '<span class="gsheet-resize-handle" data-c="' + hc + '"></span></th>';
            }
            thead += "</tr></thead>";

            var bodyRows = [];
            // Row 1: the actual column names, as plain sheet data (bold, like a typed header row).
            var headCells = "";
            for (var i = 0; i < colCount; i++) {
                var val = i < sheet.columns.length ? sheet.columns[i] : "";
                headCells += cellHtml(0, i, val, true);
            }
            bodyRows.push('<tr data-r="0">' + rowNumCell(1) + headCells + "</tr>");

            for (var r = 0; r < sheet.rows.length; r++) {
                var row = sheet.rows[r];
                var cells = "";
                for (var c2 = 0; c2 < colCount; c2++) {
                    var v = c2 < row.length ? row[c2] : "";
                    cells += cellHtml(r + 1, c2, v, false);
                }
                bodyRows.push('<tr data-r="' + (r + 1) + '">' + rowNumCell(r + 2) + cells + "</tr>");
            }

            for (var tr = 0; tr < TRAIL_ROWS; tr++) {
                var rIdx = sheet.rows.length + 1 + tr;
                var blanks = "";
                for (var tc = 0; tc < colCount; tc++) {
                    blanks += cellHtml(rIdx, tc, "", false);
                }
                bodyRows.push('<tr data-r="' + rIdx + '">' + rowNumCell(rIdx + 1) + blanks + "</tr>");
            }

            grid.innerHTML = colgroup + thead + "<tbody>" + bodyRows.join("") + "</tbody>";

            attachHandlers();
            selectCell(0, 0, true);
            if (rowCountEl) {
                rowCountEl.textContent = sheet.rows.length + " rows, " + sheet.columns.length + " columns";
            }
            if (gridWrap) gridWrap.scrollTop = 0;
        }

        function rowNumCell(n) {
            return '<th class="gsheet-rownum" data-r-label="' + n + '">' + n + "</th>";
        }

        function cellHtml(r, c, value, isHeaderRow) {
            var text = value === null || value === undefined ? "" : String(value);
            var cls = "gsheet-cell" + (isHeaderRow ? " gsheet-headerrow-cell" : "");
            return '<td class="' + cls + '" data-r="' + r + '" data-c="' + c + '">' +
                (text ? escapeHtml(text) : "") + "</td>";
        }

        function attachHandlers() {
            grid.querySelectorAll("td.gsheet-cell").forEach(function (td) {
                td.addEventListener("mousedown", function () {
                    selectCell(parseInt(td.dataset.r, 10), parseInt(td.dataset.c, 10));
                });
            });

            grid.querySelectorAll(".gsheet-resize-handle").forEach(function (handle) {
                var startX, startWidth, col;
                handle.addEventListener("mousedown", function (e) {
                    col = grid.querySelector('col[data-col="' + handle.dataset.c + '"]');
                    if (!col) return;
                    startX = e.pageX;
                    startWidth = col.getBoundingClientRect().width;
                    document.body.classList.add("col-resizing");
                    handle.classList.add("resizing");

                    function onMove(ev) {
                        col.style.width = Math.max(60, startWidth + (ev.pageX - startX)) + "px";
                    }
                    function onUp() {
                        document.body.classList.remove("col-resizing");
                        handle.classList.remove("resizing");
                        document.removeEventListener("mousemove", onMove);
                        document.removeEventListener("mouseup", onUp);
                    }
                    document.addEventListener("mousemove", onMove);
                    document.addEventListener("mouseup", onUp);
                    e.preventDefault();
                    e.stopPropagation();
                });
            });
        }

        function selectCell(r, c, skipScroll) {
            var prev = grid.querySelector(".gsheet-cell.selected");
            if (prev) prev.classList.remove("selected");
            grid.querySelectorAll(".gsheet-colhead.active, .gsheet-rownum.active").forEach(function (el) {
                el.classList.remove("active");
            });

            var td = grid.querySelector('td.gsheet-cell[data-r="' + r + '"][data-c="' + c + '"]');
            if (!td) return;
            td.classList.add("selected");
            selected = { r: r, c: c };

            var th = grid.querySelector('.gsheet-colhead[data-c="' + c + '"]');
            if (th) th.classList.add("active");
            var rowTh = grid.querySelector('tr[data-r="' + r + '"] .gsheet-rownum');
            if (rowTh) rowTh.classList.add("active");

            if (cellRefEl) cellRefEl.textContent = colLetter(c) + (r + 1);
            if (formulaInput) formulaInput.value = td.textContent;

            if (!skipScroll) {
                td.scrollIntoView({ block: "nearest", inline: "nearest" });
            }
        }

        function updateSearchCount() {
            if (!searchCountEl) return;
            if (!matches.length) {
                searchCountEl.textContent = "";
                return;
            }
            searchCountEl.textContent = (matchIndex + 1) + " of " + matches.length;
        }

        function runSearch(query) {
            grid.querySelectorAll(".gsheet-cell.match, .gsheet-cell.match-current").forEach(function (el) {
                el.classList.remove("match", "match-current");
            });
            matches = [];
            matchIndex = -1;

            var q = query.trim().toLowerCase();
            if (!q) {
                updateSearchCount();
                return;
            }
            grid.querySelectorAll("td.gsheet-cell").forEach(function (td) {
                if (td.textContent.toLowerCase().indexOf(q) !== -1) {
                    td.classList.add("match");
                    matches.push(td);
                }
            });
            if (matches.length) {
                matchIndex = 0;
                gotoMatch();
            }
            updateSearchCount();
        }

        function gotoMatch() {
            matches.forEach(function (el) { el.classList.remove("match-current"); });
            if (matchIndex < 0 || matchIndex >= matches.length) return;
            var td = matches[matchIndex];
            td.classList.add("match-current");
            td.scrollIntoView({ block: "center", inline: "center" });
            selectCell(parseInt(td.dataset.r, 10), parseInt(td.dataset.c, 10), true);
            updateSearchCount();
        }

        if (searchInput) {
            searchInput.addEventListener("input", function () {
                runSearch(searchInput.value);
            });
            searchInput.addEventListener("keydown", function (e) {
                if (e.key !== "Enter" || !matches.length) return;
                e.preventDefault();
                matchIndex = e.shiftKey
                    ? (matchIndex - 1 + matches.length) % matches.length
                    : (matchIndex + 1) % matches.length;
                gotoMatch();
            });
        }

        if (tabsBar) {
            tabsBar.querySelectorAll(".gsheet-tab").forEach(function (tab) {
                tab.addEventListener("click", function () {
                    tabsBar.querySelectorAll(".gsheet-tab").forEach(function (t) { t.classList.remove("active"); });
                    tab.classList.add("active");
                    buildGrid(tab.dataset.table);
                    var url = new URL(window.location.href);
                    url.searchParams.set("table", tab.dataset.table);
                    window.history.replaceState(null, "", url);
                });
            });
        }

        document.addEventListener("keydown", function (e) {
            if (container.offsetParent === null) return;
            if (document.activeElement === searchInput) return;
            var sheet = SHEETS[active];
            if (!sheet) return;
            var maxC = sheet.columns.length + TRAIL_COLS - 1;
            var maxR = sheet.rows.length + TRAIL_ROWS;
            var r = selected.r, c = selected.c;
            var moved = true;
            if (e.key === "ArrowUp") r = Math.max(0, r - 1);
            else if (e.key === "ArrowDown" || e.key === "Enter") r = Math.min(maxR, r + 1);
            else if (e.key === "ArrowLeft") c = Math.max(0, c - 1);
            else if (e.key === "ArrowRight" || e.key === "Tab") c = Math.min(maxC, c + 1);
            else moved = false;
            if (moved) {
                e.preventDefault();
                selectCell(r, c);
            }
        });

        if (!SHEETS[active]) {
            active = Object.keys(SHEETS)[0];
        }
        if (active) buildGrid(active);
    }

    document.querySelectorAll(".gsheet[data-sheets-var]").forEach(initGsheet);
})();
