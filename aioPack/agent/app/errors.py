"""Eigene Fehlerklassen, damit Aufrufer gezielt reagieren können."""


class OllamaError(RuntimeError):
    """Ollama ist nicht erreichbar oder lieferte eine Fehlermeldung."""


class StoreError(RuntimeError):
    """Qdrant ist nicht erreichbar oder lieferte eine Fehlermeldung."""


class RobotsUnavailable(RuntimeError):
    """robots.txt konnte nicht zuverlässig geprüft werden -> Crawl abbrechen."""


class CrawlAbort(RuntimeError):
    """Der Lernlauf wird kontrolliert abgebrochen (z. B. HTTP 429)."""
