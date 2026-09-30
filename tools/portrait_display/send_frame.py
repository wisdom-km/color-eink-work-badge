#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Explicit USB upload + SHOW for the isolated P1 3.6E diagnostic firmware.

No port autodetection, flashing, network requests or credentials. Requires
pyserial only for a real port. --dry-run performs file checks without opening IO.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zlib

FRAME_BYTES = 120000
COLORS = frozenset((0, 1, 2, 3, 5, 6))


class UploadError(RuntimeError):
    pass


def inspect_frame(path):
    path = Path(path)
    if path.stat().st_size != FRAME_BYTES:
        raise UploadError("Expected exactly 120000 bytes for the native 400x600 frame")
    data = path.read_bytes()
    if len(data) != FRAME_BYTES:
        raise UploadError("Frame changed while reading")
    if any((byte >> 4) not in COLORS or (byte & 15) not in COLORS for byte in data):
        raise UploadError("Frame contains invalid panel color codes; do not send portrait-indexed.bin")
    return data, zlib.crc32(data)


def write_all(port, data, timeout=10.0, clock=time.monotonic):
    deadline = clock() + timeout
    position = 0
    while position < len(data):
        if clock() >= deadline:
            raise UploadError("USB write timed out; no SHOW was sent")
        written = port.write(data[position:position + 4096])
        if not isinstance(written, int) or written <= 0 or written > min(4096, len(data) - position):
            raise UploadError("USB short/invalid write; no SHOW was sent")
        position += written


def wait_line(port, expected, timeout, clock=time.monotonic, ignore_errors=False):
    deadline = clock() + timeout
    while clock() < deadline:
        raw = port.readline(256)
        if not raw:
            continue
        if len(raw) >= 256 or not raw.endswith(b"\n"):
            raise UploadError("Malformed or oversized device response")
        try:
            line = raw.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise UploadError("Non-ASCII device response") from error
        if line == expected:
            return
        if line.startswith("ERR") and not ignore_errors:
            raise UploadError(line)
    raise UploadError(f"Timed out waiting for {expected!r}")


def upload(port, data, crc, *, clock=time.monotonic):
    if len(data) != FRAME_BYTES or zlib.crc32(data) != crc:
        raise UploadError("Invalid in-memory frame length or CRC")
    if any((byte >> 4) not in COLORS or (byte & 15) not in COLORS for byte in data):
        raise UploadError("Invalid in-memory frame palette")
    code = f"{crc:08X}"
    # A leading newline discards any partial old command. If a previous transfer
    # was interrupted, first wait longer than its 3 s inactivity timeout; only
    # then retry RESET. Do not keep resetting the byte timer in a tight loop.
    for attempt in range(2):
        write_all(port, b"\nRESET\n", clock=clock)
        try:
            wait_line(port, "RESET", 5.0, clock=clock, ignore_errors=True)
            break
        except UploadError:
            if attempt == 1:
                raise
    write_all(port, b"HELLO\n", clock=clock)
    wait_line(port, "P36V1 EMPTY", 3.0, clock=clock)
    write_all(port, f"BEGIN 120000 {code}\n".encode("ascii"), clock=clock)
    wait_line(port, "READY 120000", 3.0, clock=clock)
    write_all(port, data, timeout=25.0, clock=clock)
    wait_line(port, f"FRAME {code}", 5.0, clock=clock)
    # Receiving a valid frame alone never starts high voltage. SHOW is a separate
    # explicit command, emitted only after the device validates the whole frame.
    write_all(port, f"SHOW {code}\n".encode("ascii"), clock=clock)
    try:
        wait_line(port, f"DISPLAYING {code}", 5.0, clock=clock)
        wait_line(port, f"DISPLAY OK {code}", 80.0, clock=clock)
    except UploadError as error:
        if "PowerUnsafe NOT_STARTED" in str(error):
            raise UploadError("PowerUnsafe: power check failed; no refresh started") from error
        raise UploadError(f"{error}; refresh may have started, physical panel state is unknown") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frame", type=Path)
    parser.add_argument("--port", help="Explicit serial port, e.g. COM5 or /dev/ttyACM0")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, do not open a port or refresh")
    args = parser.parse_args()
    if not args.dry_run and not args.port:
        parser.error("--port is required unless --dry-run is used")
    try:
        data, crc = inspect_frame(args.frame)
        report = {"bytes": len(data), "crc32_ieee": f"{crc:08x}",
                  "sha256": hashlib.sha256(data).hexdigest(), "dry_run": args.dry_run,
                  "flash_persistence": False, "physical_image_inspected": False}
        if not args.dry_run:
            try:
                import serial
            except ImportError as error:
                raise UploadError("Install pyserial==3.5 to use an explicit USB port") from error
            # Deliberately no port scanning, firmware flashing or DTR toggling.
            # Opening a serial port can still affect board-specific reset wiring.
            with serial.Serial(args.port, 115200, timeout=0.2, write_timeout=3.0,
                               rtscts=False, dsrdtr=False) as port:
                upload(port, data, crc)
            report["device_reported"] = "DISPLAY OK"
        print(json.dumps(report, indent=2))
    except (OSError, UploadError) as error:
        parser.exit(2, f"Upload stopped: {error}\n")


if __name__ == "__main__":
    main()
