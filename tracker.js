// tracker.js
// Measures time on a page and sends heartbeats to /api/track.
//
//   open_ms     time since the page loaded
//   visible_ms  time the tab was visible (not hidden behind another tab or minimised)
//   active_ms   visible AND the participant interacted (mouse, keys, scroll, touch)
//               within the last IDLE_MS. This is the main commitment DV.
//
// Usage: StudyTracker.start({ pid, page, cond, idleMs })

(function () {
    "use strict";

    const TICK_MS = 1000;
    const HEARTBEAT_MS = 10000;

    function randomId() {
        if (window.crypto && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return Date.now().toString(36) + Math.random().toString(36).slice(2);
    }

    function postJson(url, body, useBeacon) {
        const payload = JSON.stringify(body);
        if (useBeacon && navigator.sendBeacon) {
            navigator.sendBeacon(url, payload);
            return Promise.resolve();
        }
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: payload,
            keepalive: true
        }).catch(function () { /* retried on the next heartbeat */ });
    }

    const StudyTracker = {
        start: function (opts) {
            const pid = opts.pid;
            const page = opts.page;
            const idleMs = opts.idleMs || 60000;
            const loadId = randomId();
            const startedAt = Date.now();
            let lastActivity = Date.now();
            let lastTick = Date.now();
            let activeMs = 0;
            let visibleMs = 0;

            function markActivity() {
                lastActivity = Date.now();
            }

            ["mousemove", "mousedown", "keydown", "scroll", "wheel", "touchstart", "input"].forEach(function (evt) {
                window.addEventListener(evt, markActivity, { passive: true, capture: true });
            });

            function tick() {
                const now = Date.now();
                // Cap each step so a sleeping laptop does not add a huge chunk.
                const step = Math.min(now - lastTick, TICK_MS * 3);
                lastTick = now;
                if (document.visibilityState === "visible") {
                    visibleMs += step;
                    if (now - lastActivity <= idleMs) {
                        activeMs += step;
                    }
                }
            }

            function snapshot() {
                return {
                    pid: pid,
                    page: page,
                    load_id: loadId,
                    active_ms: Math.round(activeMs),
                    visible_ms: Math.round(visibleMs),
                    open_ms: Date.now() - startedAt
                };
            }

            function send(useBeacon) {
                tick();
                return postJson("api/track", snapshot(), useBeacon);
            }

            setInterval(tick, TICK_MS);
            setInterval(function () { send(false); }, HEARTBEAT_MS);
            document.addEventListener("visibilitychange", function () {
                if (document.visibilityState === "hidden") {
                    send(true);
                } else {
                    lastTick = Date.now();
                }
            });
            window.addEventListener("pagehide", function () { send(true); });

            // Register the participant and condition so every page appears in the exports.
            if (opts.cond) {
                postJson("api/session", { pid: pid, cond: opts.cond }, false);
            }
            send(false);
            StudyTracker.event = function (type, detail) {
                return postJson("api/event", { pid: pid, page: page, type: type, detail: detail || "" }, false);
            };
            StudyTracker.event("page_opened");
            return StudyTracker;
        },
        event: function () { return Promise.resolve(); }
    };

    window.StudyTracker = StudyTracker;
})();
