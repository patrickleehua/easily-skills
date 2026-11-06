#!/usr/bin/env python3
"""Volcengine Seed TTS 2.0 CLI. Python standard library only."""

from __future__ import annotations

import argparse
import base64
import binascii
import http.client
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import wave

ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
MODEL = "doubao-seed-tts-2-0"
RESOURCE_ID = "seed-tts-2.0"
DEFAULT_SPEAKER = "zh_female_vv_uranus_bigtts"
SAMPLE_RATES = (8000, 16000, 22050, 24000, 32000, 44100, 48000)


class TTSError(Exception):
    """User-visible configuration or service failure."""


def rate(value: str) -> int:
    number = int(value)
    if not -50 <= number <= 100:
        raise argparse.ArgumentTypeError("must be between -50 and 100")
    return number


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("models", help="list supported models offline")
    sub.add_parser("voices", help="show verified example voice offline, not account entitlements")
    tts = sub.add_parser("tts", help="synthesize audio using the V3 HTTP JSON stream")
    source = tts.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--text-file", type=Path)
    tts.add_argument("--model", choices=[MODEL], default=MODEL)
    tts.add_argument("--speaker", default=os.environ.get("VOLCENGINE_TTS_SPEAKER") or DEFAULT_SPEAKER)
    tts.add_argument("--format", choices=["mp3", "ogg_opus", "pcm", "wav"], default="mp3")
    tts.add_argument("--sample-rate", type=int, choices=SAMPLE_RATES, default=24000)
    tts.add_argument("--speech-rate", type=rate, default=0)
    tts.add_argument("--loudness-rate", type=rate, default=0)
    tts.add_argument("--instruction")
    tts.add_argument("--subtitle", action="store_true")
    tts.add_argument("--output", type=Path)
    tts.add_argument("--timeout", type=positive_seconds, default=120)
    tts.add_argument("--dry-run", action="store_true", help="print request body without credentials or network")
    return root


def build_payload(args: argparse.Namespace) -> dict:
    text = args.text_file.read_text(encoding="utf-8-sig") if args.text_file else args.text
    if not text or not text.strip():
        raise TTSError("Input text must not be empty.")
    if not args.speaker.strip():
        raise TTSError("Speaker must not be empty.")
    audio = {
        "format": "pcm" if args.format == "wav" else args.format,
        "sample_rate": args.sample_rate,
        "speech_rate": args.speech_rate,
        "loudness_rate": args.loudness_rate,
    }
    if args.subtitle:
        audio["enable_subtitle"] = True
    params = {"text": text, "speaker": args.speaker, "audio_params": audio}
    if args.instruction:
        params["additions"] = json.dumps({"context_texts": [args.instruction]}, ensure_ascii=False)
    return {"user": {"uid": "volcengine-api-tools"}, "req_params": params}


def consume_stream(response, audio_file) -> dict:
    """Decode documented JSON-line frames and require an explicit completion frame."""
    info = {"audio_bytes": 0, "usage": None, "sentences": []}
    complete = False
    for line in response:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise TTSError("Invalid JSON in TTS response.") from exc
        if not isinstance(event, dict):
            raise TTSError("TTS response frame must be a JSON object.")
        code = event.get("code")
        if code not in (0, 20000000):
            raise TTSError(f"TTS code={code}: {event.get('message', 'Unknown service error')}")
        data = event.get("data")
        if data:
            try:
                chunk = base64.b64decode(data, validate=True)
            except (ValueError, TypeError, binascii.Error) as exc:
                raise TTSError("Invalid base64 audio in TTS response.") from exc
            audio_file.write(chunk)
            info["audio_bytes"] += len(chunk)
        if event.get("sentence") is not None:
            info["sentences"].append(event["sentence"])
        if code == 20000000:
            info["usage"] = event.get("usage")
            complete = True
            break
    if not complete:
        raise TTSError("TTS stream ended before completion code 20000000; audio was not saved.")
    if not info["audio_bytes"]:
        raise TTSError("TTS completed without audio; audio was not saved.")
    return info


