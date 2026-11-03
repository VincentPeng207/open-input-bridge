"""Regression tests for LY-03 action mapping and dry-run WebSocket protocol."""
import base64
import importlib.util
import json
import os
import pathlib
import shutil
import socket
import struct
import subprocess
import sys
import time
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).with_name("ly03_voice_bridge_ws_v1.py")
spec = importlib.util.spec_from_file_location("kring_ws_bridge", SOURCE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def read_exact(sock, size):
    chunks = []
    while size:
        part = sock.recv(size)
        if not part:
            raise AssertionError("WebSocket disconnected unexpectedly")
        chunks.append(part)
        size -= len(part)
    return b"".join(chunks)


def send_action(sock, idx, cmd):
    payload = json.dumps({"type": "action", "id": f"test:{idx}", "cmd": cmd}).encode()
    mask = os.urandom(4)
    header = bytes([0x81, 0x80 | len(payload)])
    sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
    b1, b2 = read_exact(sock, 2)
    assert b1 == 0x81 and b2 < 126, (b1, b2)
    return json.loads(read_exact(sock, b2))


class TestMapping(unittest.TestCase):
    def test_phone_address_display_prefers_wifi_and_hides_virtual(self):
        # Synthetic examples: a VPN/virtual adapter plus a reachable LAN subnet.
        addresses = ['172.26.0.10', '192.168.50.123']
        self.assertEqual(bridge.phone_address_choices(addresses), ['192.168.50.123'])
        self.assertEqual(bridge.phone_address_choices(addresses, show_all=True),
                         ['172.26.0.10', '192.168.50.123'])
        self.assertEqual(bridge.phone_address_choices(['172.26.0.10']), ['172.26.0.10'])
        self.assertEqual(bridge.phone_address_choices([]), [])
        self.assertEqual(bridge.phone_address_choices(['203.0.113.1']), [])
        self.assertEqual(bridge.phone_address_choices(['203.0.113.1'], show_all=True),
                         ['203.0.113.1'])

    def test_arrows_are_default_mode(self):
        self.assertEqual(bridge.keys_for_action("up", ("ctrl", "win"), "arrows"), ("up",))
        self.assertEqual(bridge.keys_for_action("down", ("ctrl", "win"), "arrows"), ("down",))

    def test_double_direction_always_pages_when_enabled(self):
        for mode in ("arrows", "pages"):
            self.assertEqual(bridge.keys_for_action("up_double", ("ctrl", "win"), mode), ("pageup",))
            self.assertEqual(bridge.keys_for_action("down_double", ("ctrl", "win"), mode), ("pagedown",))
        self.assertEqual(bridge.keys_for_action("up_double", ("ctrl", "win"), "ignore"), ())
        self.assertEqual(bridge.keys_for_action("down_double", ("ctrl", "win"), "ignore"), ())

    def test_other_modes_are_preserved(self):
        for cmd, expected in (("up", "pageup"), ("down", "pagedown")):
            self.assertEqual(bridge.keys_for_action(cmd, ("ctrl", "win"), "pages"), (expected,))
            self.assertEqual(bridge.keys_for_action(cmd, ("ctrl", "win"), "ignore"), ())

    def test_voice_and_enter_unchanged(self):
        for mode in ("arrows", "pages", "ignore"):
            self.assertEqual(bridge.keys_for_action("tap", ("ctrl", "win"), mode), ("ctrl", "win"))
            self.assertEqual(bridge.keys_for_action("double", ("ctrl", "win"), mode), ("enter",))

    def test_invalid_is_rejected(self):
        for cmd, mode in (("escape", "arrows"), ("up", "invalid"), ("up_double", "invalid")):
            with self.assertRaises(ValueError):
                bridge.keys_for_action(cmd, ("ctrl", "win"), mode)

    def test_scroll_distance_repeats_arrow_not_page_or_voice(self):
        with patch.object(bridge, 'press_combo') as send, patch.object(bridge.time, 'sleep') as pause:
            skipped, target = bridge.execute_action('up', ('ctrl','win'), 'arrows', 8, False)
            self.assertFalse(skipped)
            self.assertEqual(target, 'up x8')
            self.assertEqual(send.call_count, 8)
            self.assertEqual(pause.call_count, 7)
            self.assertTrue(all(c.args == (('up',),) for c in send.call_args_list))
            send.reset_mock()
            bridge.execute_action('down', ('ctrl','win'), 'arrows', 8, False)
            self.assertEqual(send.call_count, 8)
            send.reset_mock()
            bridge.execute_action('up_double', ('ctrl','win'), 'arrows', 8, False)
            send.assert_called_once_with(('pageup',))
            send.reset_mock()
            bridge.execute_action('tap', ('ctrl','win'), 'arrows', 8, False)
            send.assert_called_once_with(('ctrl', 'win'))
            send.reset_mock()
            bridge.execute_action('up', ('ctrl','win'), 'pages', 8, False)
            send.assert_called_once_with(('pageup',))
            send.reset_mock()
            bridge.execute_action('up', ('ctrl','win'), 'ignore', 8, False)
            send.assert_not_called()
            send.reset_mock()
            bridge.execute_action('up', ('ctrl','win'), 'arrows', 8, True)
            send.assert_not_called()

    def test_arrow_injection_sets_extended_flag(self):
        class FakeUser32:
            def __init__(self):
                self.calls = []
            def keybd_event(self, vk, scan, flags, extra):
                self.calls.append((vk, flags))
        fake = FakeUser32()
        with patch.object(bridge.sys, "platform", "win32"), patch.object(bridge.ctypes, "windll", create=True) as windll:
            windll.user32 = fake
            bridge.press_combo(("up",))
            bridge.press_combo(("down",))
            bridge.press_combo(("pageup",))
            bridge.press_combo(("pagedown",))
        self.assertEqual(fake.calls, [
            (0x26, 0x0001), (0x26, 0x0003),
            (0x28, 0x0001), (0x28, 0x0003),
            (0x21, 0x0001), (0x21, 0x0003),
            (0x22, 0x0001), (0x22, 0x0003)
        ])


class TestWebSocketDryRun(unittest.TestCase):
    def test_browser_javascript_syntax(self):
        if not shutil.which("node"):
            self.skipTest("Node.js not available for JavaScript syntax check")
        js = bridge.PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
        js = (js.replace("__TOKEN_JSON__", '"test-token"')
              .replace("__DOUBLE_MS__", "300")
              .replace("__WHEEL_BURST_MS__", "75"))
        result = subprocess.run(["node", "--check"], input=js,
                                text=True, encoding="utf-8", capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_browser_immediate_direction_classifier(self):
        if not shutil.which("node"):
            self.skipTest("Node.js not available for directional browser tests")
        script = pathlib.Path(__file__).with_name("test_directional_classifier.js")
        result = subprocess.run(["node", str(script)], text=True,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("18 browser classifier scenarios passed", result.stdout)

    def test_six_commands_produce_ack_and_doubles_page(self):
        with socket.socket() as finder:
            finder.bind(("127.0.0.1", 0))
            port = finder.getsockname()[1]
        proc = subprocess.Popen(
            [sys.executable, "-u", str(SOURCE), "--bind", "127.0.0.1",
             "--port", str(port), "--hotkey", "ctrl+win",
             "--swipes", "arrows", "--dry-run"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        transcript = []
        try:
            deadline = time.monotonic() + 8
            url = None
            while time.monotonic() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break
                transcript.append(line)
                if line.startswith("Open locally: "):
                    url = line.removeprefix("Open locally: ").strip()
                    break
            self.assertIsNotNone(url, "Server failed to start")
            token = url.split("token=", 1)[1]
            with urllib.request.urlopen(url, timeout=3) as response:
                page = response.read().decode("utf-8")
                self.assertEqual(response.headers.get("Connection"), "close")
                self.assertIn("上下操作不等待", page)
                self.assertIn("默认滚动 8 个方向键步幅", page)
                self.assertNotIn("__DIRECTION_MS__", page)
                self.assertNotIn("__SCROLL_STEPS__", page)
            # Unauthenticated HTTP callers must not receive the control page.
            with self.assertRaises(urllib.error.HTTPError) as no_token:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3)
            self.assertEqual(no_token.exception.code, 403)
            # Reproduce WinError 10054: a client resets its TCP socket while
            # HTTP's readline() is still waiting for a complete request.
            for _ in range(3):
                with socket.create_connection(("127.0.0.1", port), timeout=3) as resetter:
                    resetter.sendall(b"GET / HTTP/1.1")  # deliberately no CRLF
                    time.sleep(0.03)
                    linger = struct.pack("hh" if sys.platform == "win32" else "ii", 1, 0)
                    resetter.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
            time.sleep(0.1)
            # A reset must not prevent fresh WebSocket commands from working.
            with socket.create_connection(("127.0.0.1", port), timeout=3) as ws:
                request = (
                    f"GET /ws?token={token} HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{port}\r\n"
                    "Connection: Upgrade\r\nUpgrade: websocket\r\n"
                    "Sec-WebSocket-Version: 13\r\n"
                    "Sec-WebSocket-Key: " + base64.b64encode(os.urandom(16)).decode() + "\r\n"
                    f"Origin: http://127.0.0.1:{port}\r\n\r\n"
                )
                ws.sendall(request.encode("ascii"))
                response = b""
                while b"\r\n\r\n" not in response:
                    response += ws.recv(2048)
                self.assertIn(b"101 Switching Protocols", response)
                for i, cmd in enumerate(("tap", "double", "up", "down", "up_double", "down_double")):
                    ack = send_action(ws, i, cmd)
                    self.assertTrue(ack["ok"], cmd)
                    self.assertEqual(ack["cmd"], cmd)
                    self.assertFalse(ack.get("skipped", False), cmd)
                duplicate = send_action(ws, 0, "tap")
                self.assertTrue(duplicate["ok"])
                self.assertTrue(duplicate.get("duplicate"))
                rejected = send_action(ws, 99, "arbitrary_keyboard_key")
                self.assertFalse(rejected["ok"])
                self.assertEqual(rejected.get("error"), "Invalid action")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            captured = proc.stdout.read()
            proc.stdout.close()
        self.assertNotIn("Traceback (most recent call last)", captured)
        self.assertNotIn("ConnectionResetError", captured)


if __name__ == "__main__":
    unittest.main()
