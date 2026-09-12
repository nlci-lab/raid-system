/* Admin Dashboard > Terminal: runs a shell command on the server via
   /dashboard/admin/terminal and prints the result, console-style. No
   restrictions server-side on what can be typed here — see the comment on
   run_terminal_command() in apps/dashboard/__init__.py. */
(function () {
    const form = document.getElementById("terminalForm");
    if (!form) return;

    const input = document.getElementById("terminalInput");
    const output = document.getElementById("terminalOutput");

    function appendLine(text, className) {
        const line = document.createElement("div");
        if (className) line.className = className;
        line.textContent = text;
        output.appendChild(line);
        output.scrollTop = output.scrollHeight;
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const command = input.value.trim();
        if (!command) return;

        appendLine("$ " + command, "terminal-line-command");
        input.value = "";
        input.disabled = true;

        try {
            const res = await fetch("/dashboard/admin/terminal", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command }),
            });
            const data = await res.json();
            if (data.error) {
                appendLine(data.error, "terminal-line-error");
            } else {
                if (data.stdout) appendLine(data.stdout, "terminal-line-stdout");
                if (data.stderr) appendLine(data.stderr, "terminal-line-stderr");
                if (!data.stdout && !data.stderr) appendLine("(no output, exit " + data.returncode + ")", "terminal-line-stdout");
            }
        } catch (err) {
            appendLine("Request failed: " + err.message, "terminal-line-error");
        } finally {
            input.disabled = false;
            input.focus();
        }
    });
})();
