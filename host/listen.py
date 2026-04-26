#!/usr/bin/env python3
"""Connect to the ESP bridge and log every byte received from the calc."""

import socket
import sys
import time

ESP_IP = "10.0.0.133"
ESP_PORT = 8888

def main():
    print(f"connecting to {ESP_IP}:{ESP_PORT}...")
    s = socket.create_connection((ESP_IP, ESP_PORT), timeout=10)
    s.settimeout(None)
    print("connected. waiting for calc bytes (Ctrl-C to quit).")

    t0 = time.time()
    total = 0
    while True:
        data = s.recv(4096)
        if not data:
            print("bridge closed connection.")
            return
        for b in data:
            dt = time.time() - t0
            print(f"  +{dt:7.3f}s  byte#{total:4d}  0x{b:02x}  {b:3d}  {chr(b) if 32 <= b < 127 else '.'!r}")
            total += 1

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ndone.")
        sys.exit(0)
