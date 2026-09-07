import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("session_log_audit.py")
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("session_log_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(audit)


def write_jsonl(path: Path, rows) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def user(text, **extra):
    return {"role": "user", "message": {"content": [{"type": "text", "text": text}]}, **extra}


def assistant(text, *blocks, **extra):
    return {"role": "assistant", "message": {"content": [{"type": "text", "text": text}, *blocks]}, **extra}


class SessionLogAuditTests(unittest.TestCase):
    def test_redact_removes_attached_skill_and_secret(self):
        value = audit.redact("before <skill>private</skill> token=abc123456789 after")
        self.assertNotIn("private", value)
        self.assertNotIn("abc123456789", value)
        self.assertIn("[REDACTED]", value)

    def test_codex_subagent_uses_first_meta_and_skips_inherited_history(self):
        rows = [
            {
                "ordinal": 0,
                "type": "session_meta",
                "payload": {
                    "id": "child",
                    "cwd": "/repo",
                    "parent_thread_id": "parent",
                    "agent_path": "/root/worker",
                    "subagent_history_start_ordinal": 3,
                },
            },
            {"ordinal": 1, "type": "session_meta", "payload": {"id": "parent", "cwd": "/repo"}},
            {"ordinal": 2, "type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"text": "inherited"}]}},
            {"ordinal": 3, "type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"text": "worker result"}]}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session = audit.parse_codex(write_jsonl(Path(tmp) / "rollout.jsonl", rows))
        self.assertEqual("child", session["id"])
        self.assertEqual("parent", session["parent_session_id"])
        self.assertEqual("/root/worker", session["agent_path"])
        self.assertEqual(["worker result"], [item["text"] for item in session["messages"]])

    def test_generic_jsonl_keeps_visible_roles_only(self):
        rows = [
            {"role": "system", "content": "hidden"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sessions = audit.parse_generic(write_jsonl(Path(tmp) / "export.jsonl", rows))
        self.assertEqual(["user", "assistant"], [item["role"] for item in sessions[0]["messages"]])

    # ------------------------------------------------------------------ Claude Code

    def test_claude_root_ignores_parent_uuid_message_chain(self):
        rows = [
            {"type": "mode", "sessionId": "root-1"},
            {"sessionId": "root-1", "parentUuid": None, "isSidechain": False, "cwd": "/repo", "type": "user",
             "message": {"role": "user", "content": "first"}},
            {"sessionId": "root-1", "parentUuid": "uuid-of-first", "isSidechain": False, "cwd": "/repo", "type": "assistant",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "reply"}]}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session = audit.parse_claude_like(write_jsonl(Path(tmp) / "proj" / "root-1.jsonl", rows), "claude")
        self.assertEqual("root-1", session["id"])
        self.assertIsNone(session["parent_session_id"], "parentUuid is an intra-session pointer, not a parent session")
        self.assertEqual("proj", session["project_slug"])
        self.assertEqual(2, len(session["messages"]))

    def test_claude_subagent_links_to_parent_session_and_agent_tool_is_normalized(self):
        rows = [
            {
                "sessionId": "root-1",
                "parentUuid": "some-message-uuid",
                "cwd": "/repo",
                "isSidechain": True,
                "agentId": "planner",
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "done"},
                        {"type": "tool_use", "id": "tool-1", "name": "Agent", "input": {"subagent_type": "reviewer", "description": "review spec"}},
                    ],
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_jsonl(Path(tmp) / "proj" / "root-1" / "subagents" / "agent-planner.jsonl", rows)
            session = audit.parse_claude_like(path, "claude")
        self.assertEqual("planner", session["id"])
        self.assertEqual("root-1", session["parent_session_id"])
        self.assertEqual("planner", session["agent_path"])
        self.assertEqual("reviewer", session["calls"][0]["target"])
        self.assertEqual("review spec", session["calls"][0]["task_name"])

    def test_claude_family_selects_latest_root_with_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "projects"
            proj = projects / audit.slug_key(tmp).replace("-", "--")  # any slug; cwd decides
            base = {"cwd": tmp, "isSidechain": False}
            write_jsonl(proj / "old.jsonl", [{"sessionId": "old", "parentUuid": None, **base, "message": {"role": "user", "content": "old"}}])
            write_jsonl(proj / "new.jsonl", [
                {"sessionId": "new", "parentUuid": None, **base, "message": {"role": "user", "content": "new"}},
                {"sessionId": "new", "parentUuid": "x", **base, "message": {"role": "assistant", "content": "ok"}},
            ])
            write_jsonl(proj / "empty.jsonl", [])
            write_jsonl(proj / "new" / "subagents" / "agent-w1.jsonl", [
                {"sessionId": "new", "parentUuid": "y", "cwd": tmp, "isSidechain": True, "agentId": "w1",
                 "message": {"role": "assistant", "content": "worker"}},
            ])
            os.utime(proj / "old.jsonl", (1, 1))
            os.utime(proj / "new.jsonl", (2000, 2000))
            with mock.patch.object(audit, "claude_root", return_value=projects):
                selected, warnings = audit.discover("claude", tmp, None)
        self.assertEqual({"new", "w1"}, {s["id"] for s in selected})
        self.assertEqual(["new"], [s["parent_session_id"] for s in selected if s["id"] == "w1"])
        self.assertEqual([], warnings)

    def test_claude_session_id_matching_a_child_returns_its_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "projects"
            proj = projects / "p"
            base = {"cwd": tmp, "isSidechain": False}
            write_jsonl(proj / "root-1.jsonl", [{"sessionId": "root-1", **base, "message": {"role": "user", "content": "hi"}}])
            write_jsonl(proj / "root-1" / "subagents" / "agent-w1.jsonl", [
                {"sessionId": "root-1", "cwd": tmp, "isSidechain": True, "agentId": "w1", "message": {"role": "assistant", "content": "w"}},
            ])
            with mock.patch.object(audit, "claude_root", return_value=projects):
                selected, _ = audit.discover("claude", tmp, "w1")
        self.assertEqual({"root-1", "w1"}, {s["id"] for s in selected})

    def test_zero_hit_explains_workspace_mismatch_instead_of_silence(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "projects"
            write_jsonl(projects / "p" / "r.jsonl", [{"sessionId": "r", "cwd": "/elsewhere", "message": {"role": "user", "content": "x"}}])
            with mock.patch.object(audit, "claude_root", return_value=projects):
                selected, warnings = audit.discover("claude", tmp, None)
        self.assertEqual([], selected)
        self.assertTrue(any("none matched workspace" in w and "/elsewhere" in w for w in warnings), warnings)
        self.assertTrue(any(w.startswith("No claude sessions matched") for w in warnings), warnings)

    # ---------------------------------------------------------------------- Cursor

    def test_redact_unwraps_cursor_user_query_and_drops_ide_context(self):
        text = (
            "<user_info>OS: darwin</user_info>\n<git_status>## main</git_status>\n"
            "<open_files>auth.ts</open_files>\n<linter_errors>TS2345</linter_errors>\n\n"
            "<user_query>fix the type error in auth.ts</user_query>"
        )
        self.assertEqual("fix the type error in auth.ts", audit.redact(text))
        self.assertEqual("plain text", audit.redact("<attached_files>x.py</attached_files>plain text"))
        self.assertEqual("no tags at all", audit.redact("no tags at all"))

    def test_slug_key_matches_cursor_and_claude_project_folders(self):
        self.assertEqual(audit.slug_key(r"C:\Dev\simulations\opc"), audit.slug_key("c-Dev-simulations-opc"))
        self.assertEqual(audit.slug_key(r"C:\Dev\simulations\opc"), audit.slug_key("C--Dev-simulations-opc"))
        self.assertEqual(audit.slug_key("/Users/me/my repo"), audit.slug_key("Users-me-my-repo"))
        self.assertNotEqual(audit.slug_key("/Users/me/repo"), audit.slug_key("Users-me-repo2"))

    def test_cursor_identity_from_flat_nested_and_subagent_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcripts = Path(tmp) / "projects" / "c-Repo-x" / "agent-transcripts"
            flat = write_jsonl(transcripts / "conv-flat.jsonl", [user("hi")])
            nested = write_jsonl(transcripts / "conv-nested" / "conv-nested.jsonl", [user("hi")])
            sub = write_jsonl(transcripts / "conv-nested" / "subagents" / "sub-1.jsonl", [assistant("worker")])
            flat_s = audit.parse_claude_like(flat, "cursor")
            nested_s = audit.parse_claude_like(nested, "cursor")
            sub_s = audit.parse_claude_like(sub, "cursor")
        self.assertEqual(("conv-flat", None, "c-Repo-x"), (flat_s["id"], flat_s["parent_session_id"], flat_s["project_slug"]))
        self.assertEqual(("conv-nested", None), (nested_s["id"], nested_s["parent_session_id"]))
        self.assertEqual(("sub-1", "conv-nested", "subagents/sub-1"), (sub_s["id"], sub_s["parent_session_id"], sub_s["agent_path"]))

    def test_cursor_discovery_matches_workspace_by_project_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = "/Users/me/my repo"
            projects = Path(tmp) / "projects"
            mine = projects / "Users-me-my-repo" / "agent-transcripts"
            other = projects / "Users-me-other" / "agent-transcripts"
            write_jsonl(mine / "old" / "old.jsonl", [user("<user_query>old</user_query>")])
            write_jsonl(mine / "conv" / "conv.jsonl", [
                user("<additional_data>ctx</additional_data><user_query>build it</user_query>"),
                assistant("delegating", {"type": "tool_use", "name": "Task", "input": {"subagent_type": "explore", "task": "scan repo"}}),
            ])
            write_jsonl(mine / "conv" / "subagents" / "sub-1.jsonl", [assistant("scanned")])
            write_jsonl(other / "x.jsonl", [user("not mine")])
            write_jsonl(projects / "Users-me-my-repo" / "not-a-transcript.jsonl", [user("ignored")])
            os.utime(mine / "old" / "old.jsonl", (1, 1))
            with mock.patch.object(audit, "cursor_root", return_value=projects):
                selected, warnings = audit.discover("cursor", workspace, None)
        self.assertEqual({"conv", "sub-1"}, {s["id"] for s in selected})
        root = next(s for s in selected if s["id"] == "conv")
        self.assertEqual(workspace, root["workspace"])
        self.assertEqual(["build it", "delegating"], [m["text"] for m in root["messages"]])
        self.assertEqual(("explore", "scan repo"), (root["calls"][0]["target"], root["calls"][0]["task_name"]))
        self.assertTrue(any("project directory slug" in w for w in warnings), warnings)
        self.assertFalse(any(w.startswith("No cursor sessions") for w in warnings), warnings)

    def test_cursor_zero_hit_names_other_project_slugs(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "projects"
            write_jsonl(projects / "Users-me-other" / "agent-transcripts" / "x.jsonl", [user("hi")])
            with mock.patch.object(audit, "cursor_root", return_value=projects):
                selected, warnings = audit.discover("cursor", "/Users/me/mine", None)
        self.assertEqual([], selected)
        self.assertTrue(any("none matched workspace" in w for w in warnings), warnings)
        self.assertTrue(any("IDE sidebar" in w for w in warnings), warnings)

    # ---------------------------------------------------------------- ExpertAgent

    def test_expert_events_filter_by_task_and_summarize(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / ".expertagent" / "tasks"
            write_jsonl(tasks / "fix-a" / "events.jsonl", [
                {"at": "03:55", "cmd": "init"},
                {"at": "04:02", "cmd": "assume", "id": "a1", "q": "null too?", "decision": "yes", "confidence": "med", "reversible": True, "secret": "x"},
                {"at": "04:10", "cmd": "retier", "from": "fast", "to": "standard", "stageFrom": "plan", "stageTo": "review"},
                {"at": "04:15", "cmd": "advance", "to": "done"}, {"cmd": "unknown"},
            ])
            write_jsonl(tasks / "quick-b" / "events.jsonl", [{"at": "05:00", "cmd": "init"}])
            everything = audit.expert_events(Path(tmp))
            only_a = audit.expert_events(Path(tmp), ["fix-a"])
            summary = audit.expert_task_summary(everything)
        self.assertEqual({"fix-a", "quick-b"}, {e["task_id"] for e in everything})
        self.assertEqual(["init", "assume", "retier", "advance"], [e["cmd"] for e in only_a])
        assume = only_a[1]
        self.assertEqual(("a1", "null too?", "yes", "med", True), (assume["id"], assume["q"], assume["decision"], assume["confidence"], assume["reversible"]))
        self.assertNotIn("secret", assume, "fields outside the allowlist must not leak")
        self.assertEqual(("plan", "review"), (only_a[2]["stageFrom"], only_a[2]["stageTo"]))
        self.assertEqual(
            [{"task_id": "fix-a", "events": 4, "first_at": "03:55", "last_at": "04:15"},
             {"task_id": "quick-b", "events": 1, "first_at": "05:00", "last_at": "05:00"}],
            summary,
        )


if __name__ == "__main__":
    unittest.main()
