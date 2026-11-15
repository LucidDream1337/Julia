"""Agent-Service: OpenAI-kompatible API vor Ollama + Qdrant.
Open WebUI spricht mit diesem Service wie mit einem normalen Modell. Der Agent kann
Knowledge Bases (Qdrant-Collections) anlegen, befüllen, durchsuchen und Skills speichern."""
import ipaddress, json, os, pathlib, re, socket, time, uuid
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

OLLAMA = os.getenv("OLLAMA_URL", "http://ollama:11434")
QDRANT = os.getenv("QDRANT_URL", "http://qdrant:6333")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen3:4b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
API_KEY = os.getenv("AGENT_API_KEY", "")
ALLOW_WEB = os.getenv("AGENT_ALLOW_WEB", "false").lower() == "true"
THINK = os.getenv("AGENT_THINK", "false").lower() == "true"
DATA = pathlib.Path(os.getenv("DATA_DIR", "/data"))
SKILLS = DATA / "skills"
SKILLS.mkdir(parents=True, exist_ok=True)
REGISTRY = DATA / "kbs.json"
MAX_STEPS = 6
MODEL_ID = "julia"

qdrant = QdrantClient(url=QDRANT)
http = httpx.Client(timeout=300)
app = FastAPI()


# ---------- Hilfsfunktionen ----------
def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", s.lower().strip()).strip("-")[:48] or "unnamed"


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}


def save_registry(reg: dict) -> None:
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def embed(texts: list[str]) -> list[list[float]]:
    r = http.post(f"{OLLAMA}/api/embed", json={"model": EMBED_MODEL, "input": texts})
    r.raise_for_status()
    return r.json()["embeddings"]


def chunk(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [text[i:i + size] for i in range(0, len(text), size - overlap)]


# ---------- Knowledge Bases ----------
def create_knowledge_base(name: str, description: str = "") -> str:
    n, reg = slug(name), load_registry()
    if n in reg:
        return f"Knowledge Base '{n}' existiert bereits."
    dim = len(embed(["test"])[0])
    qdrant.create_collection(f"kb_{n}", vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    reg[n] = description
    save_registry(reg)
    return f"Knowledge Base '{n}' angelegt."


def add_to_knowledge_base(kb: str, text: str, source: str = "") -> str:
    n = slug(kb)
    if n not in load_registry():
        create_knowledge_base(n, "automatisch angelegt")
    chunks = chunk(text)
    if not chunks:
        return "Kein Text zum Speichern."
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=v,
                    payload={"text": c, "source": source, "ts": int(time.time())})
        for c, v in zip(chunks, embed(chunks))
    ]
    qdrant.upsert(f"kb_{n}", points)
    return f"{len(chunks)} Abschnitt(e) in '{n}' gespeichert."


def _search(query: str, kb: str = "", limit: int = 5) -> list:
    reg = load_registry()
    names = [slug(kb)] if kb else list(reg)
    vec, hits = embed([query])[0], []
    for n in names:
        if n in reg:
            for p in qdrant.query_points(f"kb_{n}", query=vec, limit=limit).points:
                hits.append((p.score, n, p.payload))
    return sorted(hits, key=lambda h: -h[0])[:limit]


def search_knowledge(query: str, kb: str = "") -> str:
    hits = _search(query, kb)
    return "\n\n".join(f"[{n}] ({s:.2f}) {p['text']}" for s, n, p in hits) or "Nichts gefunden."


def list_knowledge_bases() -> str:
    reg = load_registry()
    return "\n".join(f"- {n}: {d}" for n, d in reg.items()) or "Noch keine Knowledge Bases."


# ---------- Web-Lernen (optional, SSRF-geschützt) ----------
class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.out.append(data.strip())


def _is_public(host: str) -> bool:
    try:
        return all(ipaddress.ip_address(i[4][0]).is_global for i in socket.getaddrinfo(host, None))
    except Exception:
        return False


def _fetch(url: str) -> str:
    for _ in range(4):
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not _is_public(u.hostname or ""):
            raise ValueError("URL nicht erlaubt")
        r = http.get(url, follow_redirects=False, timeout=30, headers={"User-Agent": "julia-agent"})
        if r.is_redirect:
            url = urljoin(url, r.headers["location"])
            continue
        r.raise_for_status()
        return r.text[:500_000]
    raise ValueError("Zu viele Weiterleitungen")


def learn_from_url(url: str, kb: str) -> str:
    if not ALLOW_WEB:
        return "Webzugriff ist deaktiviert (AGENT_ALLOW_WEB=false)."
    p = _Text()
    p.feed(_fetch(url))
    return add_to_knowledge_base(kb, " ".join(p.out), source=url)


# ---------- Skills (reine Text-Anleitungen, kein ausführbarer Code) ----------
def save_skill(name: str, description: str, instructions: str) -> str:
    n = slug(name)
    desc = " ".join(description.split())
    (SKILLS / f"{n}.md").write_text(f"---\ndescription: {desc}\n---\n{instructions.strip()}\n", encoding="utf-8")
    return f"Skill '{n}' gespeichert."


def use_skill(name: str) -> str:
    f = SKILLS / f"{slug(name)}.md"
    return f.read_text(encoding="utf-8") if f.exists() else "Skill nicht gefunden."


def _skill_index() -> str:
    lines = []
    for f in sorted(SKILLS.glob("*.md")):
        m = re.search(r"description: (.*)", f.read_text(encoding="utf-8"))
        lines.append(f"- {f.stem}: {m.group(1) if m else ''}")
    return "\n".join(lines)


# ---------- Tool-Definitionen ----------
def _tool(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object",
                       "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
                       "required": required}}}


