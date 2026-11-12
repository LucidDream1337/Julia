import threading

import pytest

from app import db, jobs
from app.errors import BadRequest, Conflict
from app.webcrawl import Loaded, ParsedPage
from app.chunking import Block

db.init_db()


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeCrawler:
    pages = {}

    def __init__(self, rules):
        self.rules = rules
        self.fetcher = type("F", (), {"delay": 2.0})()

    def close(self):
        pass

    def load(self, url):
        return Loaded(url, page=ParsedPage(url, "Seite", [Block("text", "Inhalt " * 40)], ["https://s.example/a/2/"]))

    def crawl(self, cap, should_stop):
        for url, text in list(self.pages.items())[:cap]:
            if should_stop():
                return
            yield Loaded(url, page=ParsedPage(url, f"T {url[-2]}", [Block("text", text)], []))
        yield Loaded("https://s.example/a/err/", error="HTTP 500")


@pytest.fixture
def env(monkeypatch):
    calls = {"ensure": [], "replace": []}
    monkeypatch.setattr(jobs.embed, "get", lambda: FakeEmbedder())
    monkeypatch.setattr(jobs.store, "ensure", lambda c, d: calls["ensure"].append((c, d)))
    monkeypatch.setattr(jobs.store, "make_point", lambda url, i, v, p: {"id": f"{url}#{i}", "payload": p})
    monkeypatch.setattr(jobs.store, "replace_page", lambda c, url, pts: calls["replace"].append((c, url, len(pts))))
    monkeypatch.setattr(jobs, "WebCrawler", FakeCrawler)
    FakeCrawler.pages = {f"https://s.example/a/{i}/": f"Absatz {i}. " * 50 for i in range(1, 4)}
    return calls


def make_kb(name, notice=None):
    cfg = {"seeds": ["https://s.example/a/"], "max_pages": 50, "preset": "test", "language": "en"}
    if notice:
        cfg["notice"] = notice
    db.kb_create(name, "Test", f"kb_{name}", "test", "web", cfg)
    return db.kb_get(name)


def run_job(kb, cap=10):
    job_id = db.job_create(kb["name"], cap)
    jobs._stops[job_id] = threading.Event()
    jobs._run(job_id, kb, cap)
    return db.job_get(job_id)


def test_full_run_indexes_skips_unchanged_and_counts_errors(env):
    kb = make_kb("lauf-1")
    job = run_job(kb)
    assert job["status"] == "done"
    assert job["stats"]["pages"] == 3 and job["stats"]["errors"] == 1
    assert env["ensure"] == [("kb_lauf-1", 3)]
    assert db.page_stats("lauf-1")[0] == 3
    job2 = run_job(kb)  # zweiter Lauf: alles unverändert
    assert job2["stats"]["pages"] == 0 and job2["stats"]["unchanged"] == 3


def test_stop_flag_stops_run(env, monkeypatch):
    kb = make_kb("lauf-2")
    job_id = db.job_create("lauf-2", 10)
    ev = threading.Event()
    ev.set()
    jobs._stops[job_id] = ev
    jobs._run(job_id, kb, 10)
    assert db.job_get(job_id)["status"] == "stopped"


def test_start_requires_plan_ack_and_free_slot(env, monkeypatch):
    kb = make_kb("lauf-3", notice="Nur privat nutzen.")
    plan = {"kb": "lauf-3", "max_pages": 5, "notice": "Nur privat nutzen."}
    plan_id = db.plan_create("lauf-3", plan)
    with pytest.raises(BadRequest):
        jobs.start("unbekannt", None, True)
    with pytest.raises(BadRequest) as exc:
        jobs.start(plan_id, None, False)
    assert "Nur privat nutzen." in exc.value.message
    bad = db.plan_create("lauf-3", {"kb": "lauf-3", "max_pages": 5, "problem": "robots.txt verbietet"})
    with pytest.raises(BadRequest):
        jobs.start(bad, None, True)
    started = []
    monkeypatch.setattr(jobs.threading, "Thread", lambda **kw: type("T", (), {"start": lambda s: started.append(kw["args"])})())
    job = jobs.start(plan_id, 3, True)
    assert job["status"] == "running" and job["max_pages"] == 3 and started
    with pytest.raises(Conflict):
        jobs.start(plan_id, None, True)


def test_interrupted_jobs_are_marked_on_startup(env):
    job_id = db.job_create("lauf-1", 5)
    db.jobs_mark_interrupted()
    assert db.job_get(job_id)["status"] == "interrupted"


def test_plan_web_reports_robots_problem(monkeypatch):
    class Blocked(FakeCrawler):
        def load(self, url):
            return Loaded(url, skip="robots.txt verbietet diese URL", robots_blocked=True)

    monkeypatch.setattr(jobs, "WebCrawler", Blocked)
    make_kb("plan-1")
    plan = jobs.make_plan("plan-1", None)
    assert plan["robots_ok"] is False and "problem" in plan and plan["plan_id"]
    assert plan["estimated_minutes_max"] == round(50 * 2.0 / 60, 1)


def test_plan_web_ok(monkeypatch):
    monkeypatch.setattr(jobs, "WebCrawler", FakeCrawler)
    make_kb("plan-2")
    plan = jobs.make_plan("plan-2", 10)
    assert plan["robots_ok"] and plan["seeds_reachable"] == 1 and plan["discovered_links"] == 1
    assert plan["max_pages"] == 10 and "problem" not in plan


def test_hard_cap(env):
    cfg = {"max_pages": 999999}
    assert jobs._cap(cfg, None) == jobs.settings.hard_max_pages
    assert jobs._cap({}, 7) == 7
