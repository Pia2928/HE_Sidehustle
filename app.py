# app.py
"""
Backend for the hybrid-entrepreneur AI ideation study.

Main flow (participants arrive here from Prolific):

  /start   registers the participant
  /study   welcome -> prime ("A bit about you") -> task intro
           -> [condition assigned here, balanced randomisation, see randomisation.py]
           -> ideation (5-minute brainstorm) -> idea selection,
           then redirects to the survey (SURVEY_URL)

Pages that can also be embedded on their own (e.g. in Gorilla):

  /chat   AI assistant (generic_ai or personalized_ai condition)
  /guide  5-minute next-step guide (optional, unpaid part)
  /plan   business-plan editor with autosave (optional, unpaid part)

All data is stored in SQLite, keyed by the Prolific participant ID.
Researchers download the data as CSV from /admin/export/<table>.csv.

Run locally:   python app.py            (mock AI replies if no API key is set)
Production:    gunicorn -w 2 -b 0.0.0.0:8000 app:app
"""

import csv
import hmac
import io
import json
import os
import re
import sqlite3
import time
from contextlib import closing
from urllib.parse import quote

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, url_for
from markupsafe import escape

import content
import randomisation
from prompts import OPENING_MESSAGE, PROFILE_FIELDS, STARTER_PROMPTS, build_system_prompt

# ---------------------------------------------------------------------------
# Configuration (all via environment variables, see .env.example)
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "study.db"))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
FRAME_ANCESTORS = os.environ.get(
    "FRAME_ANCESTORS",
    "'self' https://*.gorilla.sc https://gorilla.sc https://*.research.sc https://research.sc",
)

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Model ID. Anthropic default: claude-sonnet-5-5; OpenAI default: gpt-4o; Azure: the deployment name.
MODEL = os.environ.get("MODEL", "")
TEMPERATURE = os.environ.get("TEMPERATURE", "0.7")  # set to "" for models that reject it
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "500"))

MAX_USER_MESSAGES = int(os.environ.get("MAX_USER_MESSAGES", "40"))
MAX_MESSAGE_CHARS = int(os.environ.get("MAX_MESSAGE_CHARS", "1500"))
MAX_PLAN_CHARS = int(os.environ.get("MAX_PLAN_CHARS", "20000"))

# Randomisation and flow
ALLOCATION_SEED = os.environ.get("ALLOCATION_SEED", "he-study-2026")  # fix before launch; never change after
ALLOCATION_SLOTS = int(os.environ.get("ALLOCATION_SLOTS", "2000"))
ALLOW_FORCED_CONDITION = os.environ.get("ALLOW_FORCED_CONDITION", "") == "1"  # testing only
IDEATION_SECONDS = int(os.environ.get("IDEATION_SECONDS", str(content.IDEATION_SECONDS_DEFAULT)))
MAX_ANSWER_CHARS = 2000
# Where participants go after choosing their idea. Placeholders: {pid} {cond} {idea} {study_id} {session_id}
SURVEY_URL = os.environ.get("SURVEY_URL", "")

