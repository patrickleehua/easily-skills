"""Offline CLI contracts and local HTTP fixtures; no cloud quota used."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import ProxyHandler, Request, build_opener

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bailian.py"
spec = importlib.util.spec_from_file_location("bailian", SCRIPT)
bailian = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bailian)
RESULT_SCHEMA = json.loads((ROOT / "references" / "result.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(RESULT_SCHEMA)
RESULT_VALIDATOR = Draft202012Validator(RESULT_SCHEMA, format_checker=FormatChecker())


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\0\0" * 240)
    return output.getvalue()


WAV = wav_bytes()
KEY = "sk-test-never-a-real-credential"
URL = "https://fixture.invalid/audio.wav?signature=fixture"


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body, content_type="application/json", extra_length=0):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body) + extra_length))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.events.append(("POST", self.path, dict(self.headers), request))
        mode = self.server.mode
        if mode == "timeout":
            time.sleep(.15)
        if mode in ("401", "429", "500"):
            self.reply(int(mode), json.dumps({"code": "FixtureError", "request_id": "fixture-error", "message": KEY}).encode())
            return
        if mode == "business-error":
            body = {"code": "InvalidParameter", "message": KEY, "request_id": "fixture-error"}
        elif mode == "bad-json":
            self.reply(200, b"not JSON")
            return
        elif mode == "missing-audio":
            body = {"request_id": "fixture-missing", "output": {}}
        else:
            body = {"request_id": "fixture-success", "output": {"audio": {"url": URL, "id": "audio_fixture", "expires_at": 1999999999}}, "usage": {"characters": 3}}
        self.reply(200, json.dumps(body).encode())

    def do_GET(self):
        self.server.events.append(("GET", self.path, dict(self.headers), None))
        if self.server.mode == "download-failed":
            self.reply(503, b"{}")
        elif self.server.mode == "bad-audio":
            self.reply(200, b"<html>error</html>", "text/html")
        elif self.server.mode == "truncated":
            self.reply(200, WAV[:60], "audio/wav", extra_length=100)
        else:
            self.reply(200, WAV, "audio/wav")


class LocalRoute:
    """Tests alone rewrite HTTPS targets to a local HTTP fixture."""
    def __init__(self, server):
        self.server = server
        self.opener = build_opener(ProxyHandler({}), bailian.SafeRedirect())

    def open(self, req, timeout):
        from urllib.parse import urlsplit
        parts = urlsplit(req.full_url)
        path = parts.path + ("?" + parts.query if parts.query else "")
        local = f"http://127.0.0.1:{self.server.server_port}{path}"
        request = Request(local, data=req.data, headers=dict(req.header_items()), method=req.get_method())
        return self.opener.open(request, timeout=timeout)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="百炼 fixture ")
        self.cwd = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("DASHSCOPE_")}
        self.env["PYTHONUTF8"] = "1"

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, input=None, env=None):
        proc = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.cwd,
                              env=env or self.env, input=input, text=True, encoding="utf-8",
                              capture_output=True, timeout=10)
        if "--help" not in args and "--version" not in args:
            RESULT_VALIDATOR.validate(json.loads(proc.stdout))
        return proc

    def test_chinese_file_dry_run_is_offline_and_creates_nothing(self):
        source = self.cwd / "中文 空格.txt"
        source.write_bytes("你好。\r\n第二行。".encode("utf-8-sig"))
        output = self.cwd / "新目录" / "中文 音频.wav"
        proc = self.run_cli("tts", "--text-file", str(source), "--output", str(output), "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["data"]["text_characters"], 8)
        self.assertNotIn("第二行", proc.stdout)
        self.assertFalse(output.parent.exists())
        self.assertEqual(proc.stderr, "")

    def test_stdin_and_missing_key_have_distinct_results(self):
        proc = self.run_cli("tts", "--text-file", "-", "--dry-run", input="你好")
        self.assertEqual(json.loads(proc.stdout)["data"]["text_characters"], 2)
        proc = self.run_cli("tts", "--text", "你好")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "MISSING_API_KEY")

    def test_bad_arguments_are_one_json_result(self):
        for args in (("tts", "--text", ""), ("tts", "--text", "x", "--rate", "1.2", "--dry-run"),
                     ("tts", "--text", "x", "--timeout", "nan"), ("unknown",)):
            with self.subTest(args=args):
                proc = self.run_cli(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(json.loads(proc.stdout)["status"], "error")
                self.assertNotIn("Traceback", proc.stderr)

    def test_existing_file_is_protected_before_auth_or_network(self):
        output = self.cwd / "existing.wav"
        output.write_bytes(b"keep me")
        proc = self.run_cli("tts", "--text", "hello", "--output", str(output))
        self.assertEqual(proc.returncode, 6)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "OUTPUT_EXISTS")
        self.assertEqual(output.read_bytes(), b"keep me")

    def test_doctor_models_help_version_and_redaction(self):
        env = {**self.env, "DASHSCOPE_API_KEY": KEY}
        proc = self.run_cli("doctor", env=env)
        self.assertTrue(json.loads(proc.stdout)["data"]["api_key_present"])
        self.assertNotIn(KEY, proc.stdout + proc.stderr)
        proc = self.run_cli("models")
        self.assertFalse(json.loads(proc.stdout)["data"]["live_query"])
        self.assertEqual(self.run_cli("--version").returncode, 0)
        self.assertIn("--dry-run", self.run_cli("tts", "--help").stdout)
        proc = self.run_cli("tts", "--text", "x", "--model", KEY, env=env)
        self.assertNotIn(KEY, proc.stdout + proc.stderr)


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bailian-test-")
        self.output = Path(self.temp.name) / "配音 空格.wav"
        self.server.events = []
        self.server.mode = "ok"
        self.env = patch.dict(os.environ, {"DASHSCOPE_API_KEY": KEY, "DASHSCOPE_REGION": "cn-beijing", "DASHSCOPE_WORKSPACE": ""})
        self.env.start()
        self.route = patch.object(bailian, "build_opener", return_value=LocalRoute(self.server))
        self.route.start()

    def tearDown(self):
        self.route.stop()
        self.env.stop()
        self.temp.cleanup()

    def execute(self, *extra):
        args = bailian.parser().parse_args(["tts", "--text", "你好。", "--output", str(self.output), *extra])
        data = {}
        status = bailian.execute(args, data)
        return status, data

    def test_qwen3_roundtrip_and_download_auth_isolation(self):
        status, data = self.execute()
        self.assertEqual(status, "ok")
        self.assertEqual(self.output.read_bytes(), WAV)
        self.assertEqual(data["file"]["sha256"], hashlib.sha256(WAV).hexdigest())
        self.assertEqual(data["request_id"], "fixture-success")
        self.assertEqual(data["usage"]["characters"], 3)
        post, get = self.server.events
        self.assertEqual(post[1], "/api/v1/services/aigc/multimodal-generation/generation")
        self.assertEqual(post[2]["Authorization"], f"Bearer {KEY}")
        self.assertEqual(post[3]["input"], {"text": "你好。", "voice": "Cherry", "language_type": "Auto"})
        self.assertNotIn("Authorization", get[2])
        self.assertFalse(list(self.output.parent.glob("*.part")))

    def test_full_error_envelope_matches_schema_and_redacts_remote_message(self):
        self.server.mode = "401"
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = bailian.main(["tts", "--text", "你好。", "--output", str(self.output)])
        self.assertEqual(code, 4)
        result = json.loads(stdout.getvalue())
        RESULT_VALIDATOR.validate(result)
        self.assertEqual(result["error"]["details"]["http_status"], 401)
        self.assertNotIn(KEY, stdout.getvalue() + stderr.getvalue())

    def test_audio_and_cosyvoice_request_contracts(self):
        for model, voice in (("qwen-audio-3.0-tts-flash", "longanhuan_v3.6"), ("cosyvoice-v3-plus", "longanyang")):
            with self.subTest(model=model):
                self.server.events = []
                self.execute("--model", model, "--voice", voice, "--workspace", "ws-fixture", "--rate", "1.2", "--pitch", "0.9", "--volume", "60", "--language-hint", "zh", "--overwrite")
                post = self.server.events[0]
                self.assertEqual(post[1], "/api/v1/services/audio/tts/SpeechSynthesizer")
                self.assertEqual(post[3]["model"], model)
                self.assertEqual(post[3]["input"], {"text": "你好。", "voice": voice, "format": "wav", "rate": 1.2, "pitch": .9, "volume": 60, "language_hints": ["zh"]})

    def test_service_failures_do_not_retry_or_publish_audio(self):
        for mode in ("401", "429", "500", "business-error", "bad-json", "missing-audio"):
            with self.subTest(mode=mode):
                self.server.mode, self.server.events = mode, []
                with self.assertRaises(bailian.ToolError):
                    self.execute()
                self.assertEqual(len(self.server.events), 1)
                self.assertFalse(self.output.exists())

    def test_timeout_does_not_retry(self):
        self.server.mode = "timeout"
        with self.assertRaises(bailian.ToolError) as caught:
            self.execute("--timeout", "0.03")
        self.assertEqual(caught.exception.code, "TIMEOUT")
        self.assertEqual(len(self.server.events), 1)
        time.sleep(.17)

    def test_download_failure_can_recover_without_another_post(self):
        self.server.mode = "download-failed"
        with self.assertRaises(bailian.ToolError) as caught:
            self.execute()
        self.assertEqual(caught.exception.code, "DOWNLOAD_FAILED")
        self.assertTrue(caught.exception.details["synthesis_completed"])
        self.assertEqual(caught.exception.details["audio_url"], URL)
        self.assertFalse(self.output.exists())
        self.server.mode = "ok"
        args = bailian.parser().parse_args(["download", "--url", URL, "--output", str(self.output)])
        self.assertEqual(bailian.execute(args, {}), "ok")
        self.assertEqual([e[0] for e in self.server.events], ["POST", "GET", "GET"])
        self.assertEqual(self.output.read_bytes(), WAV)

    def test_corrupt_audio_and_interrupt_leave_no_output(self):
        self.server.mode = "bad-audio"
        with self.assertRaises(bailian.ToolError) as caught:
            self.execute()
        self.assertEqual(caught.exception.details["cause"], "INVALID_AUDIO")
        self.assertFalse(self.output.exists())
        self.server.mode = "ok"
        with patch.object(bailian.os, "link", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.execute()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.output.parent.glob("*.part")))

    def test_truncated_audio_is_not_published(self):
        self.server.mode = "truncated"
        with self.assertRaises(bailian.ToolError) as caught:
            self.execute()
        self.assertEqual(caught.exception.details["cause"], "INCOMPLETE_RESPONSE")
        self.assertFalse(self.output.exists())

    def test_racing_writer_is_not_overwritten(self):
        real_link = os.link

        def competing_link(source, target):
            target.write_bytes(b"racing writer")
            return real_link(source, target)

        with patch.object(bailian.os, "link", side_effect=competing_link):
            with self.assertRaises(bailian.ToolError) as caught:
                self.execute()
        self.assertTrue(caught.exception.details["synthesis_completed"])
        self.assertEqual(self.output.read_bytes(), b"racing writer")
        self.assertFalse(list(self.output.parent.glob("*.part")))

    def test_region_workspace_and_option_validation_is_offline(self):
        cases = [
            ["--model", "cosyvoice-v3-plus", "--region", "ap-southeast-1"],
            ["--model", "qwen-audio-3.0-tts-flash"],
            ["--model", "qwen-audio-3.0-tts-flash", "--workspace", "ws-fixture"],
            ["--workspace", "https://untrusted.example"],
            ["--model", "qwen-audio-3.0-tts-flash", "--workspace", "ws-fixture", "--voice", "fixture", "--rate", "nan"],
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(bailian.ToolError):
                self.execute(*args)
        self.assertFalse(self.server.events)

    def test_redirects_never_forward_post_or_downgrade_tls(self):
        handler = bailian.SafeRedirect()
        req = Request("https://api.invalid", data=b"{}", headers={"Authorization": "Bearer fixture"})
        with self.assertRaises(bailian.ToolError):
            handler.redirect_request(req, None, 302, "redirect", {}, "https://other.invalid")
        with self.assertRaises(bailian.ToolError):
            handler.redirect_request(Request(URL), None, 302, "redirect", {}, "http://other.invalid")
        self.assertEqual(bailian.audio_url("http://bucket.oss-cn-beijing.aliyuncs.com/a.wav?x=1"), "https://bucket.oss-cn-beijing.aliyuncs.com/a.wav?x=1")


if __name__ == "__main__":
    unittest.main()
