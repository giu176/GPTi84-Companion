"""Phone-free raw Axe link test responder."""

import time

import machine
import raw_axe_protocol as raw
import wire

try:
    import ujson as json
except ImportError:
    import json

LED = machine.Pin("LED", machine.Pin.OUT)
_last_toggle_ms = 0
_led_on = False
_last_idle_log_ms = 0
_last_idle_state = None
LOG_PATH = "raw_axe_mock.log"
CHAT_STORE_PATH = "chats.v1.json"
_pending_replies = []
_active_chat_offset = 0


AI_REPLY = "this is totally an AI generated answer"
ROW_WIDTH = 16
ROWS_PER_PAGE = 8
CHAT_TEXT_ROWS = ROWS_PER_PAGE - 1
LIST_BODY_ROWS = ROWS_PER_PAGE - 2

def _seed_chats():
    return [
        {
            "id": "0",
            "title": "Engineer log",
            "messages": [
                ("You", "Sketch the link plan"),
                ("AI", "Use Pico as relay"),
                ("You", "Keep UI readable"),
                ("AI", "Title plus chat"),
                ("You", "Add prompt flow"),
                ("AI", "Prompt returns here"),
                ("You", "Seed long history"),
                ("AI", "Scrolling comes next"),
            ],
        },
        {
            "id": "1",
            "title": "Hardware test",
            "messages": [
                ("You", "Phone is offline"),
                ("AI", "Pico mock active"),
                ("You", "Can I send?"),
                ("AI", "Sending through Pico works"),
                ("You", "Need AI reply"),
                ("AI", AI_REPLY),
            ],
        },
        {
            "id": "2",
            "title": "Tiny check",
            "messages": [
                ("You", "Ping"),
                ("AI", "Pong from Pico"),
            ],
        },
        {
            "id": "3",
            "title": "Long maths",
            "messages": [
                ("You", "Explain slope intercept form"),
                ("AI", "A line can be written as y equals mx plus b"),
                ("You", "What is m"),
                ("AI", "m is the slope or change in y over change in x"),
                ("You", "What is b"),
                ("AI", "b is the y intercept where x is zero"),
                ("You", "Give a test value"),
                ("AI", "For y equals 2x plus 3, x of 4 gives 11"),
            ],
        },
        {
            "id": "4",
            "title": "Prompt saves",
            "messages": [
                ("AI", "Use this chat to verify that calculator prompts persist"),
            ],
        },
    ]


CHATS = _seed_chats()

_active_chat_id = "0"


def _reset_state():
    global CHATS, _active_chat_id, _pending_replies, _active_chat_offset
    CHATS = _seed_chats()
    _active_chat_id = "0"
    _pending_replies = []
    _active_chat_offset = 0


def _store_doc():
    return {
        "version": 1,
        "activeChatId": _active_chat_id,
        "chats": CHATS,
    }


def _load_store():
    global CHATS, _active_chat_id, _active_chat_offset
    try:
        with open(CHAT_STORE_PATH, "r") as handle:
            doc = json.load(handle)
        if doc.get("version") != 1:
            raise ValueError("bad chat store version")
        chats = doc.get("chats")
        if not isinstance(chats, list) or not chats:
            raise ValueError("empty chat store")
        CHATS = chats
        _active_chat_id = doc.get("activeChatId") or CHATS[0]["id"]
        _active_chat_offset = 0
    except Exception:
        CHATS = _seed_chats()
        _active_chat_id = "0"
        _active_chat_offset = 0
        _save_store()


def _save_store():
    try:
        with open(CHAT_STORE_PATH, "w") as handle:
            json.dump(_store_doc(), handle)
    except Exception as error:
        _log("store save error %s" % error)


def _pages(*pages):
    return ("pages:%d\n" % len(pages)).encode("ascii") + b"\x00".join(
        page.encode("ascii") for page in pages
    )


def _log(message):
    line = "%d %s" % (time.ticks_ms(), message)
    print(line)
    try:
        with open(LOG_PATH, "a") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def _reset_log():
    try:
        with open(LOG_PATH, "w") as handle:
            handle.write("")
    except Exception:
        pass


def _page_lines(*lines):
    rows = []
    for line in lines[:ROWS_PER_PAGE]:
        rows.append(str(line)[:ROW_WIDTH].ljust(ROW_WIDTH))
    while len(rows) < ROWS_PER_PAGE:
        rows.append(" " * ROW_WIDTH)
    return "".join(rows)


