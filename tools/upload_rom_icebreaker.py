from __future__ import annotations

import argparse
import binascii
import errno
import glob
import os
import select
import sys
import termios
import time
import tty
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


MAGIC = b"ROM!"
MAX_ROM_BYTES = 32 * 1024
DEFAULT_BAUDRATE = 115_200
DEFAULT_TIMEOUT_S = 10.0
AUTO_PORT_GLOBS = ("/dev/tty.usbserial-*",)

ACK_BYTE = b"A"
NACK_BYTE = b"N"

_BAUD_RATES = {
    9_600: termios.B9600,
    19_200: termios.B19200,
    38_400: termios.B38400,
    57_600: termios.B57600,
    115_200: termios.B115200,
    230_400: getattr(termios, "B230400", termios.B115200),
}


class UploadError(Exception):
    pass


@dataclass(frozen=True)
class UploadPlan:
    rom_path: Path
    payload: bytes
    crc32: int
    frame: bytes
    port: str | None
    baudrate: int
    timeout_s: float
    dry_run: bool


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload a ROM to an iCEBreaker UART ROM bitstream.")
    parser.add_argument("--port", help="serial device path; defaults to auto-detecting /dev/tty.usbserial-*")
    parser.add_argument("--rom", type=Path, required=True, help="ROM image to upload")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE, help="UART baud rate")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="ACK wait timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="print the planned upload frame without touching serial hardware")
    return parser.parse_args(argv)


def crc32_bytes(payload: bytes) -> int:
    return binascii.crc32(payload) & 0xFFFFFFFF


def build_upload_frame(payload: bytes) -> tuple[bytes, int]:
    crc32 = crc32_bytes(payload)
    length = len(payload).to_bytes(4, byteorder="little", signed=False)
    crc_bytes = crc32.to_bytes(4, byteorder="little", signed=False)
    return MAGIC + length + payload + crc_bytes, crc32


def load_rom(path: Path) -> bytes:
    try:
        payload = path.read_bytes()
    except FileNotFoundError as exc:
        raise UploadError(f"ROM file not found: {path}") from exc
    if len(payload) > MAX_ROM_BYTES:
        raise UploadError(f"ROM is {len(payload)} bytes; limit is {MAX_ROM_BYTES} bytes")
    return payload


def detect_default_port() -> str:
    matches: list[str] = []
    for pattern in AUTO_PORT_GLOBS:
        matches.extend(sorted(glob.glob(pattern)))
    unique = sorted(dict.fromkeys(matches))
    if not unique:
        raise UploadError("no serial port found; pass --port or attach an iCEBreaker exposing /dev/tty.usbserial-*")
    if len(unique) > 1:
        raise UploadError("multiple candidate serial ports found; pass --port explicitly")
    return unique[0]


def resolve_port(port: str | None, *, dry_run: bool) -> str | None:
    if port:
        return port
    if dry_run:
        return None
    return detect_default_port()


def build_plan(args: argparse.Namespace) -> UploadPlan:
    if args.baudrate not in _BAUD_RATES:
        raise UploadError(f"unsupported baudrate {args.baudrate}; supported values: {', '.join(str(rate) for rate in sorted(_BAUD_RATES))}")
    if args.timeout <= 0:
        raise UploadError("timeout must be positive")
    payload = load_rom(args.rom)
    frame, crc32 = build_upload_frame(payload)
    return UploadPlan(
        rom_path=args.rom,
        payload=payload,
        crc32=crc32,
        frame=frame,
        port=resolve_port(args.port, dry_run=args.dry_run),
        baudrate=args.baudrate,
        timeout_s=args.timeout,
        dry_run=args.dry_run,
    )


def configure_serial(fd: int, baudrate: int) -> None:
    attrs = termios.tcgetattr(fd)
    tty.setraw(fd)
    attrs = termios.tcgetattr(fd)
    speed = _BAUD_RATES[baudrate]
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)
    if hasattr(termios, "CRTSCTS"):
        attrs[2] &= ~termios.CRTSCTS
    attrs[2] |= termios.CLOCAL | termios.CREAD | termios.CS8
    attrs[3] = 0
    attrs[4] = speed
    attrs[5] = speed
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    os.set_blocking(fd, False)


