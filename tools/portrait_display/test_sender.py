# SPDX-License-Identifier: MIT
import io
from pathlib import Path
import tempfile
import unittest
import zlib

import send_frame as sender


class FakePort:
    def __init__(self, replies, write_limit=4096):
        self.replies = io.BytesIO(replies)
        self.sent = bytearray()
        self.write_limit = write_limit
    def write(self, data):
        size = min(len(data), self.write_limit)
        self.sent.extend(data[:size])
        return size
    def flush(self):
        pass
    def readline(self, size):
        return self.replies.readline(size)


class Clock:
    def __init__(self):
        self.time = 0
    def __call__(self):
        self.time += 0.0001
        return self.time


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.frame = b"\x11" * sender.FRAME_BYTES
        self.crc = zlib.crc32(self.frame)
        self.code = f"{self.crc:08X}"
    def replies(self, tail=None):
        if tail is None:
            tail = f"FRAME {self.code}\nDISPLAYING {self.code}\nDISPLAY OK {self.code}\n"
        return f"boot diagnostic\nRESET\nP36V1 EMPTY\nREADY 120000\n{tail}".encode()
    def test_success_and_partial_writes(self):
        port = FakePort(self.replies(), write_limit=37)
        sender.upload(port, self.frame, self.crc, clock=Clock())
        expected = b"\nRESET\nHELLO\n" + f"BEGIN 120000 {self.code}\n".encode() + self.frame + f"SHOW {self.code}\n".encode()
        self.assertEqual(port.sent, expected)
    def test_rejection_never_sends_show(self):
        for response in ["ERR CRC RESET_REQUIRED\n", "ERR INVALID_COLOR RESET_REQUIRED\n", "ERR RECEIVE_TIMEOUT RESET_REQUIRED\n"]:
            port = FakePort(self.replies(response))
            with self.assertRaises(sender.UploadError):
                sender.upload(port, self.frame, self.crc, clock=Clock())
            self.assertNotIn(b"SHOW ", port.sent)
    def test_wrong_frame_ack_never_sends_show(self):
        port = FakePort(self.replies("FRAME 00000000\n"))
        with self.assertRaises(sender.UploadError):
            sender.upload(port, self.frame, self.crc, clock=Clock())
        self.assertNotIn(b"SHOW ", port.sent)
    def test_display_failure_is_unknown(self):
        for reason in ["RefreshTimeout", "PowerOnNoAck", "PowerOffTimeout"]:
            port = FakePort(self.replies(f"FRAME {self.code}\nDISPLAYING {self.code}\nERR DISPLAY {reason} PANEL_STATE_UNKNOWN\n"))
            with self.assertRaisesRegex(sender.UploadError, "physical panel state is unknown"):
                sender.upload(port, self.frame, self.crc, clock=Clock())
    def test_no_device_response(self):
        port = FakePort(b"")
        with self.assertRaises(sender.UploadError):
            sender.upload(port, self.frame, self.crc, clock=Clock())
        self.assertNotIn(b"BEGIN", port.sent)
    def test_missing_display_ack_is_unknown(self):
        port = FakePort(self.replies(f"FRAME {self.code}\n"))
        with self.assertRaisesRegex(sender.UploadError, "physical panel state is unknown"):
            sender.upload(port, self.frame, self.crc, clock=Clock())
    def test_power_guard_never_started(self):
        port = FakePort(self.replies(f"FRAME {self.code}\nDISPLAYING {self.code}\nERR DISPLAY PowerUnsafe NOT_STARTED\n"))
        with self.assertRaisesRegex(sender.UploadError, "no refresh started"):
            sender.upload(port, self.frame, self.crc, clock=Clock())
    def test_zero_write(self):
        port = FakePort(b"", write_limit=0)
        with self.assertRaises(sender.UploadError):
            sender.upload(port, self.frame, self.crc, clock=Clock())
    def test_invalid_memory_frame(self):
        for data, crc in [(b"", 0), (self.frame, self.crc ^ 1), (b"\x44" * sender.FRAME_BYTES, zlib.crc32(b"\x44" * sender.FRAME_BYTES))]:
            port = FakePort(b"")
            with self.assertRaises(sender.UploadError):
                sender.upload(port, data, crc, clock=Clock())
            self.assertEqual(port.sent, b"")
    def test_file_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "frame.bin"
            for data in [b"", self.frame[:-1], self.frame + b"0", b"\x44" * sender.FRAME_BYTES]:
                file.write_bytes(data)
                with self.assertRaises(sender.UploadError):
                    sender.inspect_frame(file)
            file.write_bytes(self.frame)
            self.assertEqual(sender.inspect_frame(file), (self.frame, self.crc))
    def test_bad_responses(self):
        for response in [b"\xff\n", b"A" * 256 + b"\n", b"partial"]:
            with self.assertRaises(sender.UploadError):
                sender.wait_line(FakePort(response), "RESET", 1, clock=Clock())


if __name__ == "__main__":
    unittest.main()
