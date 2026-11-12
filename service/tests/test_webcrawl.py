import pytest

from app.errors import BadRequest, CrawlBlocked, RobotsBlocked
from app.webcrawl import Loaded, RobotsGuard, WebCrawler, WebRules, normalize_url, parse_page

W3S = {
    "seeds": ["https://www.w3schools.com/python/default.asp", "https://www.w3schools.com/c/index.php"],
    "allowed_prefixes": ["/python/", "/c/"],
    "exclude_pattern": "(?i)(tryit|exercise|quiz)",
    "extensions": [".asp", ".php"],
    "content_selector": "#main",
    "stop_headings": ["top tutorials"],
    "skip_headings": ["example"],
}


def test_rules_validation():
    with pytest.raises(BadRequest):
        WebRules.from_config({"seeds": []})
    with pytest.raises(BadRequest):
        WebRules.from_config({"seeds": ["http://unsicher.example/"]})
    with pytest.raises(BadRequest):
        WebRules.from_config({"seeds": ["https://a.example/"], "exclude_pattern": "("})


def test_delay_has_floor():
    rules = WebRules.from_config({**W3S, "delay_seconds": 0})
    assert rules.delay >= 1.0


def test_in_scope():
    r = WebRules.from_config(W3S)
    assert r.in_scope("https://www.w3schools.com/python/python_lists.asp")
    assert r.in_scope("https://www.w3schools.com/c/c_intro.php")  # .php zugelassen
    assert not r.in_scope("https://www.w3schools.com/python/exercise.asp")
    assert not r.in_scope("https://www.w3schools.com/python/pic.png")
    assert not r.in_scope("https://www.w3schools.com/java/default.asp")
    assert not r.in_scope("https://evil.example/python/x.asp")
    assert not r.in_scope("http://www.w3schools.com/python/x.asp")


def test_extensionless_paths_allowed():
    r = WebRules.from_config({"seeds": ["https://plantatlas.bio/"], "allowed_prefixes": ["/plants/"]})
    assert r.in_scope("https://plantatlas.bio/plants/rose-12/")
    assert r.in_scope("https://plantatlas.bio/plants/rose-12")
    assert not r.in_scope("https://plantatlas.bio/plants/rose-12/photo.jpg")


def test_normalize_url():
    base = "https://x.example/a/b.asp"
    assert normalize_url("c.asp?x=1#top", base) == "https://x.example/a/c.asp"
    assert normalize_url("//y.example//p", base) == "https://y.example/p"
    assert normalize_url("mailto:a@b.c", base) is None
    assert normalize_url("#frag", base) is None


HTML = """<html><head><title>T</title></head><body>
<nav><a href="/python/python_intro.asp">Intro</a></nav>
<div id="main"><h1>Python Lists</h1><p>Lists store items.</p>
<h2>Example</h2><div class="w3-code"><pre>x = [1, 2]
print(x)</pre></div>
<ul><li>append</li></ul>
<h2>Top Tutorials</h2><p>Werbung</p></div>
<a href="/python/python_dicts.asp">Dicts</a><a href="/c/exercise.asp">Ex</a>
</body></html>"""


def test_parse_page_extracts_blocks_links_and_stops():
    page = parse_page(HTML, "https://www.w3schools.com/python/python_lists.asp", WebRules.from_config(W3S))
    assert page.title == "Python Lists"
    kinds = [b.kind for b in page.blocks]
    assert "code" in kinds and "text" in kinds
    assert not any("Werbung" in b.text for b in page.blocks)
    assert not any(b.text.lower() == "example" for b in page.blocks)
    assert "https://www.w3schools.com/python/python_intro.asp" in page.links
    assert "https://www.w3schools.com/python/python_dicts.asp" in page.links
    assert all("exercise" not in l for l in page.links)


def test_parse_page_fallback_selectors_for_unknown_layout():
    rules = WebRules.from_config({"seeds": ["https://p.example/"]})
    html = "<html><body><header>Menü</header><main><h1>Rose</h1><p>Eine Blume.</p></main><footer>Impressum</footer></body></html>"
    page = parse_page(html, "https://p.example/plants/rose/", rules)
    assert page.title == "Rose"
    assert [b.text for b in page.blocks] == ["Rose", "Eine Blume."]


