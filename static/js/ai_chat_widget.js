// RAID Bot floating widget — global chat bubble injected on every page for
// logged-in staff (see base.html for the level gate). Conversation history
// and open/closed state persist in sessionStorage so navigating between
// pages doesn't reset the chat (full page loads, not an SPA, would
// otherwise lose everything client-side on every click).
(function () {
    const widget = document.getElementById("aiBotWidget");
    if (!widget) return;

    const fab = document.getElementById("aiBotFab");
    const closeBtn = document.getElementById("aiBotCloseBtn");
    const newChatBtn = document.getElementById("aiBotNewChatBtn");
    const scrollEl = document.getElementById("aiBotScroll");
    const emptyEl = document.getElementById("aiBotEmpty");
    const messagesEl = document.getElementById("aiBotMessages");
    const form = document.getElementById("aiBotForm");
    const input = document.getElementById("aiBotInput");
    const sendBtn = document.getElementById("aiBotSendBtn");

    const STORAGE_HISTORY = "aiBotHistory";
    const STORAGE_OPEN = "aiBotOpen";

    let conversationHistory = [];
    try {
        conversationHistory = JSON.parse(sessionStorage.getItem(STORAGE_HISTORY) || "[]");
    } catch (_) {
        conversationHistory = [];
    }
    let isSending = false;

    function persistHistory() {
        try {
            sessionStorage.setItem(STORAGE_HISTORY, JSON.stringify(conversationHistory));
        } catch (_) { /* storage full/unavailable — chat still works, just won't persist */ }
    }

    function setOpen(open) {
        widget.classList.toggle("open", open);
        try {
            sessionStorage.setItem(STORAGE_OPEN, open ? "1" : "0");
        } catch (_) {}
        if (open) {
            input.focus();
            scrollToBottom();
        }
    }

    fab.addEventListener("click", () => setOpen(true));
    closeBtn.addEventListener("click", () => setOpen(false));
    newChatBtn.addEventListener("click", startNewChat);

    function updateSendBtnState() {
        sendBtn.disabled = isSending || input.value.trim().length === 0;
    }

    input.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 100) + "px";
        updateSendBtnState();
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    form.addEventListener("submit", sendMessage);

    function hideEmptyState() {
        emptyEl.style.display = "none";
    }

    function showEmptyState() {
        emptyEl.style.display = "flex";
    }

    function scrollToBottom() {
        scrollEl.scrollTop = scrollEl.scrollHeight;
    }

    function sparkleIconSvg() {
        return '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z"></path></svg>';
    }

    function errorIconSvg() {
        return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
    }

    // Same marked + DOMPurify pattern main.js's setupMarkdownRender() uses
    // for blog/guide content -- RAID Bot's replies are markdown (it uses
    // **bold**, lists, etc.), so render them properly instead of showing
    // literal asterisks. Sanitized regardless, same as any other markdown
    // source in this app, even though it's local-only model output.
    function renderMarkdown(text) {
        if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
            return text; // graceful fallback if the vendor scripts somehow didn't load
        }
        return DOMPurify.sanitize(marked.parse(text));
    }

    function createMessageRow(role) {
        const row = document.createElement("div");
        row.className = "ai-bot-msg ai-bot-msg-" + role;

        if (role === "user") {
            const bubble = document.createElement("div");
            bubble.className = "ai-bot-msg-bubble";
            row.appendChild(bubble);
            return { row, content: bubble };
        }

        const avatar = document.createElement("div");
        avatar.className = "ai-bot-msg-avatar" + (role === "error" ? " ai-bot-msg-avatar-error" : "");
        avatar.innerHTML = role === "error" ? errorIconSvg() : sparkleIconSvg();

        const content = document.createElement("div");
        content.className = "ai-bot-msg-content" + (role === "error" ? " ai-bot-msg-error-text" : "");

        row.appendChild(avatar);
        row.appendChild(content);
        return { row, content };
    }

    function addMessageToUI(role, text) {
        hideEmptyState();
        const { row, content } = createMessageRow(role);
        if (role === "assistant") {
            content.innerHTML = renderMarkdown(text);
        } else {
            content.textContent = text; // user's own input / error text -- never markdown-rendered
        }
        messagesEl.appendChild(row);
        scrollToBottom();
        return row;
    }

    function addLoadingRow() {
        hideEmptyState();
        const { row, content } = createMessageRow("assistant");
        row.classList.add("ai-bot-msg-pending");
        content.innerHTML =
            '<span class="ai-bot-loading"></span><span class="ai-bot-loading"></span><span class="ai-bot-loading"></span>';
        messagesEl.appendChild(row);
        scrollToBottom();
        return { row, content };
    }

    function markRowAsError(row, content, message) {
        row.className = "ai-bot-msg ai-bot-msg-error";
        const avatar = row.querySelector(".ai-bot-msg-avatar");
        avatar.classList.add("ai-bot-msg-avatar-error");
        avatar.innerHTML = errorIconSvg();
        content.className = "ai-bot-msg-content ai-bot-msg-error-text";
        content.textContent = message;
    }

    async function sendMessage(event) {
        event.preventDefault();
        if (isSending) return;

        const message = input.value.trim();
        if (!message) return;

        addMessageToUI("user", message);
        conversationHistory.push({ role: "user", content: message });
        persistHistory();

        input.value = "";
        input.style.height = "auto";
        isSending = true;
        updateSendBtnState();

        const pending = addLoadingRow();

        try {
            const response = await fetch("/ai-chat/send", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ messages: conversationHistory })
            });

            if (!response.ok) {
                let errorMsg = "Unknown error";
                try {
                    const data = await response.json();
                    errorMsg = data.error || errorMsg;
                } catch (_) {}
                markRowAsError(pending.row, pending.content, errorMsg);
            } else {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullReply = "";
                let gotFirstChunk = false;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const textChunk = decoder.decode(value, { stream: true });
                    if (!textChunk) continue;
                    if (!gotFirstChunk) {
                        pending.row.classList.remove("ai-bot-msg-pending");
                        pending.content.textContent = "";
                        gotFirstChunk = true;
                    }
                    fullReply += textChunk;
                    // Re-parsing markdown on every chunk is cheap at this
                    // scale (network-chunk-paced, not per-character) --
                    // mid-word markdown (e.g. an unclosed "**") just
                    // renders literally until the next chunk completes it.
                    pending.content.innerHTML = renderMarkdown(fullReply);
                    scrollToBottom();
                }

                if (!gotFirstChunk) {
                    markRowAsError(pending.row, pending.content, "No response received.");
                } else {
                    conversationHistory.push({ role: "assistant", content: fullReply });
                    persistHistory();
                }
            }
        } catch (err) {
            markRowAsError(pending.row, pending.content, "Network error: " + err.message);
        } finally {
            isSending = false;
            updateSendBtnState();
            scrollToBottom();
        }
    }

    function startNewChat() {
        conversationHistory = [];
        persistHistory();
        messagesEl.innerHTML = "";
        showEmptyState();
        input.value = "";
        input.style.height = "auto";
        updateSendBtnState();
        input.focus();
    }

    // Restore any conversation from a previous page on this same session.
    for (const msg of conversationHistory) {
        addMessageToUI(msg.role, msg.content);
    }

    let wasOpen = false;
    try {
        wasOpen = sessionStorage.getItem(STORAGE_OPEN) === "1";
    } catch (_) {}
    if (wasOpen) setOpen(true);

    updateSendBtnState();
})();
