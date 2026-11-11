"""Sprachmodell-Zugriff (Chat) und Modell-Übersicht über Ollama."""
from __future__ import annotations

import httpx

from .config import settings
from .errors import OllamaError


def chat(messages: list[dict], temperature: float = 0.2, num_predict: int | None = None) -> str:
    options: dict = {"temperature": temperature, "num_ctx": settings.ollama_num_ctx}
    if num_predict:
        options["num_predict"] = num_predict
    try:
        with httpx.Client(timeout=settings.ollama_timeout) as client:
            resp = client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": options,
                },
            )
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
    return content.strip()


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
