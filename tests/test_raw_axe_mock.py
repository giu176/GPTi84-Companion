import raw_axe_mock as mock


def _pages(response):
    header, body = response.split(b"\n", 1)
    count = int(header.split(b":", 1)[1])
    pages = body.split(b"\x00")
    assert len(pages) == count
    for page in pages:
        assert len(page) == 128
    return pages


def _rows(response):
    rows = []
    for page in _pages(response):
        rows.extend(page[i:i + 16].decode("ascii").rstrip() for i in range(0, 128, 16))
    return rows


def _joined_content(response):
    titles = {chat["title"].upper() for chat in mock.CHATS}
    rows = [
        row for row in _rows(response)
        if row and row not in titles
    ]
    return " ".join(row.strip() for row in rows)


def test_mock_list_response_is_one_calculator_page():
    mock._reset_state()
    response = mock._response_for(b"LIST")

    assert response.startswith(b"pages:1\n")
    assert b"GPTI84 STATUS:OK" in response
    assert b" 1-ENGINEER LOG" in response
    assert b" 2-HARDWARE TEST" in response
    assert b"PAGE 1/1" in response
    assert len(_pages(response)[0]) == 128


def test_mock_open_response_is_chat_page():
    mock._reset_state()
    response = mock._response_for(b"OPEN:1")

    assert response.startswith(b"pages:")
    assert len(_pages(response)) > 1
    content = _joined_content(response)
    assert "YOU: SKETCH THE LINK PLAN" in content
    assert "AI: SCROLLING COMES NEXT" in content


def test_mock_scrolls_active_chat_by_one_visible_row():
    mock._reset_state()
    first = _pages(mock._response_for(b"OPEN:1"))[0]

    down = _pages(mock._response_for(b"DOWN"))[0]
    back_up = _pages(mock._response_for(b"UP"))[0]

    assert down != first
    assert back_up == first


def test_mock_app_chat_uses_chat_content_not_tx_diagnostics():
    mock._reset_state()
    response = mock._response_for(b"OPEN:2")

    content = _joined_content(response)
    assert "AI: SENDING" in content
    assert "THROUGH PICO WORKS" in content
    assert "TX OK means yes" not in content


def test_seeded_chats_have_varied_lengths_and_title_row_layout():
    mock._reset_state()

    page_counts = []
    for slot in range(1, 6):
        response = mock._response_for(("OPEN:%d" % slot).encode("ascii"))
        pages = _pages(response)
        page_counts.append(len(pages))
        for page in pages:
            rows = [page[i:i + 16].decode("ascii") for i in range(0, 128, 16)]
            assert len(rows) == 8
            assert rows[0].strip()

    assert min(page_counts) == 1
    assert max(page_counts) > 1


def test_mock_new_chat_is_pinned_first():
    mock._reset_state()

    response = mock._response_for(b"NEW")
    listing = mock._response_for(b"LIST")

    assert b"NEW CHAT 5" in response
    assert b" 1-NEW CHAT 5" in listing
    assert b"PAGE 2/2" in listing
    assert _pages(response)


def test_mock_send_appends_prompt_and_pending_ai_reply():
    mock._reset_state()

    response = mock._response_for(b"SEND:0:HELLO")

    assert b"YOU: HELLO" in response
    assert b"AI: this is tot" not in response
    assert _pages(response)


def test_mock_pending_ai_reply_is_released(monkeypatch):
    mock._reset_state()
    now = [1000]

    monkeypatch.setattr(mock.time, "ticks_ms", lambda: now[0])
    monkeypatch.setattr(mock.time, "ticks_add", lambda a, b: a + b)
    monkeypatch.setattr(mock.time, "ticks_diff", lambda a, b: a - b)

    mock._response_for(b"SEND:0:HELLO")
    before = mock._response_for(b"POLL:ACTIVE")
    assert b"AI: this is tot" not in before

    now[0] = 11000
    after = mock._response_for(b"POLL:ACTIVE")
    assert "AI: THIS IS TOTALLY AN AI GENERATED ANSWER" in _joined_content(after)


def test_chat_store_persists_complete_messages(tmp_path, monkeypatch):
    store = tmp_path / "chats.v1.json"
    monkeypatch.setattr(mock, "CHAT_STORE_PATH", str(store))
    mock._reset_state()

    mock._response_for(b"SEND:0:HELLO COMPLETE CHAT")
    mock._save_store()
    mock._reset_state()
    mock._load_store()

    chat = mock._find_chat("0")
    assert chat["messages"][-1] == ["You", "HELLO COMPLETE CHAT"]


def test_mock_ping_is_not_a_page_command():
    mock._reset_state()

    assert mock._response_for(b"PING").startswith(b"pages:1\n")
