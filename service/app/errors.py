"""Fehlerklassen. Alle Meldungen sind für Menschen (und für Julia) lesbar formuliert."""
from __future__ import annotations


class JuliaError(Exception):
    status = 502

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BadRequest(JuliaError):
    status = 400


class NotFound(JuliaError):
    status = 404


class Conflict(JuliaError):
    status = 409


class OllamaError(JuliaError):
    pass


class StoreError(JuliaError):
    pass


class RobotsUnavailable(JuliaError):
    """robots.txt ist nicht sicher bewertbar -> nicht crawlen."""


class RobotsBlocked(JuliaError):
    """robots.txt verbietet das Crawlen der Startseiten."""


class CrawlBlocked(JuliaError):
    """Die Seite lehnt ab (HTTP 429/503/403 gehäuft) -> sofort aufhören."""
