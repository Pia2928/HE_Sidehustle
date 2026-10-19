# test_chat.py
"""
Tests for the AI chat: local-area knowledge, condition-specific prompts,
profile handling and streaming (mock mode, no API key).
Run: python test_chat.py
"""

import os
import sys
import tempfile

tmp_dir = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(tmp_dir, "chat.db")
os.environ["ADMIN_TOKEN"] = "test-token"
for key in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(key, None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as study  # noqa: E402
import prompts  # noqa: E402
import regions  # noqa: E402

client = study.app.test_client()

FULL_PROFILE = {
    "region": "North West", "area_type": "City", "town": "Manchester",
    "age": "34", "gender": "Woman", "occupation": "Nurse", "sector": "Health & Social Work",
    "years_in_sector": "8", "education": "Undergraduate / Bachelor's",
    "free_time": "hiking, baking", "skills": "organising, first aid", "lose_yourself": "vintage bikes",
}


def test_region_matching():
    assert regions.match_region("north west") == "North West"
    assert regions.match_region("Yorkshire") == "Yorkshire and the Humber"
    assert regions.match_region("I live in the South-West") == "South West"
    assert regions.match_region("Cymru") == "Wales"
    assert regions.match_region("") is None and regions.match_region("Atlantis") is None
    assert regions.match_area_type("A village / rural area") == "rural"
    assert regions.match_area_type("Town or suburb") == "town"
    assert set(regions.REGIONS) == {
        "London", "South East", "South West", "East of England", "East Midlands", "West Midlands",
        "North West", "North East", "Yorkshire and the Humber", "Wales", "Scotland", "Northern Ireland"}


def test_generic_prompt_uses_area_but_not_person():
    p = prompts.build_system_prompt("generic_ai", FULL_PROFILE)
    assert "North West" in p and "Lake District" in p and "Manchester" in p
    for personal in ("Nurse", "hiking", "vintage bikes", "Woman", "34", "Health & Social Work", "Bachelor"):
        assert personal not in p, personal
    assert "Do NOT tailor" in p


def test_personalised_prompt_uses_area_and_person():
    p = prompts.build_system_prompt("personalized_ai", FULL_PROFILE)
    assert "North West" in p and "Lake District" in p
    for personal in ("Nurse", "hiking", "vintage bikes", "Woman", "Age: 34", "Health & Social Work", "Bachelor"):
        assert personal in p, personal
    assert "stereotypes" in p


def test_area_block_identical_across_conditions():
    g = prompts.build_system_prompt("generic_ai", FULL_PROFILE)
    pz = prompts.build_system_prompt("personalized_ai", FULL_PROFILE)
    import side_hustles
    area = prompts.AREA_BLOCK.format(area=regions.area_context("North West", "City", "Manchester"),
                                     best_fits=side_hustles.best_fits_text("North West", "city"))
    assert area in g and area in pz


def test_side_hustle_catalogue_in_both_conditions():
    for cond in ("generic_ai", "personalized_ai"):
        p = prompts.build_system_prompt(cond, FULL_PROFILE)
        for job in ("babysitting", "Dog walking", "unwanted clothes", "Tutoring", "food business with your council"):
            assert job in p, (cond, job)


def test_unknown_region_falls_back():
    p = prompts.build_system_prompt("generic_ai", {})
    assert "region unknown" in p


def test_profile_from_session_drives_prompt_and_is_kept():
    r = client.post("/api/session", json={"pid": "G1", "cond": "generic_ai", "profile": FULL_PROFILE})
    assert r.status_code == 200
    client.post("/api/session", json={"pid": "P1", "cond": "personalized_ai",
                                      "profile": dict(FULL_PROFILE, junk="x" * 50)})
    # A later reload with different data does not change the stored profile
    client.post("/api/session", json={"pid": "P1", "cond": "personalized_ai", "profile": {"region": "London"}})
    db_rows = {r["pid"]: r for r in export("participants")}
    assert '"North West"' in db_rows["P1"]["profile_json"] and "junk" not in db_rows["P1"]["profile_json"]

    reply = client.post("/api/chat", json={"pid": "P1", "message": "ideas"}).get_json()["reply"]
    assert "personalised" in reply
    reply = client.post("/api/chat", json={"pid": "G1", "message": "ideas"}).get_json()["reply"]
    assert "generic" in reply


def test_streaming_reply_is_saved():
    client.post("/api/session", json={"pid": "S1", "cond": "personalized_ai", "profile": FULL_PROFILE})
    res = client.post("/api/chat/stream", json={"pid": "S1", "message": "Suggest 5 side-business ideas"})
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "MOCK personalised" in text
    msgs = [m for m in export("messages") if m["pid"] == "S1"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"].startswith("[MOCK personalised")


def test_stream_rejects_no_ai_and_limits():
    client.post("/api/session", json={"pid": "N1", "cond": "generic_noai"})
    assert client.post("/api/chat/stream", json={"pid": "N1", "message": "hi"}).status_code == 403
    assert client.post("/api/chat/stream", json={"pid": "S1", "message": ""}).status_code == 400


def test_chat_page_renders():
    page = client.get("/chat?pid=S1&cond=personalized_ai").get_data(as_text=True)
    assert "What side business could you start?" in page and "Suggest 5 side-business ideas" in page
    assert client.get("/chat?pid=S1&cond=generic_noai").status_code == 400


def test_workspace_pages():
    page = client.get("/workspace?pid=W1&cond=generic_noai").get_data(as_text=True)
    assert "Idea Workspace" in page and "What do people around me need?" in page
    page = client.get("/workspace?pid=W2&cond=personalized_noai").get_data(as_text=True)
    assert "How could my hobbies help others?" in page and "showBackground: true" in page
    assert client.get("/workspace?pid=W3&cond=generic_ai").status_code == 400


def test_workspace_notes_and_profile():
    client.post("/api/session", json={"pid": "W1", "cond": "generic_noai", "profile": FULL_PROFILE})
    client.post("/api/session", json={"pid": "W2", "cond": "personalized_noai", "profile": FULL_PROFILE})
    rows = {r["pid"]: r for r in export("participants")}
    assert "North West" in rows["W1"]["profile_json"] and "Nurse" not in rows["W1"]["profile_json"]
    assert "Nurse" in rows["W2"]["profile_json"]

    assert client.post("/api/note", json={"pid": "W2", "role": "prompt", "text": "How could X?"}).status_code == 204
    assert client.post("/api/note", json={"pid": "W2", "role": "note", "text": "Baking classes"}).status_code == 204
    assert client.post("/api/note", json={"pid": "W2", "role": "assistant", "text": "x"}).status_code == 400
    assert client.post("/api/note", json={"pid": "P1", "role": "note", "text": "x"}).status_code == 403
    hist = client.post("/api/session", json={"pid": "W2", "cond": "personalized_noai"}).get_json()["history"]
    assert [h["role"] for h in hist] == ["prompt", "note"]
    summary = {r["pid"]: r for r in export("summary")}
    assert summary["W2"]["n_notes"] == "1" and summary["W2"]["n_prompts_viewed"] == "1"


def test_workspace_prompts_parallel():
    import content
    g, p = content.WORKSPACE["generic_noai"], content.WORKSPACE["personalized_noai"]
    assert len(g["starters"]) == len(p["starters"]) == 3
    assert len(g["prompts"]) == len(p["prompts"]) == 6
    avg = lambda xs: sum(len(x) for x in xs) / len(xs)
    assert abs(avg(g["prompts"]) - avg(p["prompts"])) < 25, (avg(g["prompts"]), avg(p["prompts"]))


class _FakeStream:
    def __init__(self, parts):
        self.text_stream = iter(parts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeAnthropic:
    """Records the request and returns a canned reply, like anthropic.Anthropic()."""
    def __init__(self):
        self.calls = []
        outer = self

        class Messages:
            def create(self, **kw):
                outer.calls.append(kw)
                block = type("B", (), {"type": "text", "text": "1. Dog walking for commuters"})()
                return type("R", (), {"content": [block], "model": kw["model"]})()

            def stream(self, **kw):
                outer.calls.append(kw)
                return _FakeStream(["1. Dog ", "walking"])
        self.messages = Messages()


def test_anthropic_provider_path():
    fake = _FakeAnthropic()
    old_key, old_client = study.ANTHROPIC_API_KEY, study._client
    study.ANTHROPIC_API_KEY, study._client = "test-key", fake
    try:
        assert study.llm_provider() == "anthropic" and study.model_name() == "claude-sonnet-5-5"
        client.post("/api/session", json={"pid": "AN1", "cond": "generic_ai", "profile": FULL_PROFILE})
        reply = client.post("/api/chat", json={"pid": "AN1", "message": "ideas"}).get_json()["reply"]
        assert reply == "1. Dog walking for commuters"
        kw = fake.calls[-1]
        assert kw["model"] == "claude-sonnet-5-5" and "North West" in kw["system"]
        assert kw["messages"] == [{"role": "user", "content": "ideas"}]
        text = client.post("/api/chat/stream", json={"pid": "AN1", "message": "more"}).get_data(as_text=True)
        assert text == "1. Dog walking"
        roles = [m["role"] for m in fake.calls[-1]["messages"]]
        assert roles == ["user", "assistant", "user"], roles
    finally:
        study.ANTHROPIC_API_KEY, study._client = old_key, old_client


def test_normalise_history():
    h = [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "a"},
         {"role": "user", "content": "b"}, {"role": "assistant", "content": "c"}]
    assert study.normalise_history(h) == [{"role": "user", "content": "a\n\nb"},
                                          {"role": "assistant", "content": "c"}]


def export(name):
    import csv
    import io
    res = client.get(f"/admin/export/{name}.csv?token=test-token")
    assert res.status_code == 200
    return list(csv.DictReader(io.StringIO(res.get_data(as_text=True))))


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print("All chat tests passed.")
