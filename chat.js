// chat.js
// Chat panel used on /chat and on the ideation page of the AI conditions.
//
// Usage: StudyChat.init({ pid, cond, interests, opening, logEl, formEl, inputEl, sendEl })

(function () {
    "use strict";

    function init(opts) {
        const log = opts.logEl;
        const form = opts.formEl;
        const input = opts.inputEl;
        const sendBtn = opts.sendEl;

        function addMessage(role, text) {
            const row = document.createElement("div");
            row.className = "msg " + (role === "user" ? "user" : "assistant");
            const bubble = document.createElement("div");
            bubble.className = "bubble";
            const who = document.createElement("span");
            who.className = "who";
            who.textContent = role === "user" ? "You" : "Assistant";
            bubble.appendChild(who);
            bubble.appendChild(document.createTextNode(text));
            row.appendChild(bubble);
            log.appendChild(row);
            log.scrollTop = log.scrollHeight;
            return row;
        }

        function setBusy(busy) {
            sendBtn.disabled = busy;
            input.disabled = busy;
        }

        async function startSession() {
            setBusy(true);
            try {
                const res = await fetch("api/session", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ pid: opts.pid, cond: opts.cond, interests: opts.interests || "" })
                });
                const data = await res.json();
                addMessage("assistant", opts.opening);
                (data.history || []).forEach(function (m) { addMessage(m.role, m.content); });
            } catch (e) {
                addMessage("assistant", "Connection problem. Please reload the page.");
            }
            setBusy(false);
        }

        form.addEventListener("submit", async function (ev) {
            ev.preventDefault();
            const text = input.value.trim();
            if (!text) { return; }
            addMessage("user", text);
            input.value = "";
            setBusy(true);
            const typing = addMessage("assistant", "Thinking…");
            typing.querySelector(".bubble").classList.add("typing");
            try {
                const res = await fetch("api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ pid: opts.pid, message: text })
                });
                const data = await res.json();
                typing.remove();
                addMessage("assistant", data.reply || "Sorry, something went wrong. Please try again.");
            } catch (e) {
                typing.remove();
                addMessage("assistant", "Connection problem. Please try again.");
            }
            setBusy(false);
            input.focus();
        });

        input.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter" && !ev.shiftKey) {
                ev.preventDefault();
                form.requestSubmit();
            }
        });

        startSession();
    }

    window.StudyChat = { init: init };
})();
