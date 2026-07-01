"""Canonical pinned-chat cache for the Pico.

The phone is authoritative. This file is only a fast local snapshot of pinned
chat summaries and display state, small enough for MicroPython to parse.
"""

MAGIC = "GPTI84PINS 1"
FNV1A32_OFFSET = 0x811C9DC5
FNV1A32_PRIME = 0x01000193
DEFAULT_PATH = "pins.v1"


def fnv1a32(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    h = FNV1A32_OFFSET
    for b in data:
        h ^= b
        h = (h * FNV1A32_PRIME) & 0xFFFFFFFF
    return h


def escape_field(value):
    out = []
    for ch in str(value):
        code = ord(ch)
        if code < 0x20 or ch in "|%":
            out.append("%{:02X}".format(code))
        else:
            out.append(ch)
    return "".join(out)


def unescape_field(value):
    out = []
    i = 0
    while i < len(value):
        if value[i] == "%" and i + 2 < len(value):
            try:
                out.append(chr(int(value[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(value[i])
        i += 1
    return "".join(out)


def entry_hash(chat_id, revision, title, preview):
    return fnv1a32(
        "{}\x1f{}\x1f{}\x1f{}".format(chat_id, revision, title, preview)
    )


def catalog_hash(entries):
    parts = []
    for entry in entries:
        parts.append(
            "{}\x1f{}\x1f{}\n".format(
                entry["chat_id"], int(entry["revision"]), int(entry["hash"])
            )
        )
    return fnv1a32("".join(parts))


def encode_catalog(device, entries):
    rev = 0
    normalized = []
    for entry in entries:
        revision = int(entry["revision"])
        rev = max(rev, revision)
        h = int(entry.get("hash", entry_hash(
            entry["chat_id"], revision, entry["title"], entry["preview"]
        )))
        normalized.append({
            "chat_id": entry["chat_id"],
            "revision": revision,
            "hash": h,
            "title": entry["title"],
            "preview": entry["preview"],
        })
    cat_hash = catalog_hash(normalized)
    lines = [
        MAGIC,
        "device=" + escape_field(device),
        "catalogRev=" + str(rev),
        "catalogHash={:08x}".format(cat_hash),
    ]
    for entry in normalized:
        lines.append("|".join((
            "C",
            escape_field(entry["chat_id"]),
            str(entry["revision"]),
            "{:08x}".format(entry["hash"]),
            escape_field(entry["title"]),
            escape_field(entry["preview"]),
        )))
    return "\n".join(lines) + "\n"


def decode_catalog(text):
    lines = [line for line in str(text).splitlines() if line]
    if not lines or lines[0] != MAGIC:
        raise ValueError("invalid pins catalog")
    result = {"device": "", "catalog_rev": 0, "catalog_hash": 0, "entries": []}
    for line in lines[1:]:
        if line.startswith("device="):
            result["device"] = unescape_field(line[7:])
        elif line.startswith("catalogRev="):
            result["catalog_rev"] = int(line[11:])
        elif line.startswith("catalogHash="):
            result["catalog_hash"] = int(line[12:], 16)
        elif line.startswith("C|"):
            parts = line.split("|", 5)
            if len(parts) != 6:
                raise ValueError("invalid pins entry")
            result["entries"].append({
                "chat_id": unescape_field(parts[1]),
                "revision": int(parts[2]),
                "hash": int(parts[3], 16),
                "title": unescape_field(parts[4]),
                "preview": unescape_field(parts[5]),
            })
    return result


def load(path=DEFAULT_PATH):
    with open(path, "r") as handle:
        return decode_catalog(handle.read())


def save(catalog_text, path=DEFAULT_PATH):
    parsed = decode_catalog(catalog_text)
    with open(path, "w") as handle:
        handle.write(catalog_text)
    return parsed
