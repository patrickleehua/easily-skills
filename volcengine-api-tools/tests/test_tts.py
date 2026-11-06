"""Exercise the CLI against an actual local HTTP service using V3 doc fixtures."""

import base64
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run


class TTSContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.server.calls.append({
                    "path": self.path,
                    "headers": self.headers,
                    "body": json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                })
                self.send_response(self.server.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Tt-Logid", "fixture-log-id")
                self.end_headers()
                # No Content-Length: also exercise reading a stream until connection close.
                for frame in self.server.frames:
                    self.wfile.write(json.dumps(frame, ensure_ascii=False).encode("utf-8") + b"\n")
                    self.wfile.flush()

            def log_message(self, *_):
                pass

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "audio.mp3"
        self.server.calls = []
        self.server.status = 200
        self.server.frames = []
        self.endpoint = patch.object(run, "ENDPOINT", f"http://127.0.0.1:{self.server.server_port}/api/v3/tts/unidirectional")
        self.endpoint.start()
        self.addCleanup(self.endpoint.stop)
        self.env = patch.dict(os.environ, {"VOLCENGINE_SPEECH_API_KEY": "fixture-secret"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def invoke(self, *extra):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = run.main(["tts", "--text", "你好。", "--output", str(self.output), *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def frames(self, data=b"ID3fixture-audio"):
        return [
            {"code": 0, "data": base64.b64encode(data).decode()},
            {"code": 0, "data": None, "sentence": {"text": "你好。", "words": []}},
            {"code": 20000000, "data": None, "usage": {"text_words": 3}},
        ]

    def test_http_contract_and_decoded_audio(self):
        self.server.frames = self.frames()
        code, stdout, stderr = self.invoke("--instruction", "温柔一些", "--subtitle")
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(self.output.read_bytes(), b"ID3fixture-audio")
        result = json.loads(stdout)
        self.assertEqual(result["usage"], {"text_words": 3})
        self.assertEqual(result["logid"], "fixture-log-id")
        self.assertEqual(result["sentences"][0]["text"], "你好。")
        stored = Path(result["metadata_path"]).read_text(encoding="utf-8")
        self.assertNotIn("fixture-secret", stored + stdout + stderr)
        self.assertNotIn("ID3fixture-audio", stored)
        wire = self.server.calls[0]
        self.assertEqual(wire["headers"]["X-Api-Key"], "fixture-secret")
        self.assertEqual(wire["headers"]["X-Api-Resource-Id"], "seed-tts-2.0")
        self.assertEqual(wire["headers"]["X-Control-Require-Usage-Tokens-Return"], "*")
        params = wire["body"]["req_params"]
        self.assertEqual(params["speaker"], "zh_female_vv_uranus_bigtts")
        self.assertEqual(json.loads(params["additions"]), {"context_texts": ["温柔一些"]})
        self.assertTrue(params["audio_params"]["enable_subtitle"])
        self.assertNotIn("enable_timestamp", params["audio_params"])
        self.assertNotIn("app", wire["body"])

    def test_wav_wraps_pcm_with_one_valid_header(self):
        self.output = self.output.with_suffix(".wav")
        self.server.frames = self.frames(b"\x00\x00\x01\x00" * 240)
        code, stdout, stderr = self.invoke("--format", "wav")
        self.assertEqual((code, stderr), (0, ""))
        with wave.open(str(self.output), "rb") as wav:
            self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (1, 2, 24000))
            self.assertEqual(wav.getnframes(), 480)
        self.assertEqual(json.loads(stdout)["duration_seconds"], 0.02)
        self.assertEqual(self.server.calls[0]["body"]["req_params"]["audio_params"]["format"], "pcm")

    def test_bad_or_truncated_stream_leaves_no_audio(self):
        cases = [
            self.frames()[:1],
            [{"code": 45000000, "message": "speaker permission denied"}],
            [{"code": 20000000, "data": None}],
            [{"code": 0, "data": "invalid!!"}],
            ["not a response object"],
        ]
        for frames in cases:
            with self.subTest(frames=frames):
                self.server.frames = frames
                code, _, error = self.invoke()
                self.assertEqual(code, 1)
                self.assertIn("fixture-log-id", error)
                self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_http_error_redacts_credentials(self):
        self.server.status = 403
        self.server.frames = [{"message": "rejected fixture-secret"}]
        code, _, error = self.invoke()
        self.assertEqual(code, 1)
        self.assertIn("HTTP 403", error)
        self.assertIn("[redacted]", error)
        self.assertNotIn("fixture-secret", error)
        self.assertFalse(self.output.exists())

    def test_existing_audio_is_preserved_without_a_request(self):
        self.output.write_bytes(b"existing audio")
        code, _, error = self.invoke()
        self.assertEqual(code, 1)
        self.assertIn("already exists", error)
        self.assertEqual(self.output.read_bytes(), b"existing audio")
        self.assertEqual(self.server.calls, [])

    def test_dry_run_and_missing_credentials_never_call_service(self):
        with patch.dict(os.environ, {"VOLCENGINE_SPEECH_API_KEY": ""}):
            code, stdout, _ = self.invoke("--dry-run")
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(stdout)["dry_run"])
            code, _, error = self.invoke()
            self.assertEqual(code, 1)
            self.assertIn("VOLCENGINE_SPEECH_API_KEY", error)
        self.assertEqual(self.server.calls, [])


if __name__ == "__main__":
    unittest.main()
