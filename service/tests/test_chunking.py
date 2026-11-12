from app.chunking import Block, build_chunks, content_hash, text_to_blocks


def test_chunks_respect_max_and_keep_heading_with_text():
    blocks = [Block("heading", "Intro", 2)] + [Block("text", "x" * 400) for _ in range(6)]
    chunks = build_chunks(blocks, max_chars=1000, min_chars=200)
    assert len(chunks) >= 3
    assert all(len(c.text) <= 1000 for c in chunks)
    assert chunks[0].section == "Intro"
    assert chunks[0].text.startswith("## Intro")


def test_long_code_block_is_split_and_fenced():
    code = "\n".join(f"line {i} " + "y" * 60 for i in range(60))
    chunks = build_chunks([Block("code", code)], max_chars=500, min_chars=100)
    assert len(chunks) > 1
    assert all(c.text.startswith("```") and c.text.endswith("```") for c in chunks)


def test_hash_changes_with_content():
    a = build_chunks([Block("text", "hallo welt")], 500, 100)
    b = build_chunks([Block("text", "hallo welt!")], 500, 100)
    assert content_hash("T", a) != content_hash("T", b)
    assert content_hash("T", a) == content_hash("T", a)


def test_wikipedia_text_stops_at_references():
    text = "Eine Einleitung.\n\n\n== Geschichte ==\nEs war einmal.\n\n== Einzelnachweise ==\nNicht aufnehmen."
    blocks = text_to_blocks(text)
    assert [b.kind for b in blocks] == ["text", "heading", "text"]
    assert blocks[1].text == "Geschichte" and blocks[1].level == 2
    assert all("Nicht aufnehmen" not in b.text for b in blocks)