def synthesize(args: argparse.Namespace, payload: dict) -> dict:
    api_key = os.environ.get("VOLCENGINE_SPEECH_API_KEY", "").strip()
    if not api_key:
        raise TTSError("Set VOLCENGINE_SPEECH_API_KEY to a new-console Doubao Speech API Key.")
    extension = "ogg" if args.format == "ogg_opus" else args.format
    output = (args.output or Path("output") / f"tts_{uuid.uuid4().hex}.{extension}").resolve()
    if output.suffix.lower() != f".{extension}":
        raise TTSError(f"Output extension must be .{extension} for --format {args.format}.")
    metadata = output.with_suffix(output.suffix + ".json")
    if output.exists() or metadata.exists():
        raise TTSError(f"Output or metadata already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    request_id = str(uuid.uuid4())
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": RESOURCE_ID,
            "X-Api-Request-Id": request_id,
            "X-Control-Require-Usage-Tokens-Return": "*",
        },
        method="POST",
    )
    # Disable redirects so credentials cannot be forwarded to a different host.
    opener = urllib.request.build_opener(NoRedirect())
    temp_path = None
    logid = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".part", delete=False) as target:
            temp_path = Path(target.name)
            try:
                with opener.open(request, timeout=args.timeout) as response:
                    logid = response.headers.get("X-Tt-Logid")
                    if args.format == "wav":
                        with wave.open(target, "wb") as wav:
                            wav.setnchannels(1)
                            wav.setsampwidth(2)
                            wav.setframerate(args.sample_rate)
                            info = consume_stream(response, WaveSink(wav))
                    else:
                        info = consume_stream(response, target)
            except urllib.error.HTTPError as exc:
                logid = exc.headers.get("X-Tt-Logid") if exc.headers else None
                detail = exc.read(4096).decode("utf-8", errors="replace")
                raise TTSError(f"HTTP {exc.code}: {detail}") from exc
        if args.format in ("pcm", "wav") and info["audio_bytes"] % 2:
            raise TTSError("PCM data has an incomplete 16-bit sample; audio was not saved.")
        result = {
            "status": "complete", "model": MODEL, "resource_id": RESOURCE_ID,
            "speaker": args.speaker, "format": args.format, "sample_rate": args.sample_rate,
            "speech_rate": args.speech_rate, "loudness_rate": args.loudness_rate,
            "text_characters": len(payload["req_params"]["text"]),
            "request_id": request_id, "logid": logid,
            "audio_path": str(output), "metadata_path": str(metadata),
            **info,
        }
        result["file_bytes"] = temp_path.stat().st_size
        if args.format in ("pcm", "wav"):
            result["duration_seconds"] = info["audio_bytes"] / (2 * args.sample_rate)
        # Exclusive creation protects an output another invocation created while we waited.
        with output.open("xb") as destination, temp_path.open("rb") as source:
            try:
                shutil.copyfileobj(source, destination)
            except BaseException:
                destination.close()
                output.unlink(missing_ok=True)
                raise
        with metadata.open("x", encoding="utf-8") as destination:
            json.dump(result, destination, ensure_ascii=False, indent=2)
            destination.write("\n")
        return result
    except (TTSError, OSError, ValueError, http.client.HTTPException) as exc:
        raise TTSError(f"{exc} (request_id={request_id}, logid={logid or 'unavailable'})") from exc
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


class WaveSink:
    def __init__(self, wav):
        self.wav = wav

    def write(self, data: bytes):
        self.wav.writeframesraw(data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "models":
            result = [{"model": MODEL, "resource_id": RESOURCE_ID, "transport": "HTTP Chunked V3"}]
        elif args.command == "voices":
            result = {"source": "https://www.volcengine.com/docs/6561/1257544", "scope": "offline examples, not account permissions or complete catalog", "voices": [{"name": "Vivi 2.0", "speaker": DEFAULT_SPEAKER, "resource_id": RESOURCE_ID}]}
        else:
            payload = build_payload(args)
            result = {"dry_run": True, "endpoint": ENDPOINT, "resource_id": RESOURCE_ID, "body": payload} if args.dry_run else synthesize(args, payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (TTSError, OSError, ValueError) as exc:
        message = str(exc)
        secret = os.environ.get("VOLCENGINE_SPEECH_API_KEY", "").strip()
        if secret:
            message = message.replace(secret, "[redacted]")
        print(json.dumps({"status": "error", "error": message}, ensure_ascii=False), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('{"status":"error","error":"Interrupted; request was not automatically retried."}', file=sys.stderr)
        return 130


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
