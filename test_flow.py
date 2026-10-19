# test_flow.py
"""
Tests for randomisation and the main participant flow (mock AI, no API key).
Run: python test_flow.py
"""

import collections
import csv
import io
import os
import sys
import tempfile
import threading
from urllib.parse import parse_qs, urlparse

tmp_dir = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(tmp_dir, "flow.db")
os.environ["ADMIN_TOKEN"] = "test-token"
os.environ["SURVEY_URL"] = "https://survey.example/?pid={pid}&cond={cond}&idea={idea}&desc={description}"
os.environ["ALLOCATION_SLOTS"] = "400"
os.environ["IDEATION_SECONDS"] = "0"
for key in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(key, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as study  # noqa: E402
import randomisation  # noqa: E402

client = study.app.test_client()


def test_sequence_is_balanced_per_block():
    seq = randomisation.generate_sequence("seed-x", 1000)
    blocks = collections.defaultdict(list)
    for blk, cond in seq:
        blocks[blk].append(cond)
    for items in blocks.values():
        counts = collections.Counter(items)
        assert len(counts) == 4 and len(set(counts.values())) == 1, counts
    assert randomisation.generate_sequence("seed-x", 50)[:50] == seq[:50], "sequence must be reproducible"
    assert {len(v) for v in blocks.values()} <= {4, 8}


PRIME = {"free_time": "- hiking\n- cooking", "skills": "- project management", "lose_yourself": "- vintage bikes"}


def to_ideation(pid, c=None):
    """Walk a participant through welcome, prime and task intro (where randomisation happens)."""
    c = c or client
    c.get(f"/start?PROLIFIC_PID={pid}&STUDY_ID=S1&SESSION_ID=X")
    for stage, data in (("welcome", {}), ("prime", PRIME), ("intro", {})):
        r = c.post("/api/step", json={"pid": pid, "stage": stage, "data": data})
        assert r.status_code == 200, (stage, r.get_json())


def test_no_assignment_before_task_intro():
    client.get("/start?PROLIFIC_PID=EARLY1")
    step("EARLY1", "welcome")
    step("EARLY1", "prime", PRIME)
    assert "EARLY1" not in {r["pid"] for r in export("allocation")}
    assert condition_of("EARLY1") == ""
    page = client.get("/study?pid=EARLY1").get_data(as_text=True)
    assert "Let\u2019s develop an idea!" in page and "brainstorm 5 ideas" in page
    balance = client.get("/admin/balance?token=test-token").get_json()
    assert balance["not_yet_randomised"] >= 1


def test_assignment_balanced_and_idempotent():
    for i in range(200):
        to_ideation(f"P{i:03d}")
    rows = [r for r in export("allocation") if r["pid"].startswith("P")]
    assert len(rows) == 200
    counts = collections.Counter(r["condition"] for r in rows)
    # Permuted blocks of 4/8: groups differ by at most 4 at any time.
    assert max(counts.values()) - min(counts.values()) <= 4, counts
    # Same person returning keeps their slot and condition
    before = {r["pid"]: r["condition"] for r in export("allocation")}
    client.get("/start?PROLIFIC_PID=P007")
    step("P007", "intro")
    after = {r["pid"]: r["condition"] for r in export("allocation")}
    assert before == after


def test_concurrent_assignment_never_duplicates():
    errors = []

    def worker(n):
        try:
            c = study.app.test_client()
            for j in range(10):
                to_ideation(f"C{n}_{j}", c)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    rows = export("allocation")
    slots = [r["slot"] for r in rows]
    pids = [r["pid"] for r in rows]
    assert len(slots) == len(set(slots)) and len(pids) == len(set(pids))
    assert sum(p.startswith("C") for p in pids) == 80


def step(pid, stage, data=None):
    return client.post("/api/step", json={"pid": pid, "stage": stage, "data": data or {}})


def condition_of(pid):
    return {r["pid"]: r["condition"] for r in export("flow")}[pid]


def run_full_flow(pid):
    client.get(f"/start?PROLIFIC_PID={pid}")
    assert "Your side hustle starts here" in client.get(f"/study?pid={pid}").get_data(as_text=True)
    assert step(pid, "welcome").status_code == 200

    page = client.get(f"/study?pid={pid}").get_data(as_text=True)
    assert "A bit about you" in page and "in and outside of work" in page
    assert step(pid, "prime", {"free_time": "", "skills": "x", "lose_yourself": "y"}).status_code == 422
    assert step(pid, "prime", PRIME).status_code == 200

    assert "Start brainstorming" in client.get(f"/study?pid={pid}").get_data(as_text=True)
    assert step(pid, "intro").status_code == 200
    cond = condition_of(pid)
    assert cond in study.CONDITIONS

    page = client.get(f"/study?pid={pid}").get_data(as_text=True)
    assert ('id="chat-form"' in page) == (cond in study.AI_CONDITIONS), cond
    assert ("What you wrote about yourself" in page) == (cond in study.PERSONALIZED), cond
    if cond in study.AI_CONDITIONS:
        reply = client.post("/api/chat", json={"pid": pid, "message": "ideas please"}).get_json()["reply"]
        expected = "personalised" if cond == "personalized_ai" else "generic"
        assert expected in reply, (cond, reply)

    assert step(pid, "ideation", {"ideas": ["Bike repair", "Tutoring", "Dog walking", "x", ""]}).status_code == 422
    ideas = ["Guided hikes for beginners", "Online meal-prep classes", "Vintage bike restoration", "Dog walking", "Excel tutoring"]
    assert step(pid, "ideation", {"ideas": ideas}).status_code == 200

    page = client.get(f"/study?pid={pid}").get_data(as_text=True)
    assert "Vintage bike restoration" in page and "Dog walking" in page
    assert step(pid, "select", {"index": 2, "description": "short"}).status_code == 422
    assert step(pid, "select", {"index": 2, "description": "Restore and resell vintage bikes to commuters."}).status_code == 200

    res = client.get(f"/study?pid={pid}")
    assert res.status_code == 302
    q = parse_qs(urlparse(res.headers["Location"]).query)
    assert q["pid"] == [pid] and q["cond"] == [cond] and q["idea"] == ["Vintage bike restoration"]
    assert q["desc"][0].startswith("Restore and resell")
    # Repeating a finished step does not change anything
    assert step(pid, "welcome").get_json().get("note") == "stage already completed"
    return cond


def test_brainstorm_timer_enforced():
    to_ideation("TIMER1")
    client.get("/study?pid=TIMER1")  # starts the clock
    study.IDEATION_SECONDS = 300
    try:
        r = step("TIMER1", "ideation", {"ideas": ["a idea", "b idea", "c idea", "d idea", "e idea"]})
        assert r.status_code == 422 and "not over" in r.get_json()["error"]
    finally:
        study.IDEATION_SECONDS = 0


def test_full_flow_all_conditions():
    seen = set()
    i = 0
    while len(seen) < 4 and i < 40:
        seen.add(run_full_flow(f"F{i:02d}"))
        i += 1
    assert seen == study.CONDITIONS, seen
    # Personalised assistant received the prime answers
    interests = {r["pid"]: r["interests"] for r in export("participants")}
    assert "vintage bikes" in interests["F00"]


def test_forced_condition_blocked_outside_test_mode():
    assert client.get("/start?PROLIFIC_PID=Z1&cond=generic_ai").status_code == 400


def test_forced_condition_in_test_mode():
    study.ALLOW_FORCED_CONDITION = True
    try:
        client.get("/start?PROLIFIC_PID=FORCE1&cond=personalized_noai")
        for stage, data in (("welcome", {}), ("prime", PRIME), ("intro", {})):
            step("FORCE1", stage, data)
        assert condition_of("FORCE1") == "personalized_noai"
        assert "FORCE1" not in {r["pid"] for r in export("allocation")}
    finally:
        study.ALLOW_FORCED_CONDITION = False


def test_balance_endpoint_and_summary():
    res = client.get("/admin/balance?token=test-token").get_json()
    assert {c["condition"] for c in res["conditions"]} == study.CONDITIONS
    summary = export("summary")
    finished = [r for r in summary if r["stage_reached"] == "done"]
    assert finished and all(r["selected_idea"] for r in finished)


def export(name):
    res = client.get(f"/admin/export/{name}.csv?token=test-token")
    assert res.status_code == 200
    return list(csv.DictReader(io.StringIO(res.get_data(as_text=True))))


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print("All flow tests passed.")
