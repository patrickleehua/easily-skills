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

    # ------------------------------------------------------------ v1.2 additions

    def test_generic_reads_top_level_role_and_tool_use_blocks(self):
        rows = [
            {"role": "user", "message": {"content": [{"type": "text", "text": "<user_query>go</user_query>"}]}},
            {"role": "assistant", "message": {"content": [
                {"type": "text", "text": "ok"},
                {"type": "tool_use", "id": "t1", "name": "Task", "input": {"subagent_type": "ea-planner", "description": "plan it", "prompt": "long prompt"}},
            ]}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            sessions = audit.parse_generic(write_jsonl(Path(tmp) / "export.jsonl", rows))
        self.assertEqual(["go", "ok"], [m["text"] for m in sessions[0]["messages"]])
        self.assertEqual("ea-planner", sessions[0]["calls"][0]["target"])
        self.assertEqual("long prompt", sessions[0]["calls"][0]["prompt_preview"])

    def test_explicit_cursor_input_uses_cursor_dialect_and_pulls_subagents(self):
        with tempfile.TemporaryDirectory() as tmp:
            transcripts = Path(tmp) / "projects" / "e-workspace-gx" / "agent-transcripts"
            root = write_jsonl(transcripts / "conv" / "conv.jsonl", [
                user("<timestamp>2026-09-09T15:26:00+08:00</timestamp><user_query>只做机器人打牌</user_query>"),
                assistant("派策划", {"type": "tool_use", "id": "t1", "name": "Task",
                                  "input": {"subagent_type": "generalPurpose", "description": "返修规格", "resume": "b294cda9", "prompt": "宿主降级"}}),
            ])
            write_jsonl(transcripts / "conv" / "subagents" / "sub-1.jsonl", [assistant("done")])
            sessions, warnings = audit.load_inputs([str(root)], "cursor", r"E:\workspace\gx")
        self.assertEqual({"conv", "sub-1"}, {s["id"] for s in sessions})
        main = next(s for s in sessions if s["id"] == "conv")
        self.assertEqual("cursor", main["provider"])
        self.assertEqual(r"E:\workspace\gx", main["workspace"])
        self.assertEqual("2026-09-09T15:26:00+08:00", main["messages"][0]["timestamp"])
        self.assertEqual({"resume": "b294cda9", "subagent_type": "generalPurpose"}, main["calls"][0]["extra"])
        self.assertTrue(any("explicit input" in w for w in warnings), warnings)

    def test_detect_provider_from_path_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex = write_jsonl(Path(tmp) / "rollout.jsonl", [{"type": "session_meta", "payload": {"id": "x", "cwd": tmp}}])
            claude = write_jsonl(Path(tmp) / "s.jsonl", [{"sessionId": "s", "cwd": tmp, "message": {"role": "user", "content": "hi"}}])
            plain = write_jsonl(Path(tmp) / "plain.jsonl", [{"role": "user", "content": "hi"}])
            cursor = Path(tmp) / "agent-transcripts" / "c.jsonl"
            self.assertEqual("codex", audit.detect_provider(codex))
            self.assertEqual("claude", audit.detect_provider(claude))
            self.assertEqual("generic", audit.detect_provider(plain))
            self.assertEqual("cursor", audit.detect_provider(cursor))

    def test_user_rows_are_tagged_by_origin(self):
        rows = [
            {"type": "user", "sessionId": "r", "cwd": "/repo", "timestamp": "2026-09-07T07:27:57Z",
             "message": {"role": "user", "content": "<command-message>expertagent</command-message>\n<command-name>/expertagent</command-name>\n<command-args>做 014</command-args>"}},
            {"type": "user", "sessionId": "r", "cwd": "/repo", "isMeta": True,
             "message": {"role": "user", "content": "<local-command-caveat>Caveat: DO NOT respond</local-command-caveat>"}},
            {"type": "user", "sessionId": "r", "cwd": "/repo",
             "message": {"role": "user", "content": "<task-notification>\n<task-id>a1</task-id>\n<status>completed</status>\n<summary>Agent \"Dev\" finished</summary>\n</task-notification>"}},
            {"type": "user", "sessionId": "r", "cwd": "/repo",
             "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "ignored"}]}},
            {"type": "user", "sessionId": "r", "cwd": "/repo",
             "message": {"role": "user", "content": "<system-reminder>injected</system-reminder>继续开发啊"}},
            {"type": "queue-operation", "operation": "enqueue", "sessionId": "r"},
            {"type": "last-prompt", "lastPrompt": "x", "sessionId": "r"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session = audit.parse_claude_like(write_jsonl(Path(tmp) / "p" / "r.jsonl", rows), "claude")
        self.assertEqual(
            [("command", "/expertagent 做 014"), ("system", "[local-command-caveat] Caveat: DO NOT respond"),
             ("system", '[task-notification] Agent "Dev" finished'), ("human", "继续开发啊")],
            [(m["origin"], m["text"]) for m in session["messages"]],
        )
        self.assertEqual({"queue-operation": 1, "last-prompt": 1}, session["row_types"])
        self.assertEqual("2026-09-07T07:27:57Z", session["started_at"])

    def test_claude_queued_commands_count_as_user_turns(self):
        rows = [
            {"type": "attachment", "sessionId": "r", "cwd": "/repo", "attachment": {
                "type": "queued_command", "prompt": [{"type": "text", "text": "做到什么地步了"}],
                "origin": {"kind": "human"}, "timestamp": "2026-09-07T11:51:55Z"}},
            {"type": "attachment", "sessionId": "r", "cwd": "/repo", "attachment": {
                "type": "queued_command", "prompt": [{"type": "text", "text": "/loop tick"}], "origin": {"kind": "loop"}}},
            {"type": "attachment", "sessionId": "r", "cwd": "/repo", "attachment": {"type": "other"}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session = audit.parse_claude_like(write_jsonl(Path(tmp) / "p" / "r.jsonl", rows), "claude")
        self.assertEqual([("human", "做到什么地步了", "queued", "2026-09-07T11:51:55Z"), ("system", "/loop tick", "queued", None)],
                         [(m["origin"], m["text"], m["phase"], m["timestamp"]) for m in session["messages"]])
        self.assertEqual({"attachment": 1}, session["row_types"])

    def test_sop_text_inside_agent_prompt_is_not_an_executed_call(self):
        rows = [assistant("派", {"type": "tool_use", "id": "t", "name": "Agent", "input": {
            "subagent_type": "ea-planner", "prompt": "登记时跑 node sop.mjs evidence --task x --by planner"}})]
        with tempfile.TemporaryDirectory() as tmp:
            session = audit.parse_claude_like(write_jsonl(Path(tmp) / "p" / "r.jsonl", rows), "claude")
        self.assertEqual([], session["sop_calls"])
        self.assertEqual(1, len(session["calls"]))

    def test_claude_subagent_meta_json_enriches_agent_and_nesting(self):
        rows = [{"sessionId": "root-1", "cwd": "/repo", "isSidechain": True, "agentId": "a2",
                 "message": {"role": "assistant", "content": "nudged"}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_jsonl(Path(tmp) / "p" / "root-1" / "subagents" / "agent-a2.jsonl", rows)
            path.with_name("agent-a2.meta.json").write_text(json.dumps({
                "agentType": "ea-developer", "name": "dev-nudge", "description": "Nudge dev",
                "toolUseId": "toolu_1", "parentAgentId": "a1", "spawnDepth": 2}), encoding="utf-8")
            session = audit.parse_claude_like(path, "claude")
        self.assertEqual("ea-developer", session["agent"]["type"])
        self.assertEqual("a1", session["parent_agent_id"])
        self.assertEqual("a1/a2", session["agent_path"])
        self.assertEqual("root-1", session["parent_session_id"], "family selection still keys on the root session")

    def test_mid_task_transcript_is_flagged_not_silenced(self):
        rows = [assistant("resuming d12"), user("<user_query>继续</user_query>")]
        with tempfile.TemporaryDirectory() as tmp:
            session = audit.parse_claude_like(write_jsonl(Path(tmp) / "agent-transcripts" / "c.jsonl", rows), "cursor")
        self.assertTrue(any("mid-task" in w for w in session["warnings"]), session["warnings"])

    def test_sop_calls_are_extracted_from_any_tool_input_and_infer_task_ids(self):
        rows = [
            assistant("记账", {"type": "tool_use", "id": "t1", "name": "Shell", "input": {
                "command": "node .expertagent/sop.mjs dispatch --task anbao-bot-play --expert ea-planner --resume d11 --token=abc123456789"}}),
            assistant("登记", {"type": "tool_use", "id": "t2", "name": "Bash", "input": {
                "command": "node sop.mjs evidence --task anbao-bot-play --kind test --by 主会话 && node sop.mjs advance --task other-task --to done"}}),
            assistant("无关", {"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "git status"}}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session = audit.parse_claude_like(write_jsonl(Path(tmp) / "agent-transcripts" / "c.jsonl", rows), "cursor")
        self.assertEqual([("dispatch", "anbao-bot-play"), ("evidence", "anbao-bot-play"), ("advance", "other-task")],
                         [(c["cmd"], c["task"]) for c in session["sop_calls"]])
        self.assertIn("[REDACTED]", session["sop_calls"][0]["argv"])
        self.assertEqual([], session["calls"], "sop.mjs calls are not agent calls")
        self.assertEqual(["anbao-bot-play", "other-task"], audit.inferred_task_ids([session]))

    def test_topic_and_time_naming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_jsonl(Path(tmp) / "agent-transcripts" / "c.jsonl", [
                user("<user_query>/expertagent 帮我执行飞书总需求，只要子项目「机器人打牌」，其它子项目不执行</user_query>"),
            ])
            session = audit.parse_claude_like(root, "cursor")
            session["mtime"] = 1788000000
        topic, basis = audit.derive_topic([session], [], None)
        self.assertEqual("first_user_message", basis)
        self.assertTrue(topic.startswith("帮我执行飞书总需求") and len(topic) <= 24, topic)
        self.assertEqual(("anbao-bot-play", "expert_task"), audit.derive_topic([session], ["anbao-bot-play"], None))
        self.assertEqual(("机器人-打牌", "user"), audit.derive_topic([session], [], "机器人 打牌"))
        stamp, basis = audit.session_time([session])
        self.assertEqual("transcript_mtime", basis)
        self.assertRegex(stamp, r"^\d{8}-\d{4}$")
        session["messages"][0]["timestamp"] = "2026-09-09T07:26:00Z"
        self.assertEqual("first_message", audit.session_time([session])[1])
        self.assertEqual("untitled", audit.safe_name("  /:*? "))

    def test_main_writes_auto_named_outputs(self):
        import io
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            transcript = write_jsonl(Path(tmp) / "agent-transcripts" / "conv.jsonl", [
                user("<user_query>做机器人打牌</user_query>"),
                assistant("好", {"type": "tool_use", "id": "t", "name": "Shell", "input": {"command": "node sop.mjs init --task bot-play"}}),
            ])
            write_jsonl(workspace / ".expertagent" / "tasks" / "bot-play" / "events.jsonl", [{"at": "1", "cmd": "init"}])
            write_jsonl(workspace / ".expertagent" / "tasks" / "unrelated" / "events.jsonl", [{"at": "1", "cmd": "init"}])
            argv = ["prog", "--provider", "cursor", "--workspace", str(workspace), "--input", str(transcript)]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(audit, "cursor_root", return_value=Path(tmp) / "missing"), \
                    mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                audit.main()
            summary = json.loads(out.getvalue())
            facts = Path(summary["output"])
            self.assertEqual((workspace / "session-audit").resolve(), facts.parent.resolve())
            self.assertRegex(facts.name, r"^会话日志事实-bot-play-cursor-\d{8}-\d{4}\.json$")
            self.assertRegex(Path(summary["report_path"]).name, r"^会话日志审查-bot-play-cursor-\d{8}-\d{4}\.md$")
            bundle = json.loads(facts.read_text(encoding="utf-8"))
            self.assertEqual(["bot-play"], bundle["task_ids"])
            self.assertEqual(["bot-play"], [e["task_id"] for e in bundle["expert_events"]])
            self.assertEqual(1, summary["human_turns"])


if __name__ == "__main__":
    unittest.main()