def open_serial_port(path: str, baudrate: int) -> int:
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except FileNotFoundError as exc:
        raise UploadError(f"serial port not found: {path}") from exc
    except OSError as exc:
        raise UploadError(f"failed to open serial port {path}: {exc.strerror or exc}") from exc
    try:
        configure_serial(fd, baudrate)
    except Exception:
        os.close(fd)
        raise
    return fd


def write_all(fd: int, data: bytes, *, timeout_s: float) -> None:
    deadline = _deadline(timeout_s)
    offset = 0
    while offset < len(data):
        remaining = _remaining(deadline)
        if remaining == 0:
            raise UploadError("upload timed out while sending frame")
        _, writable, _ = select.select([], [fd], [], remaining)
        if not writable:
            continue
        try:
            written = os.write(fd, data[offset:])
        except BlockingIOError:
            continue
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                continue
            raise UploadError(f"write failed on serial port: {exc.strerror or exc}") from exc
        offset += written


def read_response(fd: int, *, timeout_s: float) -> bytes:
    deadline = _deadline(timeout_s)
    while True:
        remaining = _remaining(deadline)
        if remaining == 0:
            raise TimeoutError("Upload timed out")
        readable, _, _ = select.select([fd], [], [], remaining)
        if not readable:
            continue
        try:
            data = os.read(fd, 1)
        except BlockingIOError:
            continue
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                continue
            raise UploadError(f"read failed on serial port: {exc.strerror or exc}") from exc
        if data:
            return data


def execute_upload(plan: UploadPlan) -> int:
    if plan.port is None:
        raise UploadError("dry-run plan has no concrete port to execute")
    fd = open_serial_port(plan.port, plan.baudrate)
    try:
        write_all(fd, plan.frame, timeout_s=plan.timeout_s)
        response = read_response(fd, timeout_s=plan.timeout_s)
    except TimeoutError:
        print("Upload timed out", file=sys.stderr)
        return 2
    finally:
        os.close(fd)

    if response == ACK_BYTE:
        print("Upload OK")
        return 0
    if response == NACK_BYTE:
        print("Upload failed (DUT reported NACK)", file=sys.stderr)
        return 1
    print(f"Upload failed (unexpected response 0x{response[0]:02x})", file=sys.stderr)
    return 1


def print_dry_run(plan: UploadPlan) -> None:
    length_bytes = len(plan.payload).to_bytes(4, byteorder="little", signed=False)
    crc_bytes = plan.crc32.to_bytes(4, byteorder="little", signed=False)
    preview_len = min(len(plan.frame), 32)
    preview = plan.frame[:preview_len].hex()
    if len(plan.frame) > preview_len:
        preview += "..."

    print(f"port={plan.port or '<auto-detect /dev/tty.usbserial-*>'}")
    print(f"rom={plan.rom_path}")
    print(f"baudrate={plan.baudrate}")
    print(f"timeout_s={plan.timeout_s:g}")
    print(f"payload_len={len(plan.payload)}")
    print(f"magic_hex={MAGIC.hex()}")
    print(f"length_le_hex={length_bytes.hex()}")
    print(f"crc32=0x{plan.crc32:08x}")
    print(f"crc32_le_hex={crc_bytes.hex()}")
    print(f"frame_len={len(plan.frame)}")
    print(f"frame_prefix_hex={preview}")


def _deadline(timeout_s: float) -> float:
    return time.monotonic() + timeout_s


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return 0
    return remaining


def run(argv: Sequence[str] | None = None) -> int:
    try:
        plan = build_plan(parse_args(argv))
    except UploadError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if plan.dry_run:
        print_dry_run(plan)
        return 0
    return execute_upload(plan)


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
