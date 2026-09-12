/* Admin Dashboard > File Explorer: browses PROJECT_ROOT via
   /dashboard/admin/files and previews text files via
   /dashboard/admin/files/read. Read-only — see apps/dashboard/__init__.py
   for why editing/deleting isn't duplicated here (the Terminal covers it). */
(function () {
    const listing = document.getElementById("feListing");
    if (!listing) return;

    const breadcrumb = document.getElementById("feBreadcrumb");
    const preview = document.getElementById("fePreview");
    const previewName = document.getElementById("fePreviewName");

    function formatSize(bytes) {
        if (bytes === null || bytes === undefined) return "";
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    function renderBreadcrumb(path) {
        const parts = path ? path.split("/") : [];
        let acc = "";
        const links = [{ label: "root", path: "" }];
        parts.forEach((part) => {
            acc = acc ? acc + "/" + part : part;
            links.push({ label: part, path: acc });
        });
        breadcrumb.innerHTML = links
            .map((l) => '<a href="#" data-path="' + l.path.replace(/"/g, "&quot;") + '">' + l.label + "</a>")
            .join(" / ");
        breadcrumb.querySelectorAll("a").forEach((a) => {
            a.addEventListener("click", (e) => {
                e.preventDefault();
                loadDir(a.dataset.path);
            });
        });
    }

    function renderListing(data) {
        preview.hidden = true;
        previewName.textContent = "";
        const rows = [];
        if (data.parent !== null) {
            rows.push(
                '<div class="fe-row" data-dir="true" data-path="' + (data.parent || "") + '">' +
                '<span class="fe-icon">⬆️</span><span class="fe-name">.. (up)</span></div>'
            );
        }
        if (!data.entries.length) {
            rows.push('<p class="ai-bot-dash-note">Empty directory.</p>');
        }
        data.entries.forEach((entry) => {
            const path = (data.path ? data.path + "/" : "") + entry.name;
            rows.push(
                '<div class="fe-row" data-dir="' + entry.is_dir + '" data-path="' + path.replace(/"/g, "&quot;") + '">' +
                '<span class="fe-icon">' + (entry.is_dir ? "📁" : "📄") + "</span>" +
                '<span class="fe-name">' + entry.name + "</span>" +
                '<span class="fe-size">' + formatSize(entry.size) + "</span>" +
                '<span class="fe-modified">' + (entry.modified || "") + "</span>" +
                "</div>"
            );
        });
        listing.innerHTML = rows.join("");
        listing.querySelectorAll(".fe-row").forEach((row) => {
            row.addEventListener("click", () => {
                if (row.dataset.dir === "true") {
                    loadDir(row.dataset.path);
                } else {
                    loadFile(row.dataset.path);
                }
            });
        });
    }

    async function loadDir(path) {
        listing.innerHTML = "<p class=\"ai-bot-dash-note\">Loading…</p>";
        try {
            const res = await fetch("/dashboard/admin/files?path=" + encodeURIComponent(path || ""));
            const data = await res.json();
            if (data.error) {
                listing.innerHTML = "<p class=\"ai-bot-dash-note\">" + data.error + "</p>";
                return;
            }
            renderBreadcrumb(data.path);
            renderListing(data);
        } catch (err) {
            listing.innerHTML = "<p class=\"ai-bot-dash-note\">Request failed: " + err.message + "</p>";
        }
    }

    async function loadFile(path) {
        previewName.textContent = path;
        preview.hidden = false;
        preview.textContent = "Loading…";
        try {
            const res = await fetch("/dashboard/admin/files/read?path=" + encodeURIComponent(path));
            const data = await res.json();
            preview.textContent = data.error || data.content;
        } catch (err) {
            preview.textContent = "Request failed: " + err.message;
        }
    }

    loadDir("");
})();
