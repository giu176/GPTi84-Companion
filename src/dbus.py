"""Backwards-compat shim: re-exports the split DBUS modules so REPL calls
like `dbus.put_prog_83p(...)`, `dbus.ready_check()`, `dbus.idle()` keep
working. New code should import from wire/packet/vartypes/transfer/diag
directly.
"""

from wire import (
    TIP, RING, tip, ring,
    release, pull_low, idle, read,
    recv_bit, recv_byte, recv_byte_traced, recv_n, recv_n_traced,
    send_bit, send_byte,
    set_send_byte_gap,
)
import wire as _wire

from packet import (
    VAR, CTS, DATA, VER, SKIP, ACK, ERR, RDY, SCR, DEL, EOT, REQ, RTS,
    MACHINE_ID,
    pc_id_for, checksum, hex_bytes, packet_bytes,
    send_packet, recv_packet,
)

from vartypes import (
    T_REAL, T_LIST, T_MATRIX, T_PROG,
    list_name_82, real_name, prog_name, make_var_header,
    parse_real_parts, parse_real_str, parse_real,
    parse_real_list, parse_real_list_str,
    encode_real, encode_real_list,
)

from transfer import (
    recv_var, req_var, send_var, delete_var,
    get_l1, put_l1, put_l1_83p,
    put_real, put_real_83p,
    put_prog, put_prog_83p,
    del_real_83p, del_l1_83p,
)

from diag import (
    ready_check, ready_check_82,
    probe_rts_reply, probe_rts_real_83p, probe_rts_l1_83p,
    first_bits, snoop, go,
)


# SEND_BYTE_GAP_MS lives in wire; expose as a property-ish accessor for any
# code that read/wrote dbus.SEND_BYTE_GAP_MS at module level.
def __getattr__(name):
    if name == "SEND_BYTE_GAP_MS":
        return _wire.SEND_BYTE_GAP_MS
    raise AttributeError(name)