class FakeResp:
    def __init__(self, status=200, text="", ctype="text/html", url=None):
        self.status_code, self.text, self.headers, self.url = status, text, {"content-type": ctype}, url


class FakeFetcher:
    def __init__(self, pages, robots="User-agent: *\nDisallow: /private/\n"):
        self.pages, self.robots, self.delay, self.calls = pages, robots, 1.0, []

    def get(self, url):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return FakeResp(200, self.robots, "text/plain", url)
        resp = self.pages.get(url)
        if resp is None:
            return FakeResp(404, "", url=url)
        resp.url = resp.url or url
        return resp

    def raise_delay(self, s):
        self.delay = max(self.delay, s)

    def close(self):
        pass


def make_crawler(rules, fetcher):
    c = WebCrawler.__new__(WebCrawler)
    c.rules, c.fetcher, c.robots, c._denied = rules, fetcher, RobotsGuard(fetcher), 0
    return c


def test_crawl_follows_links_respects_cap_and_robots():
    rules = WebRules.from_config({"seeds": ["https://s.example/a/"], "allowed_prefixes": ["/a/", "/private/"]})
    page = lambda title, *links: FakeResp(text=f"<html><body><main><h1>{title}</h1><p>Text hier.</p>"
                                          + "".join(f'<a href="{l}">x</a>' for l in links) + "</main></body></html>")
    fetcher = FakeFetcher({
        "https://s.example/a/": page("Start", "/a/1/", "/a/2/", "/private/geheim/"),
        "https://s.example/a/1/": page("Eins", "/a/3/"),
        "https://s.example/a/2/": page("Zwei"),
        "https://s.example/a/3/": page("Drei"),
        "https://s.example/private/geheim/": page("Geheim"),
    })
    crawler = make_crawler(rules, fetcher)
    titles = [l.page.title for l in crawler.crawl(10, lambda: False) if l.page]
    assert titles == ["Start", "Eins", "Zwei", "Drei"]
    assert "https://s.example/private/geheim/" not in fetcher.calls  # robots.txt bindend
    crawler = make_crawler(rules, fetcher)
    assert len([l for l in crawler.crawl(2, lambda: False) if l.page]) == 2


def test_crawl_stops_when_requested():
    rules = WebRules.from_config({"seeds": ["https://s.example/a/"]})
    fetcher = FakeFetcher({"https://s.example/a/": FakeResp(text="<html><body><p>Hallo Welt</p></body></html>")})
    assert list(make_crawler(rules, fetcher).crawl(10, lambda: True)) == []


def test_blocked_seed_raises():
    rules = WebRules.from_config({"seeds": ["https://s.example/private/x/"]})
    crawler = make_crawler(rules, FakeFetcher({}))
    with pytest.raises(RobotsBlocked):
        list(crawler.crawl(5, lambda: False))


def test_429_aborts_immediately():
    rules = WebRules.from_config({"seeds": ["https://s.example/a/"]})
    crawler = make_crawler(rules, FakeFetcher({"https://s.example/a/": FakeResp(status=429)}))
    with pytest.raises(CrawlBlocked):
        list(crawler.crawl(5, lambda: False))


def test_repeated_403_aborts():
    rules = WebRules.from_config({"seeds": ["https://s.example/a/"]})
    crawler = make_crawler(rules, FakeFetcher({}))
    crawler.fetcher.get = lambda url: FakeResp(200, "", "text/plain", url) if url.endswith("robots.txt") else FakeResp(status=403)
    with pytest.raises(CrawlBlocked):
        for _ in range(6):
            crawler.load("https://s.example/a/")


def test_robots_unreadable_means_no_crawl():
    from app.errors import RobotsUnavailable
    f = FakeFetcher({})
    f.get = lambda url: FakeResp(status=500)
    with pytest.raises(RobotsUnavailable):
        RobotsGuard(f).can_fetch("https://s.example/")
