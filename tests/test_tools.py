import tools
from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str):
        self._content = content

    def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str):
        self.completions = _FakeCompletions(content)


class _FakeGroqClient:
    def __init__(self, content: str):
        self.chat = _FakeChat(content)


def _patch_groq(monkeypatch, content: str):
    monkeypatch.setattr(tools, "_get_groq_client", lambda: _FakeGroqClient(content))


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=40)
    assert all(item["price"] <= 40 for item in results)


def test_search_size_filter():
    results = search_listings("tee", size="M", max_price=50)
    assert len(results) > 0
    for item in results:
        assert "m" in item["size"].lower()


def test_search_returns_empty_list_not_exception():
    results = search_listings("tee", size=None, max_price=1)
    assert isinstance(results, list)
    assert results == []


def test_suggest_outfit_with_wardrobe_returns_string(monkeypatch):
    _patch_groq(monkeypatch, "Pair the tee with baggy jeans and chunky sneakers.")
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe_does_not_crash(monkeypatch):
    _patch_groq(monkeypatch, "Try this with relaxed denim and platform sneakers.")
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_returns_string(monkeypatch):
    _patch_groq(monkeypatch, "thrifted this tee for $24 and the fit is perfect.")
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("Pair with jeans and sneakers.", item)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit_returns_error_message():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert "Unable" in result or "error" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_message():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("   ", item)
    assert isinstance(result, str)
    assert "Unable" in result or "error" in result.lower()
    