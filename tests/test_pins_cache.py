import pins_cache


def test_fnv1a32_known_fixture():
    assert pins_cache.fnv1a32("hello") == 0x4F9F2CAB


def test_catalog_roundtrip_escapes_fields():
    text = pins_cache.encode_catalog(
        "phone|one",
        [{
            "chat_id": "c|1",
            "revision": 123,
            "title": "A|B",
            "preview": "line\npercent %",
        }],
    )

    assert text.startswith("GPTI84PINS 1\n")
    assert "device=phone%7Cone" in text
    assert "C|c%7C1|123|" in text
    assert "A%7CB" in text
    assert "line%0Apercent %25" in text

    parsed = pins_cache.decode_catalog(text)

    assert parsed["device"] == "phone|one"
    assert parsed["catalog_rev"] == 123
    assert parsed["entries"][0]["chat_id"] == "c|1"
    assert parsed["entries"][0]["title"] == "A|B"
    assert parsed["entries"][0]["preview"] == "line\npercent %"
