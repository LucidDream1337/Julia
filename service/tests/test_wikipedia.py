import pytest

from app.errors import BadRequest
from app.wikipedia import WikiClient


class Fake(WikiClient):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.responses = []

    def _get(self, params):
        return self.responses.pop(0)


def test_language_validation():
    with pytest.raises(BadRequest):
        WikiClient({"lang": "de/../x"})


def test_resolve_titles_from_categories_search_and_titles():
    c = Fake({"lang": "de"})
    c.responses = [
        {"query": {"categorymembers": [
            {"ns": 0, "title": "Rose"}, {"ns": 14, "title": "Kategorie:Unter"}]}},
        {"query": {"categorymembers": [{"ns": 0, "title": "Lilie"}, {"ns": 0, "title": "Rose"}]}},
        {"query": {"search": [{"title": "Tulpe"}, {"title": "Lilie"}]}},
    ]
    titles = c.resolve_titles({"titles": ["Eiche"], "categories": [{"name": "Kategorie:Blumen", "depth": 1}], "search": "Tulpe"}, 10)
    assert titles == ["Eiche", "Rose", "Lilie", "Tulpe"]


def test_resolve_titles_respects_cap_and_requires_topic():
    c = Fake({"lang": "en"})
    assert c.resolve_titles({"titles": ["A", "B", "C"]}, 2) == ["A", "B"]
    with pytest.raises(BadRequest):
        c.resolve_titles({}, 5)


def test_extract_builds_url_and_handles_missing():
    c = Fake({"lang": "de"})
    c.responses = [{"query": {"pages": [{"title": "Rosa (Gattung)", "extract": "Text."}]}},
                   {"query": {"pages": [{"title": "Nix", "missing": True}]}}]
    page = c.extract("Rosa")
    assert page.url == "https://de.wikipedia.org/wiki/Rosa_(Gattung)"
    assert c.extract("Nix") is None
