// workspace.js
// Idea Workspace for the no-AI conditions: looks like the AI chat, but the
// "replies" are fixed thinking prompts and the participant's messages are notes.
// Needs chatui.js (for readProfile and renderMarkdown) and tracker.js.

(function () {
    "use strict";

    const BULB = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 21h6v-1H9v1zm3-19a7 7 0 0 0-4 12.7V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.3A7 7 0 0 0 12 2z"/></svg>';

    function init(opts) {
        const thread = document.getElementById("thread");
        const scroller = document.getElementById("scroller");
        const empty = document.getElementById("empty");
        const form = document.getElementById("composer");
        const input = document.getElementById("input");
        const send = document.getElementById("send");
        const promptBtn = document.getElementById("prompt-btn");
        const profile = ChatUI.readProfile(opts.profileFields || []);
        const tracker = window.StudyTracker ? StudyTracker.start({ pid: opts.pid, page: "workspace", idleMs: 60000 }) : null;
        let nextPrompt = 0;
        let introShown = false;

        function scrollDown() { scroller.scrollTop = scroller.scrollHeight; }

        function addNote(text) {
            const row = document.createElement("div");
            row.className = "msg user";
            const bubble = document.createElement("div");
            bubble.className = "bubble";
            bubble.textContent = text;
            row.appendChild(bubble);
            thread.appendChild(row);
            scrollDown();
        }

        function addGuide(markdown) {
            const row = document.createElement("div");
            row.className = "msg assistant";
            row.innerHTML = '<div class="avatar">' + BULB + '</div><div class="content"></div>';
            row.querySelector(".content").innerHTML = ChatUI.renderMarkdown(markdown);
            thread.appendChild(row);
            scrollDown();
        }

        function areaLine() {
            const parts = [profile.town, profile.region, profile.area_type].filter(Boolean);
            return parts.length ? "**Your area:** " + parts.join(" · ") : "";
        }

        function backgroundBlock() {
            const lines = [];
            // backgroundLabels is a list of [field, label] pairs, in question order
            opts.backgroundLabels.forEach(function (pair) {
                if (profile[pair[0]]) { lines.push("- **" + pair[1] + ":** " + profile[pair[0]]); }
            });
            return lines.length ? "**Your background**\n" + lines.join("\n") : "";
        }

        // First guide message: the condition's framing (+ background for personalised), shown once.
        function showIntro() {
            if (introShown) { return; }
            introShown = true;
            if (empty) { empty.remove(); }
            const parts = [opts.intro];
            if (opts.showBackground) {
                const bg = backgroundBlock();
                if (bg) { parts.push(bg); }
            }
            const area = areaLine();
            if (area) { parts.push(area); }
            addGuide(parts.join("\n\n"));
        }

        function save(role, text) {
            return fetch("api/note", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pid: opts.pid, role: role, text: text }),
                keepalive: true
            }).catch(function () { /* note stays visible; retry not needed for analysis */ });
        }

        function showPrompt(text, source) {
            showIntro();
            addGuide(text);
            save("prompt", text);
            if (tracker) { tracker.event("prompt_shown", source); }
        }

        function nextThinkingPrompt() {
            const text = opts.prompts[nextPrompt % opts.prompts.length];
            nextPrompt += 1;
            showPrompt(text, "button");
        }

        function addUserNote(text) {
            text = text.trim();
            if (!text) { return; }
            showIntro();
            addNote(text);
            save("note", text);
            if (tracker) { tracker.event("note_added", String(text.length)); }
            input.value = "";
            autosize();
            updateSend();
            input.focus();
        }

        function updateSend() { send.disabled = !input.value.trim(); }
        function autosize() {
            input.style.height = "auto";
            input.style.height = Math.min(input.scrollHeight, 180) + "px";
        }

        form.addEventListener("submit", function (ev) { ev.preventDefault(); addUserNote(input.value); });
        input.addEventListener("input", function () { autosize(); updateSend(); });
        input.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
                ev.preventDefault();
                addUserNote(input.value);
            }
        });
        promptBtn.addEventListener("click", nextThinkingPrompt);
        document.querySelectorAll(".starter").forEach(function (btn) {
            btn.addEventListener("click", function () {
                // Starter i shows prompt i, so each starter leads to a full question.
                const i = Number(btn.dataset.index);
                nextPrompt = Math.max(nextPrompt, i + 1);
                showPrompt(opts.prompts[i], "starter");
            });
        });

        // Register the session and restore earlier notes and prompts after a reload.
        fetch("api/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pid: opts.pid, cond: opts.cond, profile: profile })
        }).then(function (res) { return res.json(); }).then(function (data) {
            const history = data.history || [];
            if (!history.length) { return; }
            showIntro();
            history.forEach(function (m) {
                if (m.role === "note") { addNote(m.content); }
                else if (m.role === "prompt") {
                    addGuide(m.content);
                    const idx = opts.prompts.indexOf(m.content);
                    if (idx >= 0) { nextPrompt = Math.max(nextPrompt, idx + 1); }
                }
            });
        }).catch(function () { /* still usable without history */ });

        input.focus();
    }

    window.Workspace = { init: init };
})();