def _clean_text(text):
    return str(text).replace("\r", " ").replace("\n", " ").upper()


def _wrap_text(text, width=ROW_WIDTH):
    text = _clean_text(text)
    words = text.split(" ")
    rows = []
    current = ""
    for word in words:
        if word == "":
            continue
        while len(word) > width:
            if current:
                rows.append(current)
                current = ""
            rows.append(word[:width])
            word = word[width:]
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            rows.append(current)
            current = word
    if current:
        rows.append(current)
    if not rows:
        rows.append("")
    return rows


def _render_message_rows(sender, text):
    prefix = "%s: " % sender
    rows = []
    wrapped = _wrap_text(prefix + _clean_text(text), ROW_WIDTH)
    for index, row in enumerate(wrapped):
        if index == 0:
            rows.append(row)
        else:
            rows.append("  " + row if len(row) <= ROW_WIDTH - 2 else row)
    return rows


def _chat_rows(chat):
    rows = []
    for sender, text in chat["messages"]:
        rows.extend(_render_message_rows(sender, text))
    return rows


def _chat_pages(chat):
    title = _clean_text(chat["title"])[:ROW_WIDTH]
    content = _chat_rows(chat)
    pages = []
    for start in range(0, max(1, len(content)), CHAT_TEXT_ROWS):
        chunk = content[start:start + CHAT_TEXT_ROWS]
        pages.append(_page_lines(title, *chunk))
    return pages


def _chat_window_page(chat, offset):
    title = _clean_text(chat["title"])[:ROW_WIDTH]
    content = _chat_rows(chat)
    max_offset = max(0, len(content) - CHAT_TEXT_ROWS)
    offset = max(0, min(offset, max_offset))
    return _page_lines(title, *content[offset:offset + CHAT_TEXT_ROWS])


def _find_chat(chat_id):
    for chat in CHATS:
        if chat["id"] == chat_id:
            return chat
    return None


def _pending_delay_ms():
    return 1000 + (time.ticks_ms() % 9000)


def _process_pending():
    global _pending_replies
    if not _pending_replies:
        return
    now = time.ticks_ms()
    remaining = []
    for due_ms, chat_id in _pending_replies:
        if time.ticks_diff(now, due_ms) >= 0:
            chat = _find_chat(chat_id)
            if chat is not None:
                chat["messages"].append(("AI", AI_REPLY))
                _save_store()
                _log("fake reply chat id=%s" % chat_id)
        else:
            remaining.append((due_ms, chat_id))
    _pending_replies = remaining


def _list_page():
    return _list_pages()[0]


