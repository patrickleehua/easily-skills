#!/usr/bin/env python3
"""Normalize visible CLI-agent session facts without exporting hidden prompts or reasoning."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.1"
AGENT_CALLS = {
    "spawn_agent", "followup_task", "send_message", "interrupt_agent",
    "agent", "task", "sendmessage", "subagent", "spawn_subagent",
}
# Full sop.mjs command set (ExpertAgent v1): unknown cmds are dropped, never guessed.
EXPERT_COMMANDS = {
    "init", "dispatch", "outcome", "review", "ask", "answer",
    "advance", "sign", "note", "evidence", "assume", "overturn",
    "retier", "extend", "wait", "size", "depends", "finish",
}
BLOCK_TAGS = (
    "skill", "manually_attached_skills", "recommended_plugins",
    "environment_context", "system", "developer",
)
# Cursor wraps IDE context around the user's text; only <user_query> is user-authored.
CURSOR_CONTEXT_TAGS = (
    "user_info", "git_status", "open_files", "open_and_recently_viewed_files",
    "recently_viewed_files", "linter_errors", "additional_data", "attached_files",
    "current_file", "cursor_rules", "user_rules", "project_layout",
    "terminal_state", "selection", "selected_code", "system_reminder",
)
CURSOR_TRANSCRIPT_DIR = "agent-transcripts"


def norm_path(value: str | Path | None) -> str | None:
    if not value:
        return None
    try:
        return os.path.normcase(os.path.realpath(os.path.expanduser(str(value))))
    except OSError:
        return os.path.normcase(os.path.abspath(os.path.expanduser(str(value))))


def same_workspace(candidate: str | None, workspace: str) -> bool:
    left, right = norm_path(candidate), norm_path(workspace)
    return bool(left and right and left == right)


def redact(text: str) -> str:
    for tag in BLOCK_TAGS:
        text = re.sub(
            rf"<{tag}\b[^>]*>.*?</{tag}>",
            f"[{tag} block omitted]",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    marker = re.search(r"(?im)^## My request:\s*$", text)
    if marker and "Context from my IDE setup" in text[: marker.start()]:
        text = text[marker.end() :]
    text = strip_cursor_context(text)
    patterns = (
        r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{12,}",
        r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+",
        r"(?i)([A-Z][A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)\s*=\s*)[^\s]+",
    )
    for pattern in patterns:
        text = re.sub(pattern, r"\1[REDACTED]", text)
    return text.strip()


def strip_cursor_context(text: str) -> str:
    """Keep only the user-authored part of a Cursor message; drop IDE-attached context."""
    queries = re.findall(r"<user_query\b[^>]*>(.*?)</user_query>", text, flags=re.IGNORECASE | re.DOTALL)
    if queries:
        return "\n\n".join(query.strip() for query in queries if query.strip())
    for tag in CURSOR_CONTEXT_TAGS:
        text = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return text


def slug_key(value: str | Path | None) -> str:
    """Case-insensitive path slug: collapse every non-alphanumeric run to one dash.

    Cursor names ``~/.cursor/projects/<slug>`` by replacing separators and other
    non-alphanumerics with ``-`` (``C:\\Dev\\opc`` -> ``c-Dev-opc``); Claude Code
    uses ``C--Dev-opc``. Collapsing runs makes both comparable with a workspace path.
    """
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ("text", "input_text", "output_text"):
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
                        break
        return "\n".join(parts)
    if isinstance(content, dict):
        return content_text(content.get("content") or content.get("text") or "")
    return ""


def json_lines(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_no, raw in enumerate(handle, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    yield line_no, value
    except OSError:
        return


def safe_arguments(raw: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(raw, dict):
        return raw, False
    if not isinstance(raw, str) or not raw:
        return {}, False
    if raw.startswith("gAAAA"):
        return {}, True
    try:
        value = json.loads(raw)
        return (value if isinstance(value, dict) else {}), False
    except json.JSONDecodeError:
        return {}, False


def source_ref(path: Path, line_no: int) -> str:
    return f"{path}:{line_no}"


def empty_session(provider: str, path: Path) -> dict[str, Any]:
    return {
        "id": hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16],
        "provider": provider,
        "source_path": str(path),
        "workspace": None,
        "started_at": None,
        "parent_session_id": None,
        "agent_path": None,
        "project_slug": None,
        "messages": [],
        "calls": [],
        "warnings": [],
        "mtime": path.stat().st_mtime if path.exists() else 0,
    }


def parse_codex(path: Path) -> dict[str, Any]:
    session = empty_session("codex", path)
    msg_seq = call_seq = 0
    meta_seen = False
    history_start: int | None = None
    for line_no, row in json_lines(path):
        kind, payload = row.get("type"), row.get("payload") or {}
        timestamp = row.get("timestamp") or payload.get("timestamp")
        if kind == "session_meta":
            if meta_seen:
                continue
            meta_seen = True
            session["id"] = payload.get("id") or payload.get("session_id") or session["id"]
            session["workspace"] = payload.get("cwd")
            session["started_at"] = timestamp
            if isinstance(payload.get("subagent_history_start_ordinal"), int):
                history_start = payload["subagent_history_start_ordinal"]
            source = payload.get("source") or payload.get("thread_source")
            if isinstance(source, dict):
                sub = source.get("subagent") or {}
                spawn = sub.get("thread_spawn") or sub
                session["parent_session_id"] = spawn.get("parent_thread_id")
                session["agent_path"] = spawn.get("agent_path")
            session["parent_session_id"] = payload.get("parent_thread_id") or session["parent_session_id"]
            session["agent_path"] = payload.get("agent_path") or session["agent_path"]
            continue
        if history_start is not None and isinstance(row.get("ordinal"), int) and row["ordinal"] < history_start:
            continue
        if kind == "response_item" and payload.get("type") == "message":
            role = payload.get("role")
            if role not in ("user", "assistant") or payload.get("author"):
                continue
            text = redact(content_text(payload.get("content")))
            if text:
                msg_seq += 1
                session["messages"].append({
                    "seq": msg_seq, "timestamp": timestamp, "role": role,
                    "phase": payload.get("phase"), "text": text,
                    "source_ref": source_ref(path, line_no),
                })
        elif kind == "response_item" and payload.get("type") in ("function_call", "custom_tool_call"):
            name = str(payload.get("name") or "").split(".")[-1]
            if name.lower() not in AGENT_CALLS:
                continue
            args, encrypted = safe_arguments(payload.get("arguments") or payload.get("input"))
            call_seq += 1
            session["calls"].append({
                "seq": call_seq, "timestamp": timestamp, "name": name,
                "target": args.get("target"), "task_name": args.get("task_name"),
                "call_id": payload.get("call_id"),
                "status": "unavailable_encrypted" if encrypted else "called",
                "source_ref": source_ref(path, line_no),
            })
    return session


def parse_claude_like(path: Path, provider: str) -> dict[str, Any]:
    """Parse Claude Code / Cursor agent transcripts (one JSON object per line).

    Claude Code rows carry ``sessionId``/``cwd``/``isSidechain``/``agentId``; ``parentUuid``
    is the intra-session message chain and must NOT be read as a parent session.
    Cursor rows carry only ``role`` and ``message``; identity comes from the path.
    """
    session = empty_session(provider, path)
    msg_seq = call_seq = 0
    session_ids: list[str] = []
    agent_ids: list[str] = []
    sidechain = False
    for line_no, row in json_lines(path):
        row_session = row.get("sessionId") or row.get("session_id")
        if row_session and str(row_session) not in session_ids:
            session_ids.append(str(row_session))
        session["workspace"] = row.get("cwd") or session["workspace"]
        if row.get("isSidechain"):
            sidechain = True
        if row.get("agentId") and str(row["agentId"]) not in agent_ids:
            agent_ids.append(str(row["agentId"]))
        timestamp = row.get("timestamp") or row.get("created_at")
        message = row.get("message") if isinstance(row.get("message"), dict) else row
        role = message.get("role") or row.get("role") or (row.get("type") if row.get("type") in ("user", "assistant") else None)
        content = message.get("content")
        if role in ("user", "assistant"):
            text = redact(content_text(content))
            if text:
                msg_seq += 1
                session["messages"].append({
                    "seq": msg_seq, "timestamp": timestamp, "role": role,
                    "phase": None, "text": text, "source_ref": source_ref(path, line_no),
                })
        blocks = content if isinstance(content, list) else []
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") not in ("tool_use", "function_call"):
                continue
            name = str(block.get("name") or "")
            if name.lower().split(".")[-1] not in AGENT_CALLS:
                continue
            args = block.get("input") if isinstance(block.get("input"), dict) else {}
            call_seq += 1
            session["calls"].append({
                "seq": call_seq, "timestamp": timestamp, "name": name,
                "target": args.get("target") or args.get("subagent_type") or args.get("agent_type"),
                "task_name": args.get("task_name") or args.get("description") or args.get("task"),
                "call_id": block.get("id"), "status": "called",
                "source_ref": source_ref(path, line_no),
            })
    if provider == "cursor":
        apply_cursor_identity(session, path)
    else:
        apply_claude_identity(session, path, session_ids, agent_ids, sidechain)
    return session


def apply_claude_identity(session: dict[str, Any], path: Path, session_ids: list[str],
                          agent_ids: list[str], sidechain: bool) -> None:
    """Root: ``<projects>/<slug>/<sessionId>.jsonl``. Subagent: ``<sessionId>/subagents/agent-<id>.jsonl``."""
    in_subagents_dir = path.parent.name == "subagents"
    session["project_slug"] = (path.parent.parent.parent.name if in_subagents_dir else path.parent.name) or None
    if sidechain or agent_ids or in_subagents_dir:
        agent_id = agent_ids[0] if agent_ids else re.sub(r"^agent-", "", path.stem)
        parent = path.parent.parent.name if in_subagents_dir else (session_ids[0] if session_ids else None)
        session["id"] = agent_id
        session["parent_session_id"] = parent
        session["agent_path"] = agent_id
        if len(agent_ids) > 1:
            session["warnings"].append(f"Multiple agentId values in one transcript: {agent_ids}")
    else:
        session["id"] = session_ids[0] if session_ids else path.stem
        session["parent_session_id"] = None
    if len(session_ids) > 1:
        session["warnings"].append(f"Multiple sessionId values in one transcript: {session_ids}")


def apply_cursor_identity(session: dict[str, Any], path: Path) -> None:
    """Derive ids from the Cursor layout, since transcript rows carry no metadata.

    ``<project>/agent-transcripts/<conv>.jsonl``           flat (CLI) root
    ``<project>/agent-transcripts/<conv>/<conv>.jsonl``    nested (IDE) root
    ``<project>/agent-transcripts/<conv>/**/<sub>.jsonl``  subagent of <conv>
    """
    parts = path.parts
    anchors = [i for i, part in enumerate(parts) if part == CURSOR_TRANSCRIPT_DIR]
    if not anchors:
        session["id"] = path.stem
        session["warnings"].append(f"Cursor transcript outside an {CURSOR_TRANSCRIPT_DIR} directory: {path}")
        return
    anchor = anchors[-1]
    session["project_slug"] = parts[anchor - 1] if anchor > 0 else None
    rel = parts[anchor + 1:]
    if len(rel) == 1 or (len(rel) == 2 and path.stem == rel[0]):
        session["id"] = path.stem if len(rel) == 1 else rel[0]
        session["parent_session_id"] = None
        return
    session["id"] = path.stem
    session["parent_session_id"] = rel[0]
    session["agent_path"] = "/".join(rel[1:-1] + (path.stem,))


def parse_generic_markdown(path: Path) -> dict[str, Any]:
    session = empty_session("generic", path)
    text = path.read_text(encoding="utf-8", errors="replace")
    role_re = re.compile(r"(?im)^(?:#{1,6}\s*)?(user|assistant|asst)\s*:\s*|^(?:#{1,6}\s+)(user|assistant|asst)\s*$")
    matches = list(role_re.finditer(text))
    for index, match in enumerate(matches):
        role = (match.group(1) or match.group(2) or "").lower()
        role = "assistant" if role == "asst" else role
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = redact(text[match.end():end])
        if value:
            session["messages"].append({
                "seq": len(session["messages"]) + 1, "timestamp": None,
                "role": role, "phase": None, "text": value,
                "source_ref": f"{path}:char-{match.start()}",
            })
    if not session["messages"]:
        session["warnings"].append("No explicit user/assistant Markdown role markers found")
    return session


def parse_generic(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in (".md", ".txt"):
        return [parse_generic_markdown(path)]
    rows = list(json_lines(path))
    if not rows and path.suffix.lower() == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            values = value if isinstance(value, list) else [value]
            rows = [(index + 1, row) for index, row in enumerate(values) if isinstance(row, dict)]
        except (OSError, json.JSONDecodeError):
            rows = []
    session = empty_session("generic", path)
    for line_no, row in rows:
        message = row.get("message") if isinstance(row.get("message"), dict) else row
        role = message.get("role")
        text = redact(content_text(message.get("content") or message.get("text")))
        if role in ("user", "assistant") and text:
            session["messages"].append({
                "seq": len(session["messages"]) + 1,
                "timestamp": row.get("timestamp") or row.get("created_at"),
                "role": role, "phase": None, "text": text,
                "source_ref": source_ref(path, line_no),
            })
        calls = message.get("tool_calls") or row.get("tool_calls") or []
        for call in calls if isinstance(calls, list) else []:
            if not isinstance(call, dict):
                continue
            function = call.get("function") if isinstance(call.get("function"), dict) else call
            name = str(function.get("name") or "")
            args, encrypted = safe_arguments(function.get("arguments") or function.get("input"))
            session["calls"].append({
                "seq": len(session["calls"]) + 1, "timestamp": row.get("timestamp"),
                "name": name, "target": args.get("target"),
                "task_name": args.get("task_name"), "call_id": call.get("id"),
                "status": "unavailable_encrypted" if encrypted else "called",
                "source_ref": source_ref(path, line_no),
            })
    if not rows:
        session["warnings"].append("No parseable JSON/JSONL records found")
    return [session]


def candidate_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*.jsonl") if path.is_file()]


def generic_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    suffixes = {".jsonl", ".json", ".md", ".txt"}
    return [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes]


def codex_root() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() / "sessions" if configured else Path.home() / ".codex" / "sessions"


def claude_root() -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(configured).expanduser() / "projects" if configured else Path.home() / ".claude" / "projects"


def cursor_root() -> Path:
    configured = os.environ.get("CURSOR_CONFIG_DIR")
    return Path(configured).expanduser() / "projects" if configured else Path.home() / ".cursor" / "projects"


def project_dirs(root: Path, workspace: str) -> list[Path]:
    """Project folders under a provider root whose slug matches the workspace path."""
    if not root.exists():
        return []
    key = slug_key(workspace)
    return [path for path in root.iterdir() if path.is_dir() and slug_key(path.name) == key]


def claude_files(root: Path, workspace: str) -> list[Path]:
    """Prefer the project folder whose slug matches; fall back to a full scan (cwd still decides)."""
    matched = project_dirs(root, workspace)
    if matched:
        return [path for folder in matched for path in candidate_files(folder)]
    return candidate_files(root)


def cursor_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        path for path in root.glob(f"*/{CURSOR_TRANSCRIPT_DIR}/**/*.jsonl")
        if path.is_file()
    ]


def is_root(session: dict[str, Any]) -> bool:
    return not session.get("parent_session_id")


def choose_family(sessions: list[dict[str, Any]], workspace: str, session_id: str | None,
                  provider: str = "") -> tuple[list[dict[str, Any]], list[str]]:
    """Pick the target root session and its descendants; explain a zero hit instead of hiding it."""
    diagnostics: list[str] = []
    label = f"{provider} " if provider else ""
    matched = [s for s in sessions if same_workspace(s.get("workspace"), workspace)]
    if sessions and not matched:
        others = sorted({str(s.get("workspace")) for s in sessions if s.get("workspace")})
        hint = f"; other workspaces seen (first 3 of {len(others)}): {others[:3]}" if others else ""
        diagnostics.append(
            f"{len(sessions)} {label}transcript(s) parsed but none matched workspace {workspace}{hint}"
        )
        return [], diagnostics
    if session_id:
        hits = [s for s in matched if session_id in str(s.get("id")) or session_id in s["source_path"]]
        by_id = {str(s["id"]): s for s in matched}
        roots = []
        for hit in hits:
            root = hit
            seen: set[str] = set()
            while not is_root(root) and str(root.get("parent_session_id")) in by_id and str(root["id"]) not in seen:
                seen.add(str(root["id"]))
                root = by_id[str(root["parent_session_id"])]
            if root not in roots:
                roots.append(root)
        if not roots:
            elsewhere = [s for s in sessions if s not in matched and (session_id in str(s.get("id")) or session_id in s["source_path"])]
            where = f"; found outside workspace in {[s.get('workspace') for s in elsewhere][:3]}" if elsewhere else ""
            diagnostics.append(
                f"session id '{session_id}' not found among {len(matched)} {label}session(s) matched to workspace{where}"
            )
    else:
        roots = [s for s in matched if is_root(s)]
        if matched and not roots:
            diagnostics.append(
                f"{len(matched)} {label}transcript(s) matched workspace but all were classified as child "
                "transcripts; pass --session-id to pick one explicitly"
            )
        populated = [s for s in roots if s["messages"] or s["calls"]]
        if roots and not populated:
            diagnostics.append(f"{len(roots)} {label}root session(s) matched workspace but all are empty")
        roots = sorted(populated or roots, key=lambda value: value.get("mtime", 0), reverse=True)[:1]
    if not roots:
        return [], diagnostics
    selected_ids = {str(s["id"]) for s in roots}
    changed = True
    while changed:
        changed = False
        for session in matched:
            if str(session.get("parent_session_id")) in selected_ids and str(session["id"]) not in selected_ids:
                selected_ids.add(str(session["id"]))
                changed = True
    return [s for s in matched if str(s["id"]) in selected_ids], diagnostics


def discover(provider: str, workspace: str, session_id: str | None) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if provider == "codex":
        root = codex_root()
        files, parser = candidate_files(root), parse_codex
    elif provider == "claude":
        root = claude_root()
        files, parser = claude_files(root, workspace), lambda path: parse_claude_like(path, "claude")
    elif provider == "cursor":
        root = cursor_root()
        files, parser = cursor_files(root), lambda path: parse_claude_like(path, "cursor")
    else:
        return [], [f"Unsupported discovery provider: {provider}"]
    if not root.exists():
        return [], [f"{provider} session root not found: {root}"]
    parsed = [parser(path) for path in files]
    if provider == "cursor":
        key = slug_key(workspace)
        for session in parsed:
            if slug_key(session.get("project_slug")) == key:
                session["workspace"] = workspace
        matched_slugs = sorted({s["project_slug"] for s in parsed if s.get("workspace")})
        if matched_slugs:
            warnings.append(
                f"cursor workspace matched by project directory slug {matched_slugs} "
                "(agent transcripts carry no cwd, timestamps or tool results)"
            )
        else:
            warnings.append("Cursor coverage includes agent transcripts only; IDE sidebar private storage is not parsed")
    selected, diagnostics = choose_family(parsed, workspace, session_id, provider)
    warnings.extend(diagnostics)
    if not selected:
        warnings.append(f"No {provider} sessions matched workspace {workspace}")
    return selected, warnings


def expert_events(workspace: Path, task_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Orchestration events from ``.expertagent/tasks/*/events.jsonl``.

    Events are workspace-wide, not per session; ``task_ids`` narrows them to the
    task(s) the audited session actually ran so parallel windows do not leak in.
    """
    result: list[dict[str, Any]] = []
    root = workspace / ".expertagent" / "tasks"
    if not root.exists():
        return result
    wanted = {value for value in task_ids if value}
    allowed = (
        "at", "cmd", "id", "expert", "name", "depth", "object", "via", "result", "role", "verdict",
        "from", "to", "stage", "kind", "path", "gate", "by",
        # assume / overturn
        "q", "decision", "basis", "confidence", "reversible", "answer", "voided",
        # retier / extend / wait / depends / finish / advance / sign
        "stageFrom", "stageTo", "rounds", "reason", "timeout", "elapsed",
        "who", "what", "due", "status", "ok", "reasons", "assumptions", "comment", "ref", "seen",
    )
    for path in root.glob("*/events.jsonl"):
        task_id = path.parent.name
        if wanted and task_id not in wanted:
            continue
        for line_no, row in json_lines(path):
            if row.get("cmd") not in EXPERT_COMMANDS:
                continue
            event = {key: row[key] for key in allowed if key in row}
            event["task_id"] = task_id
            event["source_ref"] = source_ref(path, line_no)
            result.append(event)
    return result