CONDITIONS = set(randomisation.CONDITIONS)
AI_CONDITIONS = {"generic_ai", "personalized_ai"}
PERSONALIZED = {"personalized_noai", "personalized_ai"}
STAGES = ["welcome", "prime", "intro", "ideation", "select", "done"]
PAGES = {"chat", "workspace", "guide", "plan", "welcome", "prime", "intro", "ideation", "select"}
NOAI_CONDITIONS = {"generic_noai", "personalized_noai"}
MAX_NOTES = int(os.environ.get("MAX_NOTES", "200"))
PLAN_FIELDS = ["idea", "customer", "offer", "first_steps", "resources"]
PID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS participants (
    pid TEXT PRIMARY KEY,
    condition TEXT NOT NULL,
    interests TEXT,
    profile_json TEXT,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pid TEXT NOT NULL,
    condition TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS page_time (
    load_id TEXT PRIMARY KEY,
    pid TEXT NOT NULL,
    page TEXT NOT NULL,
    active_ms INTEGER NOT NULL DEFAULT 0,
    visible_ms INTEGER NOT NULL DEFAULT 0,
    open_ms INTEGER NOT NULL DEFAULT 0,
    started_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pid TEXT NOT NULL,
    page TEXT NOT NULL,
    type TEXT NOT NULL,
    detail TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS plans (
    pid TEXT PRIMARY KEY,
    fields_json TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    save_count INTEGER NOT NULL DEFAULT 1,
    submitted INTEGER NOT NULL DEFAULT 0,
    first_saved REAL NOT NULL,
    last_saved REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS allocation (
    slot INTEGER PRIMARY KEY,
    block INTEGER NOT NULL,
    condition TEXT NOT NULL,
    pid TEXT UNIQUE,
    assigned_at REAL
);
CREATE TABLE IF NOT EXISTS flow (
    pid TEXT PRIMARY KEY,
    condition TEXT,
    forced_condition TEXT,
    slot INTEGER,
    assigned_at REAL,
    study_id TEXT,
    session_id TEXT,
    stage TEXT NOT NULL,
    prime_json TEXT,
    ideas_json TEXT,
    selected_index INTEGER,
    selected_text TEXT,
    started_at REAL NOT NULL,
    prime_done_at REAL,
    ideation_started_at REAL,
    ideation_done_at REAL,
    select_done_at REAL
);
CREATE INDEX IF NOT EXISTS idx_messages_pid ON messages(pid);
CREATE INDEX IF NOT EXISTS idx_events_pid ON events(pid);
CREATE INDEX IF NOT EXISTS idx_page_time_pid ON page_time(pid);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA busy_timeout=5000")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.executescript(SCHEMA)
        # Older databases: add columns introduced later.
        cols = {r[1] for r in db.execute("PRAGMA table_info(participants)")}
        if "profile_json" not in cols:
            db.execute("ALTER TABLE participants ADD COLUMN profile_json TEXT")
        db.row_factory = sqlite3.Row
        randomisation.ensure_sequence(db, ALLOCATION_SEED, ALLOCATION_SLOTS)
        db.commit()


init_db()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def valid_pid(pid):
    return isinstance(pid, str) and bool(PID_RE.match(pid))


def json_body():
    # sendBeacon posts text/plain, so parse regardless of content type
    data = request.get_json(force=True, silent=True)
    return data if isinstance(data, dict) else {}


def word_count(text):
    return len(re.findall(r"\b\w+\b", text or ""))


def clean_profile(raw):
    """Keep only known survey fields, as short strings."""
    if not isinstance(raw, dict):
        return None
    profile = {k: str(raw.get(k, "")).strip()[:500] for k in PROFILE_FIELDS if str(raw.get(k, "")).strip()}
    return profile or None


def upsert_participant(db, pid, condition, interests=None, profile=None):
    now = time.time()
    profile_json = json.dumps(profile, ensure_ascii=False) if profile else None
    row = db.execute("SELECT condition FROM participants WHERE pid = ?", (pid,)).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO participants (pid, condition, interests, profile_json, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, condition, interests, profile_json, now, now),
        )
        return condition
    if profile_json:
        # First profile received is kept, so reloading the page cannot change what the assistant knows.
        db.execute("UPDATE participants SET profile_json = COALESCE(profile_json, ?) WHERE pid = ?",
                   (profile_json, pid))
    # The first recorded condition is authoritative; a changed URL cannot switch it.
    if row["condition"] != condition:
        log_event(db, pid, "system", "condition_mismatch", f"stored={row['condition']} received={condition}")
    if interests:
        db.execute("UPDATE participants SET interests = COALESCE(interests, ?), last_seen = ? WHERE pid = ?",
                   (interests, now, pid))
    else:
        db.execute("UPDATE participants SET last_seen = ? WHERE pid = ?", (now, pid))
    return row["condition"]


def log_event(db, pid, page, event_type, detail=None):
    db.execute(
        "INSERT INTO events (pid, page, type, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (pid, page, event_type[:64], (detail or "")[:2000], time.time()),
    )


@app.after_request
def security_headers(resp):
    # Allow embedding only from Gorilla (configurable); never cache participant data.
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        f"frame-ancestors {FRAME_ANCESTORS}"
    )
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

_client = None


def llm_provider():
    """Which AI service is configured: anthropic, azure, openai or mock (no key)."""
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
        return "azure"
    if OPENAI_API_KEY:
        return "openai"
    return "mock"


def llm_client():
    global _client
    if _client is not None:
        return _client
    provider = llm_provider()
    if provider == "anthropic":
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    elif provider == "azure":
        from openai import AzureOpenAI
        _client = AzureOpenAI(azure_endpoint=AZURE_OPENAI_ENDPOINT, api_key=AZURE_OPENAI_API_KEY,
                              api_version=AZURE_OPENAI_API_VERSION)
    elif provider == "openai":
        from openai import OpenAI
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def model_name():
    if MODEL:
        return MODEL
    return "claude-sonnet-5-5" if llm_provider() == "anthropic" else "gpt-4o"


def normalise_history(history):
    """Merge consecutive messages from the same side (e.g. after a failed reply) and start with the user,
    as the Anthropic API requires alternating turns."""
    out = []
    for m in history:
        if m["role"] not in ("user", "assistant") or not m["content"].strip():
            continue
        if out and out[-1]["role"] == m["role"]:
            out[-1] = {"role": m["role"], "content": out[-1]["content"] + "\n\n" + m["content"]}
        else:
            out.append({"role": m["role"], "content": m["content"]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def _anthropic_kwargs(system_prompt, history):
    kwargs = {"model": model_name(), "system": system_prompt, "messages": normalise_history(history),
              "max_tokens": MAX_OUTPUT_TOKENS}
    if TEMPERATURE != "":
        kwargs["temperature"] = float(TEMPERATURE)
    return kwargs


def _openai_kwargs(system_prompt, history):
    kwargs = {"model": model_name(), "messages": [{"role": "system", "content": system_prompt}] + history,
              "max_tokens": MAX_OUTPUT_TOKENS}
    if TEMPERATURE != "":
        kwargs["temperature"] = float(TEMPERATURE)
    return kwargs


def generate_reply(system_prompt, history):
    """history: list of {"role": "user"|"assistant", "content": str}"""
    provider = llm_provider()
    if provider == "mock":
        # Mock mode for local testing without an API key.
        tag = "personalised" if "interest profile" in system_prompt else "generic"
        return (f"[MOCK {tag} reply] Here are some ideas:\n\n1. **Idea A** for local commuters\n"
                "2. **Idea B** for small businesses\n3. **Idea C** weekend workshops\n"
                "4. **Idea D** mobile service\n5. **Idea E** online shop"), "mock"
    client = llm_client()
    if provider == "anthropic":
        resp = client.messages.create(**_anthropic_kwargs(system_prompt, history))
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        return text, getattr(resp, "model", model_name())
    resp = client.chat.completions.create(**_openai_kwargs(system_prompt, history))
    return resp.choices[0].message.content or "", getattr(resp, "model", model_name())


def generate_reply_stream(system_prompt, history):
    """Yield text chunks of the reply. Same settings as generate_reply."""
    provider = llm_provider()
    if provider == "mock":
        text, _ = generate_reply(system_prompt, history)
        for word in text.split(" "):
            time.sleep(0.02)
            yield word + " "
        return
    client = llm_client()
    if provider == "anthropic":
        with client.messages.stream(**_anthropic_kwargs(system_prompt, history)) as stream:
            for text in stream.text_stream:
                yield text
        return
    for chunk in client.chat.completions.create(stream=True, **_openai_kwargs(system_prompt, history)):
        # Azure sends an initial chunk without choices (content-filter results)
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ---------------------------------------------------------------------------
# Pages (embedded in Gorilla)
# ---------------------------------------------------------------------------


def page_args(require_ai=False):
    pid = request.args.get("pid", "")
    cond = request.args.get("cond", "")
    if not valid_pid(pid) or cond not in CONDITIONS:
        abort(400, "Missing or invalid pid/cond in the URL.")
    if require_ai and cond not in AI_CONDITIONS:
        abort(400, "The chat is only available in the AI conditions.")
    return pid, cond


@app.route("/chat")
def chat_page():
    pid, cond = page_args(require_ai=True)
    interests = request.args.get("interests", "")[:4000]
    return render_template("chat.html", pid=pid, cond=cond, interests=interests,
                           opening=OPENING_MESSAGE, starters=STARTER_PROMPTS,
                           profile_fields=list(PROFILE_FIELDS), max_chars=MAX_MESSAGE_CHARS)


@app.route("/workspace")
def workspace_page():
    """No-AI brainstorm environment: same look as /chat, with notes and fixed thinking prompts."""
    pid, cond = page_args()
    if cond not in NOAI_CONDITIONS:
        abort(400, "The workspace is only used in the no-AI conditions.")
    w = content.WORKSPACE
    return render_template("workspace.html", pid=pid, cond=cond, w=w, wc=w[cond],
                           background_labels=list(content.BACKGROUND_LABELS.items()),
                           show_background=cond == "personalized_noai",
                           profile_fields=list(PROFILE_FIELDS), max_chars=MAX_MESSAGE_CHARS)


@app.route("/guide")
def guide_page():
    pid, cond = page_args()
    return render_template("guide.html", pid=pid, cond=cond)


@app.route("/plan")
def plan_page():
    pid, cond = page_args()
    idea = request.args.get("idea", "")[:1000]
    return render_template("plan.html", pid=pid, cond=cond, idea=idea, max_chars=MAX_PLAN_CHARS)


@app.route("/health")
def health():
    return jsonify(ok=True, llm=llm_provider(), model=model_name() if llm_provider() != "mock" else None)


# ---------------------------------------------------------------------------
# Main flow: /start -> /study (welcome, prime, ideation, select) -> survey
# ---------------------------------------------------------------------------


def prime_pairs(answers):
    return [(q["text"], (answers or {}).get(q["key"], "")) for q in content.PRIME_ABOUT_YOU["questions"]]


def profile_text(answers):
    """Interest profile handed to the personalised assistant."""
    return "\n".join(f"{question}\n{answer.strip() or '-'}" for question, answer in prime_pairs(answers))


def get_flow(db, pid):
    return db.execute("SELECT * FROM flow WHERE pid = ?", (pid,)).fetchone()


def survey_redirect_url(row):
    ideas = json.loads(row["ideas_json"] or "[]")
    idx = row["selected_index"]
    idea = ideas[idx] if idx is not None and 0 <= idx < len(ideas) else ""
    values = {
        "pid": row["pid"], "cond": row["condition"], "idea": idea[:500],
        "description": (row["selected_text"] or "")[:1000],
        "study_id": row["study_id"] or "", "session_id": row["session_id"] or "",
    }
    return SURVEY_URL.format(**{k: quote(str(v), safe="") for k, v in values.items()})


@app.route("/start")
def start():
    """Prolific study link: https://<app>/start?PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID=...&SESSION_ID=..."""
    pid = request.args.get("PROLIFIC_PID") or request.args.get("pid", "")
    if not valid_pid(pid):
        abort(400, "We could not read your participant ID. Please return to Prolific and open the study link again.")
    db = get_db()
    if get_flow(db, pid) is None:
        forced = request.args.get("cond", "")
        if forced and not (ALLOW_FORCED_CONDITION and forced in CONDITIONS):
            abort(400, "Choosing a condition is only possible in test mode.")
        db.execute(
            "INSERT INTO flow (pid, forced_condition, study_id, session_id, stage, started_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pid, forced or None, request.args.get("STUDY_ID", "")[:64], request.args.get("SESSION_ID", "")[:64],
             "welcome", time.time()))
        log_event(db, pid, "welcome", "started")
        db.commit()
    return redirect(url_for("study", pid=pid))


def assign_condition(db, row):
    """Randomise at the end of the task intro, so drop-outs before ideation never use up a slot."""
    pid = row["pid"]
    if row["forced_condition"]:
        cond, slot = row["forced_condition"], None
    else:
        cond, slot = randomisation.assign(db, pid)  # opens the write transaction
    db.execute("UPDATE flow SET condition = ?, slot = ?, assigned_at = ? WHERE pid = ?", (cond, slot, time.time(), pid))
    upsert_participant(db, pid, cond)
    # Stored for everyone; only the personalised assistant's prompt uses it.
    db.execute("UPDATE participants SET interests = ? WHERE pid = ?",
               (profile_text(json.loads(row["prime_json"] or "{}")), pid))
    log_event(db, pid, "intro", "assigned", f"condition={cond} slot={slot} forced={bool(row['forced_condition'])}")
    return cond


@app.route("/study")
def study():
    pid = request.args.get("pid", "")
    if not valid_pid(pid):
        abort(400, "Missing participant ID.")
    db = get_db()
    row = get_flow(db, pid)
    if row is None:
        return redirect(url_for("start", pid=pid))
    cond, stage = row["condition"], row["stage"]
    common = {"pid": pid, "cond": cond, "stage": stage, "step": STAGES.index(stage) + 1, "n_steps": len(STAGES) - 1}

    if stage == "welcome":
        return render_template("flow_welcome.html", c=content.WELCOME, **common)

    if stage == "prime":
        return render_template("flow_prime.html", c=content.PRIME_ABOUT_YOU, max_chars=MAX_ANSWER_CHARS, **common)

    if stage == "intro":
        return render_template("flow_intro.html", c=content.TASK_INTRO, **common)

    if stage == "ideation":
        if row["ideation_started_at"] is None:
            db.execute("UPDATE flow SET ideation_started_at = ? WHERE pid = ?", (time.time(), pid))
            db.commit()
            row = get_flow(db, pid)
        remaining = max(0, int(IDEATION_SECONDS - (time.time() - row["ideation_started_at"])))
        show_prime = cond in content.SHOW_PRIME_ANSWERS_IN
        return render_template(
            "flow_ideation.html", c=content.IDEATION[cond], reminder=content.IDEATION_REMINDER,
            is_ai=cond in AI_CONDITIONS,
            prime=prime_pairs(json.loads(row["prime_json"] or "{}")) if show_prime else [],
            min_ideas=content.MIN_IDEAS, max_ideas=content.MAX_IDEAS,
            min_idea_chars=content.MIN_IDEA_CHARS, max_idea_chars=content.MAX_IDEA_CHARS,
            remaining=remaining, opening=OPENING_MESSAGE, max_chars=MAX_MESSAGE_CHARS, **common)

    if stage == "select":
        return render_template("flow_select.html", c=content.SELECT,
                               ideas=json.loads(row["ideas_json"] or "[]"), **common)

    # done
    if SURVEY_URL:
        return redirect(survey_redirect_url(row))
    return render_template("flow_done.html", c=content.DONE, **common)


@app.route("/api/step", methods=["POST"])
def api_step():
    data = json_body()
    pid, stage = data.get("pid"), data.get("stage")
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    if not valid_pid(pid) or stage not in STAGES:
        return jsonify(error="invalid request"), 400
    db = get_db()
    row = get_flow(db, pid)
    next_url = url_for("study", pid=pid)
    if row is None:
        return jsonify(error="unknown participant", next=url_for("start", pid=pid)), 404
    if row["stage"] != stage:
        # Already past this step (double click, back button): just move on.
        return jsonify(next=next_url, note="stage already completed")

    now = time.time()

    if stage == "welcome":
        db.execute("UPDATE flow SET stage = 'prime' WHERE pid = ?", (pid,))

    elif stage == "prime":
        answers = {}
        for q in content.PRIME_ABOUT_YOU["questions"]:
            text = str(payload.get(q["key"], "")).strip()[:MAX_ANSWER_CHARS]
            if len(text) < 2:
                return jsonify(error="Please answer every question."), 422
            answers[q["key"]] = text
        db.execute("UPDATE flow SET stage = 'intro', prime_json = ?, prime_done_at = ? WHERE pid = ?",
                   (json.dumps(answers, ensure_ascii=False), now, pid))

    elif stage == "intro":
        assign_condition(db, row)
        db.execute("UPDATE flow SET stage = 'ideation' WHERE pid = ?", (pid,))

    elif stage == "ideation":
        raw = payload.get("ideas")
        if not isinstance(raw, list):
            return jsonify(error="Please add your ideas."), 422
        ideas = [str(i).strip()[:content.MAX_IDEA_CHARS] for i in raw[:content.MAX_IDEAS]]
        ideas = [i for i in ideas if len(i) >= content.MIN_IDEA_CHARS]
        if len(ideas) < content.MIN_IDEAS:
            return jsonify(error=f"Please add at least {content.MIN_IDEAS} ideas."), 422
        started = row["ideation_started_at"] or now
        if now - started < IDEATION_SECONDS - 2:
            return jsonify(error="The brainstorming time is not over yet. Keep adding ideas."), 422
        db.execute("UPDATE flow SET stage = 'select', ideas_json = ?, ideation_done_at = ? WHERE pid = ?",
                   (json.dumps(ideas, ensure_ascii=False), now, pid))

    elif stage == "select":
        ideas = json.loads(row["ideas_json"] or "[]")
        try:
            idx = int(payload.get("index"))
        except (TypeError, ValueError):
            idx = -1
        description = str(payload.get("description", "")).strip()[:MAX_ANSWER_CHARS]
        if not 0 <= idx < len(ideas):
            return jsonify(error="Please choose one idea."), 422
        if len(description) < 20:
            return jsonify(error="Please describe your idea in a few sentences."), 422
        db.execute("UPDATE flow SET stage = 'done', selected_index = ?, selected_text = ?, select_done_at = ? WHERE pid = ?",
                   (idx, description, now, pid))

    else:
        return jsonify(next=next_url)

    log_event(db, pid, stage, "step_completed")
    db.commit()
    return jsonify(next=next_url)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@app.route("/api/session", methods=["POST"])
def api_session():
    data = json_body()
    pid, cond = data.get("pid"), data.get("cond")
    if not valid_pid(pid) or cond not in CONDITIONS:
        return jsonify(error="invalid pid or condition"), 400
    interests = (data.get("interests") or "")[:4000] or None
    profile = clean_profile(data.get("profile"))
    if profile and cond in ("generic_ai", "generic_noai"):
        # Generic conditions only use the area; don't keep personal answers here.
        profile = {k: v for k, v in profile.items() if k in ("region", "area_type", "town")} or None
    db = get_db()
    stored = upsert_participant(db, pid, cond, interests, profile)
    history = []
    if stored in AI_CONDITIONS or stored in NOAI_CONDITIONS:
        rows = db.execute("SELECT role, content FROM messages WHERE pid = ? ORDER BY id", (pid,)).fetchall()
        history = [dict(r) for r in rows]
    db.commit()
    return jsonify(condition=stored, history=history)


def prepare_chat(db):
    """Validate a chat request and store the user's message. Returns (context, error_response)."""
    data = json_body()
    pid = data.get("pid")
    message = (data.get("message") or "").strip()
    if not valid_pid(pid):
        return None, (jsonify(error="invalid pid"), 400)
    if not message:
        return None, (jsonify(error="empty message"), 400)
    message = message[:MAX_MESSAGE_CHARS]

    part = db.execute("SELECT condition, interests, profile_json FROM participants WHERE pid = ?", (pid,)).fetchone()
    if part is None or part["condition"] not in AI_CONDITIONS:
        return None, (jsonify(error="no AI session for this participant"), 403)

    n_user = db.execute("SELECT COUNT(*) FROM messages WHERE pid = ? AND role = 'user'", (pid,)).fetchone()[0]
    if n_user >= MAX_USER_MESSAGES:
        return None, (jsonify(error="message limit reached",
                              reply="You've reached the message limit for this task. Please continue with the study."), 429)

    history = [dict(r) for r in db.execute(
        "SELECT role, content FROM messages WHERE pid = ? ORDER BY id", (pid,)).fetchall()]
    db.execute("INSERT INTO messages (pid, condition, role, content, created_at) VALUES (?, ?, 'user', ?, ?)",
               (pid, part["condition"], message, time.time()))
    db.commit()
    profile = json.loads(part["profile_json"]) if part["profile_json"] else {}
    system_prompt = build_system_prompt(part["condition"], profile, part["interests"])
    return {"pid": pid, "condition": part["condition"], "system_prompt": system_prompt,
            "messages": history + [{"role": "user", "content": message}]}, None


def save_assistant_message(db, ctx, reply, model_used):
    db.execute(
        "INSERT INTO messages (pid, condition, role, content, model, created_at) VALUES (?, ?, 'assistant', ?, ?, ?)",
        (ctx["pid"], ctx["condition"], reply, model_used, time.time()))
    db.commit()


ASSISTANT_ERROR = "Sorry, the assistant is having trouble right now. Please try again in a moment."


@app.route("/api/chat", methods=["POST"])
def api_chat():
    db = get_db()
    ctx, err = prepare_chat(db)
    if err:
        return err
    try:
        reply, model_used = generate_reply(ctx["system_prompt"], ctx["messages"])
    except Exception as exc:  # keep the participant moving; log the failure
        log_event(db, ctx["pid"], "chat", "llm_error", repr(exc))
        db.commit()
        return jsonify(error="assistant unavailable", reply=ASSISTANT_ERROR), 502
    save_assistant_message(db, ctx, reply, model_used)
    return jsonify(reply=reply)


@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    """Same as /api/chat, but streams the reply as plain text while it is generated."""
    db = get_db()
    ctx, err = prepare_chat(db)
    if err:
        return err

    def generate():
        # The request's DB connection may already be closed while streaming, so use our own.
        parts = []
        error = None
        try:
            for piece in generate_reply_stream(ctx["system_prompt"], ctx["messages"]):
                parts.append(piece)
                yield piece
        except Exception as exc:
            error = repr(exc)
            if not parts:
                yield ASSISTANT_ERROR
        reply = "".join(parts).strip()
        with closing(sqlite3.connect(DB_PATH, timeout=10)) as conn:
            conn.execute("PRAGMA busy_timeout=5000")
            if error:
                log_event(conn, ctx["pid"], "chat", "llm_error", error)
            if reply:
                save_assistant_message(conn, ctx, reply, model_name() if llm_provider() != "mock" else "mock")
            conn.commit()

    return Response(generate(), mimetype="text/plain; charset=utf-8",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})


@app.route("/api/note", methods=["POST"])
def api_note():
    """Workspace (no-AI): save a participant's note, or log which thinking prompt was shown."""
    data = json_body()
    pid, role = data.get("pid"), data.get("role")
    text = str(data.get("text") or "").strip()[:MAX_MESSAGE_CHARS]
    if not valid_pid(pid) or role not in ("note", "prompt") or not text:
        return jsonify(error="invalid request"), 400
    db = get_db()
    part = db.execute("SELECT condition FROM participants WHERE pid = ?", (pid,)).fetchone()
    if part is None or part["condition"] not in NOAI_CONDITIONS:
        return jsonify(error="no workspace session for this participant"), 403
    n = db.execute("SELECT COUNT(*) FROM messages WHERE pid = ?", (pid,)).fetchone()[0]
    if n >= MAX_NOTES:
        return jsonify(error="limit reached"), 429
    db.execute("INSERT INTO messages (pid, condition, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
               (pid, part["condition"], role, text, time.time()))
    db.commit()
    return ("", 204)


@app.route("/api/track", methods=["POST"])
def api_track():
    """Heartbeat from tracker.js. Keeps the maximum value seen per page load."""
    data = json_body()
    pid, page, load_id = data.get("pid"), data.get("page"), str(data.get("load_id", ""))[:64]
    if not valid_pid(pid) or page not in PAGES or not load_id:
        return jsonify(error="invalid"), 400

    def ms(key):
        try:
            return max(0, min(int(data.get(key, 0)), 24 * 3600 * 1000))
        except (TypeError, ValueError):
            return 0

    now = time.time()
    db = get_db()
    db.execute(
        """INSERT INTO page_time (load_id, pid, page, active_ms, visible_ms, open_ms, started_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(load_id) DO UPDATE SET
             active_ms = MAX(active_ms, excluded.active_ms),
             visible_ms = MAX(visible_ms, excluded.visible_ms),
             open_ms = MAX(open_ms, excluded.open_ms),
             updated_at = excluded.updated_at""",
        (load_id, pid, page, ms("active_ms"), ms("visible_ms"), ms("open_ms"), now, now))
    db.commit()
    return ("", 204)


@app.route("/api/event", methods=["POST"])
def api_event():
    data = json_body()
    pid, page, etype = data.get("pid"), data.get("page"), data.get("type")
    if not valid_pid(pid) or page not in PAGES or not isinstance(etype, str) or not etype:
        return jsonify(error="invalid"), 400
    db = get_db()
    log_event(db, pid, page, etype, str(data.get("detail", "")))
    db.commit()
    return ("", 204)


@app.route("/api/plan", methods=["GET", "POST"])
def api_plan():
    db = get_db()
    if request.method == "GET":
        pid = request.args.get("pid", "")
        if not valid_pid(pid):
            return jsonify(error="invalid pid"), 400
        row = db.execute("SELECT fields_json, submitted FROM plans WHERE pid = ?", (pid,)).fetchone()
        if row is None:
            return jsonify(fields={}, submitted=False)
        return jsonify(fields=json.loads(row["fields_json"]), submitted=bool(row["submitted"]))

    data = json_body()
    pid = data.get("pid")
    if not valid_pid(pid):
        return jsonify(error="invalid pid"), 400
    raw = data.get("fields") if isinstance(data.get("fields"), dict) else {}
    fields = {k: str(raw.get(k, ""))[:MAX_PLAN_CHARS] for k in PLAN_FIELDS}
    submitted = 1 if data.get("submitted") else 0
    wc = sum(word_count(v) for v in fields.values())
    now = time.time()
    db.execute(
        """INSERT INTO plans (pid, fields_json, word_count, save_count, submitted, first_saved, last_saved)
           VALUES (?, ?, ?, 1, ?, ?, ?)
           ON CONFLICT(pid) DO UPDATE SET
             fields_json = excluded.fields_json,
             word_count = excluded.word_count,
             save_count = save_count + 1,
             submitted = MAX(submitted, excluded.submitted),
             last_saved = excluded.last_saved""",
        (pid, json.dumps(fields, ensure_ascii=False), wc, submitted, now, now))
    if submitted:
        log_event(db, pid, "plan", "plan_submitted", f"words={wc}")
    db.commit()
    return jsonify(saved=True, word_count=wc)


# ---------------------------------------------------------------------------
# Researcher export
# ---------------------------------------------------------------------------

EXPORTS = {
    "participants": "SELECT * FROM participants ORDER BY first_seen",
    "messages": "SELECT * FROM messages ORDER BY pid, id",
    "page_time": "SELECT * FROM page_time ORDER BY pid, started_at",
    "events": "SELECT * FROM events ORDER BY pid, id",
    "plans": "SELECT * FROM plans ORDER BY pid",
    "flow": "SELECT * FROM flow ORDER BY started_at",
    "allocation": "SELECT * FROM allocation WHERE pid IS NOT NULL ORDER BY slot",
    # One row per participant: the main DVs, ready for analysis.
    "summary": """
        SELECT p.pid, p.condition,
          f.slot AS allocation_slot, f.stage AS stage_reached,
          ROUND(f.ideation_done_at - f.ideation_started_at, 1) AS ideation_s,
          f.selected_text AS selected_idea,
          (SELECT COUNT(*) FROM messages m WHERE m.pid = p.pid AND m.role = 'user') AS n_user_messages,
          (SELECT COUNT(*) FROM messages m WHERE m.pid = p.pid AND m.role = 'note') AS n_notes,
          (SELECT COUNT(*) FROM messages m WHERE m.pid = p.pid AND m.role = 'prompt') AS n_prompts_viewed,
          ROUND(COALESCE((SELECT SUM(active_ms) FROM page_time t WHERE t.pid = p.pid AND t.page = 'workspace'), 0) / 1000.0, 1) AS workspace_active_s,
          ROUND(COALESCE((SELECT SUM(active_ms) FROM page_time t WHERE t.pid = p.pid AND t.page = 'chat'), 0) / 1000.0, 1) AS chat_active_s,
          ROUND(COALESCE((SELECT SUM(active_ms) FROM page_time t WHERE t.pid = p.pid AND t.page = 'guide'), 0) / 1000.0, 1) AS guide_active_s,
          ROUND(COALESCE((SELECT SUM(visible_ms) FROM page_time t WHERE t.pid = p.pid AND t.page = 'guide'), 0) / 1000.0, 1) AS guide_visible_s,
          ROUND(COALESCE((SELECT SUM(active_ms) FROM page_time t WHERE t.pid = p.pid AND t.page = 'plan'), 0) / 1000.0, 1) AS plan_active_s,
          ROUND(COALESCE((SELECT SUM(visible_ms) FROM page_time t WHERE t.pid = p.pid AND t.page = 'plan'), 0) / 1000.0, 1) AS plan_visible_s,
          (SELECT COUNT(DISTINCT detail) FROM events e WHERE e.pid = p.pid AND e.type = 'section_opened') AS guide_sections_opened,
          COALESCE(pl.word_count, 0) AS plan_words,
          COALESCE(pl.submitted, 0) AS plan_submitted,
          (SELECT COUNT(*) FROM events e WHERE e.pid = p.pid AND e.type = 'plan_downloaded') AS plan_downloads
        FROM participants p
        LEFT JOIN plans pl ON pl.pid = p.pid
        LEFT JOIN flow f ON f.pid = p.pid
        ORDER BY p.first_seen
    """,
}


@app.route("/admin/export/<name>.csv")
def admin_export(name):
    token = request.args.get("token", "") or request.headers.get("X-Admin-Token", "")
    if not ADMIN_TOKEN or not hmac.compare_digest(token, ADMIN_TOKEN):
        abort(403)
    if name not in EXPORTS:
        abort(404)
    cur = get_db().execute(EXPORTS[name])
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([d[0] for d in cur.description])
    writer.writerows(cur.fetchall())
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={name}.csv"})


@app.route("/admin/balance")
def admin_balance():
    """Quick check during data collection: participants per condition and stage reached."""
    token = request.args.get("token", "") or request.headers.get("X-Admin-Token", "")
    if not ADMIN_TOKEN or not hmac.compare_digest(token, ADMIN_TOKEN):
        abort(403)
    db = get_db()
    rows = db.execute(
        """SELECT condition, COUNT(*) AS randomised,
                  SUM(stage IN ('select', 'done')) AS ideation_done,
                  SUM(stage = 'done') AS finished
           FROM flow WHERE condition IS NOT NULL GROUP BY condition ORDER BY condition""").fetchall()
    not_yet = db.execute("SELECT COUNT(*) FROM flow WHERE condition IS NULL").fetchone()[0]
    return jsonify(conditions=[dict(r) for r in rows], not_yet_randomised=not_yet)


@app.errorhandler(400)
def bad_request(err):
    return Response(f"<p style='font-family:sans-serif'>{escape(err.description)}</p>", status=400)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=True)
