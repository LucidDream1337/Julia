"""Sprachmodell-Zugriff (Chat) und Modell-Übersicht über Ollama."""
from __future__ import annotations

import re

import httpx

from .config import settings
from .errors import OllamaError


_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def chat(messages: list[dict], temperature: float = 0.2, num_predict: int | None = None) -> str:
    options: dict = {"temperature": temperature, "num_ctx": settings.ollama_num_ctx}
    if num_predict:
        options["num_predict"] = num_predict
    payload: dict = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": options,
    }
    # Qwen3 & Co. "denken" standardmäßig; das verbraucht Tokens (Query-Rewrite hat nur 48) und Zeit.
    if not settings.ollama_think:
        payload["think"] = False
    try:
        with httpx.Client(timeout=settings.ollama_timeout) as client:
            url = f"{settings.ollama_base_url}/api/chat"
            resp = client.post(url, json=payload)
            if resp.status_code == 400 and "think" in payload and "think" in resp.text.lower():
                payload.pop("think")  # Modell/Ollama-Version kennt den Parameter nicht
                resp = client.post(url, json=payload)
            if resp.status_code == 404 and "not found" in resp.text.lower():
                raise OllamaError(
                    f"Modell '{settings.ollama_model}' fehlt in Ollama. Installieren mit: "
                    f"docker exec julia-school-ollama ollama pull {settings.ollama_model}"
                )
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content", "")
    except httpx.HTTPError as exc:
        raise OllamaError(
            f"Ollama nicht erreichbar oder fehlerhaft ({settings.ollama_base_url}): {exc}"
        ) from exc
    except ValueError as exc:
        raise OllamaError(f"Ungültige Antwort von Ollama: {exc}") from exc
    return _THINK_RE.sub("", content).strip()


def list_models() -> list[str]:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            return [m.get("name", "") for m in resp.json().get("models", [])]
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError(f"Ollama nicht erreichbar: {exc}") from exc


def model_available(wanted: str, installed: list[str]) -> bool:
    """'nomic-embed-text' passt auch auf 'nomic-embed-text:latest'. Groß-/Kleinschreibung egal."""
    wanted = wanted.strip().lower()
    installed = [name.lower() for name in installed]
    if wanted in installed:
        return True
    if ":" not in wanted:
        return any(name.startswith(wanted + ":") for name in installed)
    return False
