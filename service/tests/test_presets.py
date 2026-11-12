import pytest

from app import presets
from app.errors import BadRequest
from app.webcrawl import WebRules


def test_all_shipped_presets_are_valid():
    found = presets.load_presets()
    assert {"w3schools", "wikipedia", "plantatlas"} <= set(found)
    typ, cfg = presets.build_config("w3schools", None, None, None)
    assert typ == "web" and len(cfg["seeds"]) == 10
    WebRules.from_config(cfg)
    typ, cfg = presets.build_config("plantatlas", None, None, None)
    assert cfg["seeds"] == ["https://plantatlas.bio/"] and cfg["notice"]


def test_parts_select_seeds_and_prefixes():
    _, cfg = presets.build_config("w3schools", ["python", "sql"], None, None)
    assert cfg["allowed_prefixes"] == ["/python/", "/sql/"] and cfg["parts"] == ["python", "sql"]
    assert "notice" in cfg  # Bestätigungspflicht bleibt erhalten


def test_unknown_part_and_preset():
    with pytest.raises(BadRequest):
        presets.build_config("w3schools", ["cobol"], None, None)
    with pytest.raises(BadRequest):
        presets.build_config("gibtsnicht", None, None, None)


def test_wikipedia_needs_topic():
    with pytest.raises(BadRequest):
        presets.build_config("wikipedia", None, None, None)
    typ, cfg = presets.build_config("wikipedia", None, None, {"categories": [{"name": "Kategorie:Botanik"}]})
    assert typ == "wikipedia" and cfg["lang"] == "de"


def test_custom_web_source():
    typ, cfg = presets.build_config(None, None, "web", {"seeds": ["https://docs.example/"]})
    assert typ == "web"
    with pytest.raises(BadRequest):
        presets.build_config(None, None, None, {})


def test_name_validation():
    assert presets.validate_name(" W3Schools-Python ") == "w3schools-python"
    for bad in ("", "a", "x y", "../etc", "-abc"):
        with pytest.raises(BadRequest):
            presets.validate_name(bad)