def expert_task_summary(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per task so the auditor can see which tasks share the workspace."""
    tasks: dict[str, dict[str, Any]] = {}
    for event in events:
        entry = tasks.setdefault(event["task_id"], {"task_id": event["task_id"], "events": 0, "first_at": None, "last_at": None})
        entry["events"] += 1
        at = event.get("at")
        if at:
            entry["first_at"] = min(entry["first_at"], at) if entry["first_at"] else at
            entry["last_at"] = max(entry["last_at"], at) if entry["last_at"] else at
    return sorted(tasks.values(), key=lambda value: value["task_id"])


def strip_internal(bundle: dict[str, Any]) -> dict[str, Any]:
    for session in bundle["sessions"]:
        session.pop("mtime", None)
    return bundle


def markdown(bundle: dict[str, Any]) -> str:
    lines = ["# 会话日志事实", "", "## 范围与数据源", ""]
    lines.append(f"- 工作区：`{bundle['workspace']}`")
    lines.append(f"- Provider：{', '.join(bundle['providers']) or '无'}")
    lines.append(f"- 会话数：{len(bundle['sessions'])}")
    lines.append(f"- ExpertAgent 事件数：{len(bundle['expert_events'])}")
    if bundle.get("expert_tasks"):
        tasks = ", ".join(f"{t['task_id']}({t['events']})" for t in bundle["expert_tasks"])
        lines.append(f"- ExpertAgent 任务：{tasks}")
    for warning in bundle["warnings"]:
        lines.append(f"- 限制：{warning}")
    lines.extend(["", "## Agent 调用关系", "", "```text"])
    if bundle["sessions"]:
        for session in bundle["sessions"]:
            parent = session.get("parent_session_id") or "root"
            label = session.get("agent_path") or session["id"]
            slug = f" project={session['project_slug']}" if session.get("project_slug") else ""
            lines.append(f"{parent} -> {label} [{session['provider']}{slug}]")
    else:
        lines.append("未发现匹配会话")
    lines.extend(["```", "", "## 可见消息", ""])
    for session in bundle["sessions"]:
        lines.extend([f"### {session.get('agent_path') or session['id']}", ""])
        for message in session["messages"]:
            heading = "用户调用" if message["role"] == "user" else "模型输出"
            lines.append(f"#### {heading} M{message['seq']}")
            lines.append("")
            lines.append(message["text"])
            lines.append("")
            lines.append(f"来源：`{message['source_ref']}`")
            lines.append("")
        if session["calls"]:
            lines.append("#### Agent 调用")
            lines.append("")
            for call in session["calls"]:
                detail = call.get("task_name") or call.get("target") or call.get("status")
                lines.append(f"- C{call['seq']} `{call['name']}` → {detail}（`{call['source_ref']}`）")
            lines.append("")
    lines.extend(["## ExpertAgent 事件", ""])
    if bundle["expert_events"]:
        lines.append("| 时间 | 任务 | 命令 | 事件/专家 | 结果 | 来源 |")
        lines.append("|---|---|---|---|---|---|")
        for event in bundle["expert_events"]:
            subject = event.get("name") or event.get("expert") or event.get("id") or "-"
            outcome = event.get("result") or event.get("verdict") or event.get("to") or "-"
            lines.append(f"| {event.get('at', '-')} | {event['task_id']} | {event.get('cmd', '-')} | {subject} | {outcome} | `{event['source_ref']}` |")
    else:
        lines.append("未发现 ExpertAgent 事件。")
    lines.extend(["", "## 事实缺口", ""])
    warnings = bundle["warnings"] + [w for s in bundle["sessions"] for w in s["warnings"]]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- 无解析器已知缺口。")
    lines.extend(["", "## 审查结论", "", "本文件只含事实。若需流程评价，请基于指定 Skill/SOP 另写结论并引用上述来源。", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("auto", "codex", "claude", "cursor", "generic"), default="auto")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--input", action="append", default=[], help="Explicit transcript file or directory")
    parser.add_argument("--session-id")
    parser.add_argument("--task-id", action="append", default=[], help="Only keep ExpertAgent events of these task ids")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    workspace = str(Path(args.workspace).expanduser().resolve())
    sessions: list[dict[str, Any]] = []
    warnings: list[str] = []
    providers = ("codex", "claude", "cursor") if args.provider == "auto" else (args.provider,)
    for provider in providers:
        if provider == "generic":
            continue
        found, provider_warnings = discover(provider, workspace, args.session_id)
        sessions.extend(found)
        warnings.extend(provider_warnings)

    for raw in args.input:
        path = Path(raw).expanduser().resolve()
        files = generic_files(path) if path.is_dir() else [path]
        for item in files:
            if not item.exists():
                warnings.append(f"Explicit input not found: {item}")
                continue
            sessions.extend(parse_generic(item))
    if args.provider == "generic" and not args.input:
        warnings.append("generic provider requires at least one --input")

    invocation = " ".join(shlex.quote(value) for value in sys.argv)
    events = expert_events(Path(workspace), args.task_id)
    bundle = strip_internal({
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "workspace": workspace,
        "providers": sorted({s["provider"] for s in sessions}),
        "sessions": sessions,
        "expert_events": events,
        "expert_tasks": expert_task_summary(events),
        "warnings": warnings,
        "invocation": invocation,
    })
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "markdown":
        output.write_text(markdown(bundle), encoding="utf-8")
    else:
        output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output), "sessions": len(sessions),
        "messages": sum(len(s["messages"]) for s in sessions),
        "calls": sum(len(s["calls"]) for s in sessions),
        "expert_events": len(bundle["expert_events"]), "warnings": warnings,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
