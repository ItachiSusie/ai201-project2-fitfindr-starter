import agent
import app


def test_run_agent_happy_path_populates_all_fields(monkeypatch):
    item = {
        "id": "lst_test",
        "title": "Test Tee",
        "description": "Test item",
        "category": "tops",
        "style_tags": ["vintage", "graphic tee"],
        "size": "M",
        "condition": "good",
        "price": 24.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }
    calls = {}

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [item])

    def fake_suggest(new_item, wardrobe):
        calls["suggest_item"] = new_item
        calls["suggest_wardrobe"] = wardrobe
        return "Pair with baggy jeans and chunky sneakers."

    def fake_fit(outfit, new_item):
        calls["fit_outfit"] = outfit
        calls["fit_item"] = new_item
        return "thrifted this test tee and it's a full look"

    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest)
    monkeypatch.setattr(agent, "create_fit_card", fake_fit)

    wardrobe = {"items": [{"id": "w_001"}]}
    session = agent.run_agent("vintage graphic tee under $30 size M", wardrobe)

    assert session["error"] is None
    assert session["selected_item"] == item
    assert session["outfit_suggestion"] == "Pair with baggy jeans and chunky sneakers."
    assert session["fit_card"] == "thrifted this test tee and it's a full look"
    assert calls["suggest_item"] is session["selected_item"]
    assert calls["fit_item"] is session["selected_item"]
    assert calls["fit_outfit"] == session["outfit_suggestion"]


def test_run_agent_no_results_returns_early(monkeypatch):
    called = {"suggest": False, "fit": False}
    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [])

    def fake_suggest(new_item, wardrobe):
        called["suggest"] = True
        return "should not run"

    def fake_fit(outfit, new_item):
        called["fit"] = True
        return "should not run"

    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest)
    monkeypatch.setattr(agent, "create_fit_card", fake_fit)

    session = agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    assert session["error"] is not None
    assert session["fit_card"] is None
    assert called["suggest"] is False
    assert called["fit"] is False


def test_run_agent_empty_outfit_stops_before_fit_card(monkeypatch):
    item = {
        "id": "lst_test",
        "title": "Test Tee",
        "description": "Test item",
        "category": "tops",
        "style_tags": ["vintage"],
        "size": "M",
        "condition": "good",
        "price": 24.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }
    called = {"fit": False}

    monkeypatch.setattr(agent, "search_listings", lambda **kwargs: [item])
    monkeypatch.setattr(agent, "suggest_outfit", lambda **kwargs: "   ")

    def fake_fit(outfit, new_item):
        called["fit"] = True
        return "should not run"

    monkeypatch.setattr(agent, "create_fit_card", fake_fit)

    session = agent.run_agent("vintage tee", {"items": []})

    assert session["error"] is not None
    assert session["fit_card"] is None
    assert called["fit"] is False


def test_handle_query_empty_input():
    listing, outfit, fit = app.handle_query("   ", "Example wardrobe")
    assert "Please enter" in listing
    assert outfit == ""
    assert fit == ""


def test_handle_query_error_path(monkeypatch):
    monkeypatch.setattr(
        app,
        "run_agent",
        lambda query, wardrobe: {
            "error": "No listings matched your search.",
            "selected_item": None,
            "outfit_suggestion": None,
            "fit_card": None,
        },
    )
    listing, outfit, fit = app.handle_query("impossible query", "Example wardrobe")
    assert listing == "No listings matched your search."
    assert outfit == ""
    assert fit == ""