def _list_pages():
    _process_pending()
    entries = [" 0-NEW CHAT"]
    for index, chat in enumerate(CHATS, start=1):
        entries.append(" %d-%s" % (index, _clean_text(chat["title"])))
    page_count = max(1, (len(entries) + LIST_BODY_ROWS - 1) // LIST_BODY_ROWS)
    pages = []
    for page_index in range(page_count):
        start = page_index * LIST_BODY_ROWS
        body = entries[start:start + LIST_BODY_ROWS]
        footer = "PAGE %d/%d" % (page_index + 1, page_count)
        pages.append(_page_lines("GPTI84 STATUS:OK", *body, footer))
    return pages


def _chat_page(chat):
    _process_pending()
    return _chat_pages(chat)


def _scroll_active(delta):
    global _active_chat_offset
    _process_pending()
    chat = _find_chat(_active_chat_id) or CHATS[0]
    content = _chat_rows(chat)
    max_offset = max(0, len(content) - CHAT_TEXT_ROWS)
    _active_chat_offset = max(0, min(_active_chat_offset + delta, max_offset))
    return _chat_window_page(chat, _active_chat_offset)


def _new_chat():
    global _active_chat_id, _active_chat_offset
    _process_pending()
    chat_id = str(len(CHATS))
    chat = {
        "id": chat_id,
        "title": "New chat %s" % chat_id,
        "messages": [("AI", "Send a prompt")],
    }
    CHATS.insert(0, chat)
    _active_chat_id = chat_id
    _active_chat_offset = 0
    _save_store()
    _log("created chat id=%s" % chat_id)
    return chat


def _send_prompt(chat_id, prompt):
    global _active_chat_id, _pending_replies, _active_chat_offset
    _process_pending()
    if chat_id == "ACTIVE":
        chat_id = _active_chat_id
    chat = _find_chat(chat_id)
    if chat is None:
        chat = _new_chat()
    chat["messages"].append(("You", prompt or "HELLO"))
    due_ms = time.ticks_add(time.ticks_ms(), _pending_delay_ms())
    _pending_replies.append((due_ms, chat["id"]))
    _active_chat_id = chat["id"]
    _active_chat_offset = max(0, len(_chat_rows(chat)) - CHAT_TEXT_ROWS)
    _save_store()
    _log("send chat id=%s prompt=%s reply_due=%d" % (
        chat["id"],
        prompt or "HELLO",
        due_ms,
    ))
    return chat


def _response_for(payload):
    global _active_chat_id, _active_chat_offset
    _process_pending()
    text = bytes(payload).decode("ascii")
    if text == "LIST":
        return _pages(*_list_pages())
    if text == "NEW":
        return _pages(*_chat_page(_new_chat()))
    if text == "ACTIVE" or text == "POLL:ACTIVE":
        return _pages(*_chat_page(_find_chat(_active_chat_id) or CHATS[0]))
    if text == "UP":
        return _pages(_scroll_active(-1))
    if text == "DOWN":
        return _pages(_scroll_active(1))
    if text.startswith("SEND:"):
        parts = text.split(":", 2)
        chat_id = parts[1] if len(parts) > 1 else _active_chat_id
        prompt = parts[2] if len(parts) > 2 else "HELLO"
        return _pages(*_chat_page(_send_prompt(chat_id, prompt)))
    if text.startswith("OPEN:"):
        slot = text.split(":", 1)[1]
        if slot == "0":
            return _pages(*_chat_page(_new_chat()))
        try:
            index = int(slot) - 1
        except ValueError:
            index = 0
        if 0 <= index < len(CHATS):
            _active_chat_id = CHATS[index]["id"]
            _active_chat_offset = 0
            _save_store()
            _log("opened chat id=%s slot=%s" % (_active_chat_id, slot))
            return _pages(*_chat_page(CHATS[index]))
        return _pages(_page_lines("Unknown chat", text, "Pico OK Mock"))
    return _pages(
        _page_lines("Unknown command", text[:16], "Pico OK Mock")
    )


def _tick_idle_led():
    global _last_toggle_ms, _led_on, _last_idle_log_ms, _last_idle_state
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_toggle_ms) >= 500:
        _led_on = not _led_on
        LED.value(_led_on)
        _last_toggle_ms = now
    state = wire.read()
    if state != _last_idle_state or time.ticks_diff(now, _last_idle_log_ms) >= 5000:
        _last_idle_state = state
        _last_idle_log_ms = now
        _log("idle line tip=%d ring=%d" % (state[0], state[1]))


def _mark_activity():
    global _last_toggle_ms, _led_on
    _led_on = True
    LED.value(1)
    _last_toggle_ms = time.ticks_ms()


def run():
    _reset_log()
    _load_store()
    _log("raw-axe-mock boot")
    _log("waiting for calculator frames")
    wire.idle()
    wire.set_edge_logger(_log)
    while True:
        try:
            frame = raw.read_frame(wire.recv_byte, timeout_ms=250)
            if frame is None:
                _tick_idle_led()
                time.sleep_ms(10)
                continue
            frame_type, payload = frame
            _mark_activity()
            if frame_type != raw.REQUEST:
                _log("non-request frame type=%s" % frame_type)
                raw.write_frame(
                    wire.send_byte,
                    raw.ERROR,
                    b"EXPECTED REQUEST",
                    timeout_ms=1000,
                )
                continue
            _log("request %r" % (payload,))
            if payload == b"PING":
                _log("ping ok")
                continue
            response = _response_for(payload)
            if raw.write_frame(
                wire.send_byte,
                raw.RESPONSE,
                response,
                timeout_ms=1000,
            ):
                _log("response sent bytes=%d" % len(response))
            else:
                _log("response send failed bytes=%d" % len(response))
        except Exception as error:
            _log("error %s" % error)
            try:
                raw.write_frame(
                    wire.send_byte,
                    raw.ERROR,
                    str(error).encode("ascii")[:128],
                    timeout_ms=1000,
                )
            except Exception:
                pass
