"""Test-Umgebung: Pfade setzen, bevor app.config gelesen wird. Keine Netzwerkzugriffe."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "service"))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="julia-test-"))
os.environ.setdefault("PRESETS_DIR", str(ROOT / "presets"))
os.environ.setdefault("SKILLS_DIR", str(ROOT / "skills"))
os.environ.setdefault("CRAWLER_CONTACT", "test@example.org")
os.environ.setdefault("MIN_CRAWL_DELAY", "1")
