from __future__ import annotations

import io
import os
import pty
import select
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"

sys.path.insert(0, str(TOOLS))

import upload_rom_icebreaker


class UploadRomIcebreakerTest(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = upload_rom_icebreaker.run(args)
        return rc, stdout.getvalue(), stderr.getvalue()

    def make_rom(self, directory: Path, name: str, payload: bytes) -> Path:
        path = directory / name
        path.write_bytes(payload)
        return path

    def loopback_roundtrip(
        self,
        payload: bytes,
        *,
        response: bytes | None,
        timeout_s: float = 0.25,
    ) -> tuple[int, str, str, bytes]:
        expected_frame, _ = upload_rom_icebreaker.build_upload_frame(payload)
        master_fd, slave_fd = pty.openpty()
        slave_name = os.ttyname(slave_fd)
        os.close(slave_fd)

        received = bytearray()
        failures: list[Exception] = []

        def worker() -> None:
            deadline = time.monotonic() + timeout_s
            try:
                while len(received) < len(expected_frame):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("timed out waiting for uploader frame")
                    readable, _, _ = select.select([master_fd], [], [], remaining)
                    if not readable:
                        continue
                    chunk = os.read(master_fd, len(expected_frame) - len(received))
                    if chunk:
                        received.extend(chunk)
                if response is None:
                    time.sleep(timeout_s * 1.5)
                else:
                    os.write(master_fd, response)
                    time.sleep(0.02)
            except Exception as exc:  # pragma: no cover - surfaced via assertion below
                failures.append(exc)
            finally:
                os.close(master_fd)

        thread = threading.Thread(target=worker)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                rom_path = self.make_rom(Path(tmpdir), "demo.gb", payload)
                rc, stdout, stderr = self.run_cli(
                    "--port",
                    slave_name,
                    "--rom",
                    str(rom_path),
                    "--timeout",
                    str(timeout_s),
                )
        finally:
            thread.join(timeout=1.0)

        if failures:
            raise failures[0]
        self.assertFalse(thread.is_alive(), "loopback helper thread should exit")
        self.assertEqual(bytes(received), expected_frame)
        return rc, stdout, stderr, bytes(received)

    def test_dry_run_reports_frame_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rom_path = self.make_rom(Path(tmpdir), "demo.gb", bytes([0x01, 0x02, 0x03, 0x04]))
            frame, crc32 = upload_rom_icebreaker.build_upload_frame(rom_path.read_bytes())
            rc, stdout, stderr = self.run_cli("--rom", str(rom_path), "--dry-run")

        self.assertEqual(rc, 0, stderr)
        self.assertEqual(stderr, "")
        self.assertIn("port=<auto-detect /dev/tty.usbserial-*>", stdout)
        self.assertIn("payload_len=4", stdout)
        self.assertIn("magic_hex=524f4d21", stdout)
        self.assertIn("length_le_hex=04000000", stdout)
        self.assertIn(f"crc32=0x{crc32:08x}", stdout)
        self.assertIn(f"frame_len={len(frame)}", stdout)
        self.assertIn(f"frame_prefix_hex={frame.hex()}", stdout)

    def test_loopback_ack_returns_zero(self) -> None:
        rc, stdout, stderr, _ = self.loopback_roundtrip(bytes(range(16)), response=b"A")
        self.assertEqual(rc, 0, stderr)
        self.assertEqual(stderr, "")
        self.assertIn("Upload OK", stdout)

    def test_loopback_nack_returns_one(self) -> None:
        rc, stdout, stderr, _ = self.loopback_roundtrip(bytes(range(8)), response=b"N")
        self.assertEqual(rc, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Upload failed (DUT reported NACK)", stderr)

    def test_timeout_returns_two(self) -> None:
        rc, stdout, stderr, _ = self.loopback_roundtrip(bytes(range(8)), response=None, timeout_s=0.1)
        self.assertEqual(rc, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Upload timed out", stderr)

    def test_missing_auto_detected_port_is_reported_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rom_path = self.make_rom(Path(tmpdir), "demo.gb", bytes([0xAA]))
            with patch.object(upload_rom_icebreaker.glob, "glob", return_value=[]):
                rc, stdout, stderr = self.run_cli("--rom", str(rom_path))

        self.assertEqual(rc, 1)
        self.assertEqual(stdout, "")
        self.assertIn("no serial port found", stderr)

    def test_oversized_rom_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rom_path = self.make_rom(Path(tmpdir), "big.gb", bytes(upload_rom_icebreaker.MAX_ROM_BYTES + 1))
            rc, stdout, stderr = self.run_cli("--rom", str(rom_path), "--dry-run")

        self.assertEqual(rc, 1)
        self.assertEqual(stdout, "")
        self.assertIn("limit is", stderr)


if __name__ == "__main__":
    unittest.main()
