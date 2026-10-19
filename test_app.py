# test_app.py
"""
End-to-end test of the study backend in mock mode (no API key needed).
Run: python test_app.py
"""

import csv
import io
import os
import sys
import tempfile

tmp_dir = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(tmp_dir, "test.db")
os.environ["ADMIN_TOKEN"] = "test-token"
for key in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(key, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as study  # noqa: E402

client = study.app.test_client()


def export(name):
    res = client.get(f"/admin/export/{name}.csv?token=test-token")
    assert res.status_code == 200, res.status_code
    return list(csv.DictReader(io.StringIO(res.get_data(as_text=True))))


def main():
    # Pages render, and bad input is rejected
    assert client.get("/chat?pid=P1&cond=personalized_ai&interests=cycling").status_code == 200
    assert client.get("/chat?pid=P2&cond=generic_noai").status_code == 400
    assert client.get("/chat?pid=bad%20id&cond=generic_ai").status_code == 400
    assert client.get("/guide?pid=P1&cond=personalized_ai").status_code == 200
    assert client.get("/plan?pid=P1&cond=personalized_ai&idea=Bike%20repair").status_code == 200
    res = client.get("/chat?pid=P1&cond=generic_ai")
    assert "frame-ancestors" in res.headers["Content-Security-Policy"]

    # Personalized AI participant
    r = client.post("/api/session", json={"pid": "P1", "cond": "personalized_ai", "interests": "cycling; logistics"})
    assert r.get_json()["condition"] == "personalized_ai"
    r = client.post("/api/chat", json={"pid": "P1", "message": "Give me ideas"})
    assert "personalised" in r.get_json()["reply"], r.get_json()

    # Generic AI participant
    client.post("/api/session", json={"pid": "P2", "cond": "generic_ai"})
    r = client.post("/api/chat", json={"pid": "P2", "message": "Give me ideas"})
    assert "generic" in r.get_json()["reply"]

    # Condition cannot be switched via URL after first contact
    r = client.post("/api/session", json={"pid": "P2", "cond": "personalized_ai", "interests": "x"})
    assert r.get_json()["condition"] == "generic_ai"
    assert len(r.get_json()["history"]) == 2

    # No-AI participant cannot use the chat API
    client.post("/api/session", json={"pid": "P3", "cond": "generic_noai"})
    assert client.post("/api/chat", json={"pid": "P3", "message": "hi"}).status_code == 403

    # Time tracking keeps the max per page load (heartbeats can arrive out of order)
    client.post("/api/track", json={"pid": "P1", "page": "plan", "load_id": "L1",
                                    "active_ms": 30000, "visible_ms": 40000, "open_ms": 50000})
    client.post("/api/track", json={"pid": "P1", "page": "plan", "load_id": "L1",
                                    "active_ms": 10000, "visible_ms": 10000, "open_ms": 10000})
    # sendBeacon sends text/plain
    client.post("/api/track", data='{"pid":"P1","page":"guide","load_id":"L2","active_ms":120000,'
                                   '"visible_ms":150000,"open_ms":160000}', content_type="text/plain")
    client.post("/api/event", json={"pid": "P1", "page": "guide", "type": "section_opened", "detail": "validate"})
    client.post("/api/event", json={"pid": "P1", "page": "guide", "type": "section_opened", "detail": "validate"})
    client.post("/api/event", json={"pid": "P1", "page": "guide", "type": "section_opened", "detail": "costs"})

    # Plan autosave, restore, submit
    client.post("/api/plan", json={"pid": "P1", "fields": {"idea": "Mobile bike repair"}})
    client.post("/api/plan", json={"pid": "P1", "fields": {"idea": "Mobile bike repair",
                                                          "customer": "Commuters in Leeds who cycle daily"},
                                   "submitted": True})
    assert client.get("/api/plan?pid=P1").get_json()["fields"]["customer"].startswith("Commuters")

    # Exports
    assert client.get("/admin/export/summary.csv?token=wrong").status_code == 403
    summary = {row["pid"]: row for row in export("summary")}
    p1 = summary["P1"]
    assert p1["condition"] == "personalized_ai"
    assert p1["n_user_messages"] == "1"
    assert float(p1["plan_active_s"]) == 30.0, p1
    assert float(p1["guide_active_s"]) == 120.0
    assert p1["guide_sections_opened"] == "2"
    assert p1["plan_words"] == "9", p1["plan_words"]
    assert p1["plan_submitted"] == "1"
    assert set(summary) == {"P1", "P2", "P3"}
    assert len(export("messages")) == 4
    assert any(e["type"] == "condition_mismatch" for e in export("events"))

    print("All tests passed.")


if __name__ == "__main__":
    main()
