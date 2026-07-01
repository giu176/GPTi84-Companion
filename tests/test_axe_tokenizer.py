import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bastok  # noqa: E402


def test_axe_graphics_tokens_are_encoded():
    body = bastok.tokenize(
        ".GPTI84\n"
        "Full\n"
        "Fix 5\n"
        "Fix 9\n"
        "ClrDraw\n"
        "Line(0,8,95,8)\n"
        "Text(1,0,\"GPTI84\")\n"
        "DispGraph\n"
    )

    assert bytes([0xBB, 0x67]) in body  # Full
    assert bytes([0x73, 0x35]) in body  # Fix 5
    assert bytes([0x73, 0x39]) in body  # Fix 9
    assert bytes([0x85]) in body  # ClrDraw
    assert bytes([0x9C]) in body  # Line(
    assert bytes([0x93]) in body  # Text(
    assert bytes([0xDF]) in body  # DispGraph


def test_axe_link_tokens_are_encoded():
    body = bastok.tokenize("Send(126,30000)\nGet(\n0->port\n")

    assert bytes([0xE7]) in body  # Send(
    assert bytes([0xE8]) in body  # Get(
    assert bytes([0xFB]) in body  # port


def test_axe_buffer_and_memory_tokens_are_encoded():
    body = bastok.tokenize("Buff(32)->B\n0->{B+26}\nG->{B+K}\n")

    assert bytes([0xB3]) in body  # Buff(
    assert bytes([0x08]) in body  # {
    assert bytes([0x09]) in body  # }


def test_axe_source_does_not_bake_pico_chat_titles():
    source = (ROOT / "programs" / "axe_gpti84" / "AXGPTI84.basic").read_text()

    forbidden = [
        "ENGINEER LOG",
        "HARDWARE TEST",
        "TINY CHECK",
        "LONG MATHS",
        "PROMPT SAVES",
        "MATH HELP",
        "STUDY PLAN",
        "QUICK ASK",
        "LOREM IPSUM",
        "DOLOR SIT",
        "CONSECUTOR",
    ]
    for text in forbidden:
        assert text not in source


def test_axe_source_is_gui_only_key_wait_loop():
    source = (ROOT / "programs" / "axe_gpti84" / "AXGPTI84.basic").read_text()

    assert "Repeat getKey\nEnd\nIf getKey(1)" in source
    assert "Send(" not in source
    assert "Get(" not in source
    assert "Buff(32)->B" in source
    assert "Repeat K=26" in source
    assert "0->{B+26}" in source
    assert 'Text(0,0,"CHATS")' in source
    assert "sub(HR)" in source
    assert "Lbl HR" in source
    assert "20->N" in source
    assert "1->P" in source
    assert "Lbl TP" in source
    assert "4->P" in source
    assert "101->P" in source
    assert "If X=3" in source
    assert "Lbl PG" in source
    assert "47->{B+4}" in source
    assert "B+5->Y" in source
    assert "If V=1\nC->I\nsub(TP)\nP-1->X\nIf O<X" in source
    assert 'Text(0,0,"SHAKESPEARE")' in source
    assert 'Text(0,8,"TO BE OR NOT TO BE THAT IS")' in source
    assert "CHOOSE TEXT" not in source
    assert "RIGHT TO PROMPT" not in source
    assert "2->T\n2->V" in source
    assert "If T=2\nU+1->U\nN+1->N\n1->C\nEnd\n1->T" in source
    assert "sub(A)" not in source
    assert "sub(C)" not in source
    assert "Lbl A" not in source
    assert "Lbl C" not in source
    assert "sub(J)" not in source
    assert "Line(" in source
    assert "DispGraph" in source
    assert "30000" not in source
    assert "4000" not in source