TOOLS = [
    _tool("list_knowledge_bases", "Zeigt alle vorhandenen Knowledge Bases.", {}, []),
    _tool("create_knowledge_base", "Legt eine neue Knowledge Base an.",
          {"name": "Kurzer Name, z. B. 'rezepte'", "description": "Wofür die KB gedacht ist"}, ["name"]),
    _tool("add_to_knowledge_base", "Speichert Text dauerhaft in einer Knowledge Base (legt sie bei Bedarf an).",
          {"kb": "Name der KB", "text": "Der zu speichernde Inhalt", "source": "Herkunft, optional"}, ["kb", "text"]),
    _tool("search_knowledge", "Durchsucht Knowledge Bases semantisch.",
          {"query": "Suchanfrage", "kb": "Optional: nur diese KB"}, ["query"]),
    _tool("learn_from_url", "Liest eine Webseite und speichert sie in einer KB.",
          {"url": "Vollständige URL", "kb": "Ziel-KB"}, ["url", "kb"]),
    _tool("save_skill", "Speichert eine wiederverwendbare Vorgehensweise als Skill.",
          {"name": "Skill-Name", "description": "Eine Zeile: wann der Skill nützt",
           "instructions": "Klare Schritt-für-Schritt-Anleitung"}, ["name", "description", "instructions"]),
    _tool("use_skill", "Lädt die Anleitung eines gespeicherten Skills.", {"name": "Skill-Name"}, ["name"]),
]
FUNCS = {f.__name__: f for f in (
    list_knowledge_bases, create_knowledge_base, add_to_knowledge_base, search_knowledge,
    learn_from_url, save_skill, use_skill)}
LEARNING = {"create_knowledge_base", "add_to_knowledge_base", "learn_from_url", "save_skill"}

SYSTEM = """Du bist Julia, eine private, lernende KI-Assistentin. Antworte in der Sprache des Nutzers.
Du kannst dir mit Werkzeugen dauerhaft Wissen und Fähigkeiten aneignen:
- Gibt dir der Nutzer Fakten, Präferenzen oder Dokumente, die später nützlich sind: lege bei Bedarf mit create_knowledge_base eine passende Knowledge Base an und speichere den Inhalt mit add_to_knowledge_base.
- Musst du etwas nachschlagen: search_knowledge.
- Hast du einen wiederholbaren Ablauf erarbeitet oder bringt der Nutzer dir einen bei: speichere ihn mit save_skill (kurze Beschreibung + klare Schritte).
- Passt ein bekannter Skill zur Aufgabe, lade ihn zuerst mit use_skill.
- Erfinde keine Quellen. Speichere keine Passwörter oder Schlüssel, außer der Nutzer verlangt es ausdrücklich."""


def _text(c) -> str:
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return c or ""


def build_system(question: str) -> str:
    parts = [SYSTEM]
    skills = _skill_index()
    if skills:
        parts.append("Bekannte Skills:\n" + skills)
    if question and load_registry():
        hits = [h for h in _search(question, limit=4) if h[0] > 0.5]
        if hits:
            parts.append("Relevantes Wissen aus deinen Knowledge Bases:\n" +
                         "\n".join(f"[{n}] {p['text']}" for _, n, p in hits))
    return "\n\n".join(parts)


def run_agent(messages: list[dict]) -> str:
    msgs = [{"role": m["role"], "content": _text(m.get("content"))}
            for m in messages if m.get("role") in ("user", "assistant")]
    question = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
    msgs.insert(0, {"role": "system", "content": build_system(question)})
    learned = []
    for _ in range(MAX_STEPS):
        r = http.post(f"{OLLAMA}/api/chat", json={
            "model": CHAT_MODEL, "messages": msgs, "tools": TOOLS, "stream": False,
            "think": THINK, "options": {"num_ctx": 8192, "temperature": 0.4}})
        r.raise_for_status()
        m = r.json()["message"]
        calls = m.get("tool_calls") or []
        if not calls:
            text = re.sub(r"<think>.*?</think>", "", m.get("content", ""), flags=re.S).strip()
            if learned:
                text += "\n\n---\n*🧠 Gelernt: " + ", ".join(learned) + "*"
            return text
        msgs.append({"role": "assistant", "content": m.get("content", ""), "tool_calls": calls})
        for c in calls:
            fn = c["function"]
            args = fn.get("arguments") or {}
            try:
                result = FUNCS[fn["name"]](**args)
                if fn["name"] in LEARNING:
                    learned.append(f"{fn['name']}({args.get('kb') or args.get('name', '')})")
            except Exception as e:
                result = f"Fehler: {e}"
            msgs.append({"role": "tool", "tool_name": fn["name"], "content": str(result)})
    return "Abbruch: zu viele Werkzeugschritte."


# ---------- OpenAI-kompatible API ----------
def check(auth: str) -> None:
    if API_KEY and auth != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Ungültiger API-Key")


class ChatReq(BaseModel):
    model_config = {"extra": "allow"}
    model: str = MODEL_ID
    messages: list[dict]
    stream: bool = False


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/v1/models")
def models(authorization: str = Header(default="")):
    check(authorization)
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}]}


@app.post("/v1/chat/completions")
def chat(req: ChatReq, authorization: str = Header(default="")):
    check(authorization)
    text = run_agent(req.messages)
    cid, created = f"chatcmpl-{uuid.uuid4().hex}", int(time.time())
    if req.stream:
        def sse(delta, finish):
            body = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": MODEL_ID,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"

        def gen():
            yield sse({"role": "assistant", "content": text}, None)
            yield sse({}, "stop")
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    return {"id": cid, "object": "chat.completion", "created": created, "model": MODEL_ID,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
