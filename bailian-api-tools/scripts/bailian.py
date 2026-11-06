#!/usr/bin/env python3
"""Model Studio TTS CLI. See references/tts.md for official protocol sources.

Standard library only; no SDK source is vendored.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import platform
import re
import socket
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"
REGIONS = {"cn-beijing": "dashscope.aliyuncs.com", "ap-southeast-1": "dashscope-intl.aliyuncs.com"}
MODELS = {
    "qwen3-tts-flash": {"family": "qwen3", "voice": "Cherry", "regions": list(REGIONS)},
    **{f"qwen-audio-{version}-tts-{tier}": {
        "family": "audio", "voice": None, "regions": list(REGIONS)
    } for version in ("3.0", "3.1") for tier in ("flash", "plus")},
    **{name: {"family": "cosyvoice", "voice": None, "regions": ["cn-beijing"]}
       for name in ("cosyvoice-v3.5-plus", "cosyvoice-v3.5-flash", "cosyvoice-v3-plus", "cosyvoice-v3-flash", "cosyvoice-v2")},
}
LANGUAGES = ("Auto", "Chinese", "English", "German", "Italian", "Portuguese", "Spanish", "Japanese", "Korean", "French", "Russian")
LANGUAGE_HINTS = ("zh", "en", "fr", "de", "ja", "ko", "ru", "pt", "th", "id", "vi", "es", "it", "ms", "fil", "ar")
MAX_AUDIO = 128 * 1024 * 1024
MAX_JSON = 1024 * 1024


class ToolError(Exception):
    def __init__(self, code, message, exit_code=2, **details):
        super().__init__(message)
        self.code, self.exit_code, self.details = code, exit_code, details


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ToolError("INVALID_ARGUMENT", message)


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an authenticated synthesis request, including 307/308.
        if req.get_method() != "GET":
            raise ToolError("UNEXPECTED_REDIRECT", "Synthesis redirect refused.", 4)
        return super().redirect_request(req, fp, code, msg, headers, audio_url(newurl))


def audio_url(value):
    if not isinstance(value, str):
        raise ToolError("INVALID_AUDIO_URL", "Expected an audio URL.", 4)
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    # Official responses sometimes contain an HTTP OSS URL; use TLS for OSS.
    if parts.scheme == "http" and host.endswith(".aliyuncs.com"):
        parts = parts._replace(scheme="https")
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise ToolError("INVALID_AUDIO_URL", "Audio downloads require HTTPS without user credentials.", 4)
    return urlunsplit(parts)


def request_bytes(req, timeout, limit):
    try:
        with build_opener(SafeRedirect()).open(req, timeout=timeout) as response:
            if response.status != 200:
                raise ToolError("HTTP_ERROR", "Unexpected HTTP status.", 4, http_status=response.status)
            length = response.headers.get("Content-Length")
            expected = int(length) if length and length.isdigit() else None
            if expected is not None and expected > limit:
                raise ToolError("RESPONSE_TOO_LARGE", "Response exceeds size limit.", 4)
            content_type = response.headers.get_content_type()
            if req.get_method() == "GET" and (content_type.startswith("text/") or content_type == "application/json"):
                raise ToolError("INVALID_AUDIO", "Download returned text instead of audio.", 4)
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ToolError("RESPONSE_TOO_LARGE", "Response exceeds size limit.", 4)
            if expected is not None and len(data) != expected:
                raise ToolError("INCOMPLETE_RESPONSE", "HTTP body was truncated; do not resubmit synthesis automatically.", 4)
            return data
    except HTTPError as exc:
        details = {"http_status": exc.code}
        try:
            with exc:
                body = json.loads(exc.read(MAX_JSON))
            if isinstance(body, dict):
                # Do not echo remote messages: they can contain text or credentials.
                details.update(api_code=body.get("code"), request_id=body.get("request_id"))
        except (ValueError, OSError, http.client.HTTPException):
            pass
        raise ToolError("API_ERROR", "HTTP request rejected; check status, API code, region and permissions.", 4, **details) from None
    except (TimeoutError, socket.timeout):
        raise ToolError("TIMEOUT", "HTTP operation timed out; synthesis outcome may be unknown.", 5) from None
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ToolError("TIMEOUT", "HTTP operation timed out; synthesis outcome may be unknown.", 5) from None
        raise ToolError("NETWORK_ERROR", "HTTP connection failed; synthesis outcome may be unknown.", 4) from None
    except http.client.HTTPException:
        raise ToolError("NETWORK_ERROR", "Incomplete HTTP response; synthesis outcome may be unknown.", 4) from None


def target_path(value, overwrite):
    target = Path(value).expanduser().absolute()
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ToolError("INVALID_OUTPUT", "Output must be a regular file path.", 6)
    if target.exists() and not overwrite:
        raise ToolError("OUTPUT_EXISTS", "Output exists; use --overwrite only if replacement is intended.", 6)
    parent = target.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK):
        raise ToolError("INVALID_OUTPUT", "Output parent is not writable.", 6)
    return target


def save_audio(url, target, overwrite, timeout):
    data = request_bytes(Request(audio_url(url), headers={"User-Agent": f"bailian-api-tools/{VERSION}"}), timeout, MAX_AUDIO)
    suffix = target.suffix.lower()
    valid = bool(data)
    if suffix == ".wav":
        valid = len(data) > 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    elif suffix == ".mp3":
        valid = data.startswith(b"ID3") or (len(data) > 2 and data[0] == 255 and data[1] & 224 == 224)
    elif suffix == ".opus":
        valid = data.startswith(b"OggS")
    if not valid:
        raise ToolError("INVALID_AUDIO", "Downloaded response is empty or does not match the output format.", 4)
    target_path(target, overwrite)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".part", delete=False) as handle:
            temp = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temp, target)
        else:
            # Same-filesystem hard link publishes the complete file without replacing a racing writer.
            os.link(temp, target)
        return {"path": str(target.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def build_tts(args):
    spec = MODELS[args.model]
    if args.region not in spec["regions"]:
        raise ToolError("UNSUPPORTED_REGION", "This model is unavailable in the selected region.")
    workspace = args.workspace or None
    if workspace and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}", workspace):
        raise ToolError("INVALID_WORKSPACE", "Workspace must be a DNS label, not a URL.")
    if spec["family"] != "qwen3" and not workspace:
        raise ToolError("MISSING_WORKSPACE", "Set DASHSCOPE_WORKSPACE or --workspace for this model.", 3)
    if args.text_file:
        text = sys.stdin.read() if args.text_file == "-" else Path(args.text_file).read_text(encoding="utf-8-sig")
    else:
        text = args.text
    if not text or not text.strip():
        raise ToolError("EMPTY_TEXT", "Text must not be empty.")
    voice = args.voice if args.voice is not None else spec["voice"]
    if not voice or not voice.strip():
        raise ToolError("MISSING_VOICE", "Choose --voice from the official list for this model.")
    body = {"model": args.model, "input": {"text": text, "voice": voice}}
    controls = {"format": args.format, "sample_rate": args.sample_rate, "rate": args.rate,
                "pitch": args.pitch, "volume": args.volume, "instruction": args.instruction,
                "language_hints": [args.language_hint] if args.language_hint else None}
    if spec["family"] == "qwen3":
        if any(v is not None for k, v in controls.items() if k != "format") or args.format not in (None, "wav"):
            raise ToolError("UNSUPPORTED_OPTION", "Qwen3 HTTP outputs WAV; use Qwen-Audio-TTS/CosyVoice for audio controls.")
        body["input"]["language_type"] = args.language or "Auto"
        fmt = "wav"
        path = "/services/aigc/multimodal-generation/generation"
    else:
        if args.language is not None:
            raise ToolError("UNSUPPORTED_OPTION", "Use --language-hint for Qwen-Audio-TTS/CosyVoice.")
        fmt = args.format or "wav"
        controls["format"] = fmt
        for key, value, low, high in (("rate", args.rate, .5, 2), ("pitch", args.pitch, .5, 2), ("volume", args.volume, 0, 100)):
            if value is not None and (not math.isfinite(value) or not low <= value <= high):
                raise ToolError("INVALID_ARGUMENT", f"{key} must be between {low} and {high}.")
        if fmt == "opus" and args.sample_rate in (22050, 44100):
            raise ToolError("INVALID_ARGUMENT", "Opus does not support sample rate 22050 or 44100.")
        body["input"].update({k: v for k, v in controls.items() if v is not None})
        path = "/services/audio/tts/SpeechSynthesizer"
    target = target_path(args.output or f"output/tts-{uuid.uuid4().hex[:12]}.{fmt}", args.overwrite)
    if target.suffix.lower() != f".{fmt}":
        raise ToolError("FORMAT_MISMATCH", f"Output file extension must be .{fmt}.")
    host = f"{workspace}.{args.region}.maas.aliyuncs.com" if workspace else REGIONS[args.region]
    summary = {"model": args.model, "voice": voice, "region": args.region,
               "text_characters": len(text), "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
               "output_path": str(target), "format": fmt}
    return f"https://{host}/api/v1{path}", body, target, summary


def execute(args, data):
    if args.command == "models":
        data["models"] = [{"id": name, **spec} for name, spec in MODELS.items()]
        data["catalog_date"] = "2026-10-28"
        data["live_query"] = False
        return "ok"
    if args.command == "doctor":
        region = os.environ.get("DASHSCOPE_REGION", "cn-beijing")
        if region not in REGIONS:
            raise ToolError("INVALID_REGION", "DASHSCOPE_REGION must be cn-beijing or ap-southeast-1.", 3)
        data.update(api_key_present=bool(os.environ.get("DASHSCOPE_API_KEY", "").strip()),
                    region=region,
                    workspace_present=bool(os.environ.get("DASHSCOPE_WORKSPACE", "").strip()),
                    network_checked=False, credential_validated=False)
        return "ok"
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 600:
        raise ToolError("INVALID_ARGUMENT", "--timeout must be greater than 0 and at most 600 seconds.")
    if args.command == "download":
        target = target_path(args.output, args.overwrite)
        if target.suffix.lower() not in (".wav", ".mp3", ".pcm", ".opus"):
            raise ToolError("INVALID_OUTPUT", "Choose .wav, .mp3, .pcm or .opus output.")
        data["file"] = save_audio(args.url, target, args.overwrite, args.timeout)
        return "ok"
    endpoint, body, target, summary = build_tts(args)
    data.update(summary)
    if args.dry_run:
        data["endpoint"] = endpoint
        data["input_options"] = {k: v for k, v in body["input"].items() if k != "text"}
        return "dry_run"
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not key:
        raise ToolError("MISSING_API_KEY", "Set DASHSCOPE_API_KEY through the environment.", 3)
    if "\r" in key or "\n" in key:
        raise ToolError("INVALID_API_KEY", "API key must not contain line breaks.", 3)
    req = Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                           "User-Agent": f"bailian-api-tools/{VERSION}"}, method="POST")
    raw = request_bytes(req, args.timeout, MAX_JSON)
    try:
        response = json.loads(raw)
        if not isinstance(response, dict):
            raise ValueError
        if response.get("code"):
            raise ToolError("API_ERROR", "Service returned an error; synthesis was not confirmed.", 4,
                            api_code=response.get("code"), request_id=response.get("request_id"))
        audio = response["output"]["audio"]
        url = audio["url"]
        if not isinstance(url, str) or not url:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ToolError("INVALID_RESPONSE", "Service did not return a valid audio URL; synthesis outcome may be unknown.", 4) from None
    data.update(request_id=response.get("request_id"), usage=response.get("usage"),
                audio_url=url, audio_id=audio.get("id"), expires_at=audio.get("expires_at"))
    try:
        data["file"] = save_audio(url, target, args.overwrite, args.timeout)
    except (ToolError, OSError) as exc:
        raise ToolError("DOWNLOAD_FAILED", "Synthesis completed; use download with audio_url instead of resubmitting TTS.",
                        6 if isinstance(exc, OSError) else exc.exit_code,
                        synthesis_completed=True, audio_url=url, request_id=response.get("request_id"),
                        cause=exc.code if isinstance(exc, ToolError) else "FILE_ERROR") from None
    return "ok"


def parser():
    root = Parser(description="Bailian HTTP TTS. Commands emit JSON; no automatic API retries.")
    root.add_argument("--version", action="version", version=f"bailian-api-tools {VERSION}")
    commands = root.add_subparsers(dest="command", required=True, parser_class=Parser)
    commands.add_parser("doctor", help="Check local configuration without network calls.")
    commands.add_parser("models", help="List supported models from the bundled catalog (offline).")
    tts = commands.add_parser("tts", help="Synthesize text and save audio.")
    source = tts.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--text-file", help="UTF-8 text file, or - for stdin.")
    tts.add_argument("--model", choices=MODELS, default="qwen3-tts-flash")
    tts.add_argument("--voice")
    tts.add_argument("--region", choices=REGIONS, default=os.environ.get("DASHSCOPE_REGION", "cn-beijing"))
    tts.add_argument("--workspace", default=os.environ.get("DASHSCOPE_WORKSPACE"))
    tts.add_argument("--language", choices=LANGUAGES, help="Qwen3 only; default Auto.")
    tts.add_argument("--language-hint", choices=LANGUAGE_HINTS, help="Qwen-Audio/CosyVoice only.")
    tts.add_argument("--format", choices=("wav", "mp3", "pcm", "opus"))
    tts.add_argument("--sample-rate", type=int, choices=(8000, 12000, 16000, 22050, 24000, 44100, 48000))
    tts.add_argument("--rate", type=float)
    tts.add_argument("--pitch", type=float)
    tts.add_argument("--volume", type=int)
    tts.add_argument("--instruction")
    tts.add_argument("--dry-run", action="store_true")
    tts.add_argument("--output")
    download = commands.add_parser("download", help="Download an existing audio URL without another synthesis call.")
    download.add_argument("--url", required=True)
    download.add_argument("--output", required=True)
    for command in (tts, download):
        command.add_argument("--timeout", type=float, default=60, help="Per HTTP operation timeout in seconds; default 60.")
        command.add_argument("--overwrite", action="store_true")
    return root


def redact(value):
    # Also redact server-supplied fields, file paths and echoed invalid arguments.
    serialized = json.dumps(value, ensure_ascii=False)
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if key:
        serialized = serialized.replace(json.dumps(key, ensure_ascii=False)[1:-1], "[REDACTED]")
    return serialized


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    started = time.monotonic()
    result = {"schema_version": SCHEMA_VERSION, "tool_version": VERSION,
              "run_id": str(uuid.uuid4()), "started_at": datetime.now(timezone.utc).isoformat(),
              "runtime": {"os": platform.system(), "python": platform.python_version()}, "data": {}}
    exit_code = 0
    try:
        args = parser().parse_args(argv)
        result["command"] = args.command
        result["status"] = execute(args, result["data"])
    except ToolError as exc:
        result.update(status="error", error={"code": exc.code, "message": str(exc), "details": exc.details})
        exit_code = exc.exit_code
    except (OSError, UnicodeError, ValueError) as exc:
        result.update(status="error", error={"code": "FILE_OR_INPUT_ERROR", "message": "Local file or input operation failed.", "details": {"type": type(exc).__name__}})
        exit_code = 6
    except KeyboardInterrupt:
        result.update(status="error", error={"code": "INTERRUPTED", "message": "Interrupted; a submitted synthesis may still complete remotely.", "details": {}})
        exit_code = 130
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    if exit_code:
        print(redact({"code": result["error"]["code"], "message": result["error"]["message"]}), file=sys.stderr)
    print(redact(result))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
