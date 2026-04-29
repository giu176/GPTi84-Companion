"""WebSocket front-end that proxies framed-TCP to the local relay.

Run on the same host as relay_server.py. Each inbound WS connection opens
a paired TCP connection to the relay; binary WS messages are forwarded as
already-framed bytes (4-byte big-endian length + body, the relay's native
format) and reverse traffic is reassembled into discrete WS messages so a
single TCP frame maps 1:1 to a single WS message.

Sits behind cloudflared, which proxies https://relay.xandwr.com/ to
http://localhost:8080 (this server). Cloudflare Access enforces the
service-token gate at the edge, so this process trusts that anyone who
reached it is authorised.
"""

import argparse
import asyncio
import struct
import sys

import websockets


async def _read_frame(reader):
    hdr = await reader.readexactly(4)
    (length,) = struct.unpack(">I", hdr)
    body = await reader.readexactly(length)
    return hdr + body


async def _ws_to_tcp(ws, writer):
    async for msg in ws:
        if isinstance(msg, str):
            continue
        writer.write(msg)
        await writer.drain()


async def _tcp_to_ws(reader, ws):
    while True:
        try:
            frame = await _read_frame(reader)
        except asyncio.IncompleteReadError:
            return
        await ws.send(frame)


async def handle(ws, relay_host, relay_port):
    peer = ws.remote_address
    print("ws: connected %s path=%s" % (peer, ws.request.path), flush=True)
    try:
        reader, writer = await asyncio.open_connection(relay_host, relay_port)
    except OSError as e:
        print("ws: relay dial failed (%s); closing %s" % (e, peer), flush=True)
        await ws.close(code=1011, reason="relay unavailable")
        return
    try:
        await asyncio.gather(
            _ws_to_tcp(ws, writer),
            _tcp_to_ws(reader, ws),
            return_exceptions=False,
        )
    except websockets.ConnectionClosed:
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        print("ws: disconnected %s" % (peer,), flush=True)


async def main_async(args):
    async def handler(ws):
        await handle(ws, args.relay_host, args.relay_port)

    print("ws_bridge: listening on %s:%d -> relay %s:%d" % (
        args.host, args.port, args.relay_host, args.relay_port), flush=True)
    async with websockets.serve(handler, args.host, args.port):
        await asyncio.Future()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--relay-host", default="127.0.0.1")
    ap.add_argument("--relay-port", type=int, default=9999)
    args = ap.parse_args(argv)
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
