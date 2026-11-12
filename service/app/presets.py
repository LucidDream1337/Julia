"""Quellen-Vorlagen (presets/*.json) und Aufbau der Konfiguration einer Wissensdatenbank."""
from __future__ import annotations

import copy
import json
import logging
import re

from .config import settings
from .errors import BadRequest
from .webcrawl import WebRules

log = logging.getLogger(__name__)
SOURCE_TYPES = ("web", "wikipedia")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")


def load_presets() -> dict[str, dict]:
    presets: dict[str, dict] = {}
    if not settings.presets_dir.is_dir():
        return presets
    for path in sorted(settings.presets_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("type") not in SOURCE_TYPES:
                raise ValueError(f"type muss einer von {SOURCE_TYPES} sein")
            presets[path.stem] = data
        except (OSError, ValueError) as exc:
            log.error("Preset %s ist ungültig: %s", path.name, exc)
    return presets


def list_presets() -> list[dict]:
    out = []
    for name, p in load_presets().items():
        out.append({
            "name": name,
            "title": p.get("title", name),
            "type": p["type"],
            "description": p.get("description", ""),
            "parts": sorted((p.get("parts") or {}).keys()),
            "language": p.get("language", ""),
            "size_hint": p.get("size_hint"),
            "needs_acknowledgement": bool(p.get("notice")),
        })
    return out


def validate_name(name: str) -> str:
    name = (name or "").strip().lower()
    if not NAME_RE.match(name):
        raise BadRequest(
            "Ungültiger Name. Erlaubt sind 2 bis 40 Zeichen: Kleinbuchstaben, Ziffern, '-' und '_' "
            "(z. B. 'w3schools-python')."
        )
    return name


def build_config(preset: str | None, parts: list[str] | None, source_type: str | None,
                 overrides: dict | None) -> tuple[str, dict]:
    """Liefert (Quelltyp, Konfiguration). Entweder per Preset oder mit eigenem Typ + Konfiguration."""
    overrides = dict(overrides or {})
    if preset:
        presets = load_presets()
        if preset not in presets:
            raise BadRequest(f"Unbekanntes Preset '{preset}'. Verfügbar: {', '.join(presets) or 'keine'}.")
        p = presets[preset]
        cfg = copy.deepcopy(p.get("defaults") or {})
        available = p.get("parts") or {}
        if available:
            chosen = parts or list(available.keys())
            unknown = [x for x in chosen if x not in available]
            if unknown:
                raise BadRequest(f"Unbekannte parts {unknown}. Verfügbar: {', '.join(sorted(available))}.")
            cfg["seeds"], cfg["allowed_prefixes"] = [], []
            for key in chosen:
                cfg["seeds"] += available[key].get("seeds", [])
                cfg["allowed_prefixes"] += available[key].get("allowed_prefixes", [])
            cfg["parts"] = chosen
        elif parts:
            raise BadRequest(f"Das Preset '{preset}' kennt keine parts.")
        for key in ("notice", "license", "language", "size_hint"):
            if p.get(key):
                cfg[key] = p[key]
        cfg["preset"] = preset
        cfg.update(overrides)
        typ = p["type"]
    else:
        if source_type not in SOURCE_TYPES:
            raise BadRequest(f"Gib entweder preset oder type an ({', '.join(SOURCE_TYPES)}).")
        typ, cfg = source_type, overrides
    validate_config(typ, cfg)
    return typ, cfg


def validate_config(typ: str, cfg: dict) -> None:
    if typ == "web":
        WebRules.from_config(cfg)  # wirft BadRequest bei Fehlern
    elif typ == "wikipedia":
        if not (cfg.get("titles") or cfg.get("categories") or cfg.get("search")):
            raise BadRequest("Für Wikipedia wird titles, categories oder search gebraucht.")
    try:
        if int(cfg.get("max_pages", 1)) < 1:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise BadRequest("max_pages muss eine positive Zahl sein.") from exc
