// chatui.js
// Full-page chat for the AI conditions (embedded in Gorilla as an iframe).
//
// Profile data from the Gorilla survey is read from the link, either as normal
// query parameters (?region=...&age=...) or, more robustly, after a "#" with
// "||" between fields:  #region=North West||age=34||free_time=hiking, cooking
// The part after "#" is never cut off by "&" or "#" inside answers.

(function () {
    "use strict";

    function readProfile(fields) {
        const profile = {};
        const query = new URLSearchParams(window.location.search);
        fields.forEach(function (f) {
            if (query.get(f)) { profile[f] = query.get(f); }
        });
        let hash = window.location.hash.replace(/^#/, "");
        try { hash = decodeURIComponent(hash); } catch (e) { /* keep raw text */ }
        if (hash) {
            hash.split("||").forEach(function (part) {
                const i = part.indexOf("=");
                if (i < 1) { return; }
                const key = part.slice(0, i).trim();
                const value = part.slice(i + 1).trim();
                // Gorilla leaves unfilled placeholders like ${store:x}; ignore them
                if (fields.indexOf(key) !== -1 && value && value.indexOf("${") === -1) {
                    profile[key] = value;
                }
            });
        }
        return profile;
    }

    // Minimal, safe Markdown: escape everything, then bold, inline code, lists, paragraphs.
    function escapeHtml(s) {
        return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }
    function inline(s) {
        return escapeHtml(s)
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/`([^`]+)`/g, "<code>$1</code>");
    }
    function renderMarkdown(text) {
        const lines = text.replace(/\r/g, "").split("\n");
        let html = "";
        let list = null;
        let para = [];
        function flushPara() {
            if (para.length) { html += "<p>" + para.map(inline).join("<br>") + "</p>"; para = []; }
        }
        function closeList() {
            if (list) { html += "</" + list + ">"; list = null; }
        }
        lines.forEach(function (line) {
            const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
            const ul = line.match(/^\s*[-*•]\s+(.*)$/);
            const h = line.match(/^\s*#{1,6}\s+(.*)$/);
            if (ol || ul) {
                flushPara();
                const type = ol ? "ol" : "ul";
                if (list !== type) { closeList(); html += "<" + type + ">"; list = type; }
                html += "<li>" + inline((ol || ul)[1]) + "</li>";
            } else if (h) {
                flushPara(); closeList();
                html += "<p><strong>" + inline(h[1]) + "</strong></p>";
            } else if (!line.trim()) {
                flushPara(); closeList();
            } else {
                closeList();
                para.push(line);
            }
        });
        flushPara(); closeList();
        return html;
    }

    const SPARK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l1.9 5.6L19.5 9.5l-5.6 1.9L12 17l-1.9-5.6L4.5 9.5l5.6-1.9z"/></svg>';

    function init(opts) {
        const thread = document.getElementById("thread");
        const scroller = document.getElementById("scroller");
        const empty = document.getElementById("empty");
        const form = document.getElementById("composer");
        const input = document.getElementById("input");
        const send = document.getElementById("send");
        const profile = readProfile(opts.profileFields || []);
        const tracker = window.StudyTracker ? StudyTracker.start({ pid: opts.pid, page: "chat", idleMs: 60000 }) : null;
        let busy = false;

        function scrollDown() { scroller.scrollTop = scroller.scrollHeight; }
        function hideEmpty() { if (empty) { empty.remove(); } }

        function addUser(text) {
            hideEmpty();
            const row = document.createElement("div");
            row.className = "msg user";
            const bubble = document.createElement("div");
            bubble.className = "bubble";
            bubble.textContent = text;
            row.appendChild(bubble);
            thread.appendChild(row);
            scrollDown();
        }

        function addAssistant(text) {
            hideEmpty();
            const row = document.createElement("div");
            row.className = "msg assistant";
            row.innerHTML = '<div class="avatar">' + SPARK + '</div><div class="content"></div>';
            const content = row.querySelector(".content");
            thread.appendChild(row);
            const api = {
                row: row,
                text: "",
                typing: function () {
                    content.innerHTML = '<span class="typing" aria-label="Assistant is typing"><span></span><span></span><span></span></span>';
                },
                set: function (t) { api.text = t; content.innerHTML = renderMarkdown(t); scrollDown(); },
                finish: function () {
                    const actions = document.createElement("div");
                    actions.className = "actions";
                    const copy = document.createElement("button");
                    copy.type = "button";
                    copy.className = "copy";
                    copy.textContent = "Copy";
                    copy.addEventListener("click", function () {
                        copyText(api.text).then(function () {
                            copy.textContent = "Copied";
                            setTimeout(function () { copy.textContent = "Copy"; }, 1500);
                        });
                        if (tracker) { tracker.event("copy_clicked"); }
                    });
                    actions.appendChild(copy);
                    row.querySelector(".content").appendChild(actions);
                }
            };
            if (text) { api.set(text); api.finish(); }
            return api;
        }

        function copyText(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                return navigator.clipboard.writeText(text).catch(function () { return legacyCopy(text); });
            }
            return legacyCopy(text);
        }
        function legacyCopy(text) {
            const ta = document.createElement("textarea");
            ta.value = text;
            ta.setAttribute("readonly", "");
            ta.className = "visually-hidden";
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand("copy"); } catch (e) { /* ignore */ }
            ta.remove();
            return Promise.resolve();
        }

        function updateSend() { send.disabled = busy || !input.value.trim(); }
        function autosize() {
            input.style.height = "auto";
            input.style.height = Math.min(input.scrollHeight, 180) + "px";
        }

        async function sendMessage(text) {
            text = text.trim();
            if (!text || busy) { return; }
            busy = true;
            updateSend();
            addUser(text);
            input.value = "";
            autosize();
            if (tracker) { tracker.event("message_sent", String(text.length)); }
            const reply = addAssistant("");
            reply.typing();
            scrollDown();
            try {
                const res = await fetch("api/chat/stream", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ pid: opts.pid, message: text })
                });
                if (!res.ok) {
                    let msg = "Sorry, something went wrong. Please try again.";
                    try { msg = (await res.json()).reply || msg; } catch (e) { /* not JSON */ }
                    reply.set(msg);
                } else if (res.body && res.body.getReader) {
                    const reader = res.body.getReader();
                    const decoder = new TextDecoder();
                    let acc = "";
                    for (;;) {
                        const step = await reader.read();
                        if (step.done) { break; }
                        acc += decoder.decode(step.value, { stream: true });
                        reply.set(acc);
                    }
                    acc += decoder.decode();
                    reply.set(acc.trim() || "Sorry, I didn't get a reply. Please try again.");
                } else {
                    reply.set((await res.text()).trim());
                }
            } catch (e) {
                reply.set("Connection problem. Please try again.");
            }
            reply.finish();
            busy = false;
            updateSend();
            input.focus();
        }

        form.addEventListener("submit", function (ev) {
            ev.preventDefault();
            sendMessage(input.value);
        });
        input.addEventListener("input", function () { autosize(); updateSend(); });
        input.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
                ev.preventDefault();
                sendMessage(input.value);
            }
        });
        document.querySelectorAll(".starter").forEach(function (btn) {
            btn.addEventListener("click", function () {
                if (tracker) { tracker.event("starter_clicked", btn.textContent); }
                sendMessage(btn.textContent);
            });
        });

        // Register the session (and the survey profile), then restore earlier messages after a reload.
        fetch("api/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pid: opts.pid, cond: opts.cond, interests: opts.interests || "", profile: profile })
        }).then(function (res) { return res.json(); }).then(function (data) {
            (data.history || []).forEach(function (m) {
                if (m.role === "user") { addUser(m.content); } else { addAssistant(m.content); }
            });
        }).catch(function () { /* the chat still works; history just isn't restored */ });

        input.focus();
    }

    window.ChatUI = { init: init, renderMarkdown: renderMarkdown, readProfile: readProfile };
})();
