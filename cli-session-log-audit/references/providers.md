# Provider Stores and Limits

只读取与当前工作区或显式输入匹配的文件。下列路径均可被环境变量或用户参数覆盖。

## Codex

- 默认根：`${CODEX_HOME}/sessions`；未设置时 `~/.codex/sessions`。
- 常见文件：`rollout-*.jsonl`。
- 可取事实：`session_meta`、工作区、父子 session、user/assistant message、collaboration tool call、`function_call` 里的 `sop.mjs` 命令。
- 限制：工具参数可能加密。此时只记录工具名、call id 和 `unavailable_encrypted`。

## Claude Code

- 默认根：`${CLAUDE_CONFIG_DIR}/projects`；未设置时 `~/.claude/projects`。
- 目录布局：
  - 根会话：`<projects>/<工作区 slug>/<sessionId>.jsonl`，slug 形如 `C--Users-me-repo`。
  - 子代理：`<projects>/<slug>/<sessionId>/subagents/agent-<agentId>.jsonl`，行内 `isSidechain=true`、`agentId=<agentId>`，且 `sessionId` 与父会话相同。
  - 子代理元数据：同目录 `agent-<agentId>.meta.json`，含 `agentType`、`name`、`description`、`toolUseId`、`parentAgentId`、`spawnDepth`。脚本读入 `sessions[].agent`；`parentAgentId` 非空说明该实例是另一个子代理（通常是领衔）派的，`agent_path` 写成 `父/子`。
  - `tool-results/` 目录是工具结果溢出文件，不读。
- 可取事实：`sessionId`、`cwd`、`isSidechain`、`agentId`、user/assistant message、`tool_use`（Agent/Task/SendMessage 派发与 Bash 里的 `sop.mjs` 命令）。
- user 行分类（`messages[].origin`）：
  - `command`：`<command-name>/x</command-name><command-args>…</command-args>`，渲染为 `/x …`，算真人输入。
  - `system`：`<task-notification>`、`<local-command-stdout>`、`<local-command-caveat>`、`<system-reminder>` 等宿主注入，或 `isMeta=true` 的行；只保留标签名和宿主自己的 `<summary>`。
  - 只含 `tool_result` 块的 user 行没有可见文本，直接跳过。
  - 用户在 Agent 忙时输入的内容不在 user 行里，而在 `type=attachment` 且 `attachment.type=queued_command` 的行：脚本按 `attachment.origin.kind` 判定 `human`/`system`，`phase=queued`。
- 根会话判定只看 `isSidechain`/`agentId`/是否位于 `subagents/` 目录。`parentUuid` 是同一会话内逐条消息的链式指针，不是跨会话父子关系，脚本不用它判根。
- 工作区匹配：先按目录 slug 缩小范围，再以行内 `cwd` 为准；slug 不命中时退回全量扫描。
- 限制：不同版本字段会变化；`queue-operation`/`bridge-session`/`attachment`/`last-prompt`/`ai-title`/`file-history-snapshot` 等非消息行只计数进 `row_types`，不猜字段含义。

## Cursor

- 默认根：`${CURSOR_CONFIG_DIR}/projects`；未设置时 `~/.cursor/projects`。
- 目录布局（只扫 `agent-transcripts` 下的 `.jsonl`）：
  - 项目目录名是工作区路径的转义：去掉开头 `/`，非字母数字一律换成 `-`，例如 `C:\Dev\simulations\opc` → `c-Dev-simulations-opc`、`E:\workspace\gx-server` → `e-workspace-gx-server`、`/Users/me/my repo` → `Users-me-my-repo`。
  - CLI 扁平布局：`<project>/agent-transcripts/<conversation_id>.jsonl`。
  - IDE 嵌套布局：`<project>/agent-transcripts/<conversation_id>/<conversation_id>.jsonl`。
  - 子代理：同一 `<conversation_id>/` 目录下的其他 `.jsonl`（实际见过 `subagents/<uuid>.jsonl`），脚本记为该会话的子会话，`agent_path` 为相对路径。子代理文件名就是 `Task` 的 resume id，可与主会话 `calls[].extra.resume` 对上。
- 行格式：每行只有**顶层** `role` 与 `message`，`message` 里没有 `role`；`message.content` 为 `text`/`tool_use` 块。**没有** `cwd`、消息 id、tool result 与 usage。时间戳只在用户行文本里以 `<timestamp>…</timestamp>` 出现时才有，脚本取为该条消息的 `timestamp`。
- 工具调用：`Task` 块的 `input` 含 `subagent_type`（常见 `generalPurpose` 或专家卡名）、`description`、`prompt`，续派时带 resume id；`Shell`/终端类工具的 `command` 里能看到 `sop.mjs` 命令。脚本把前者记进 `calls`（含 `extra` 与 `prompt_preview`），后者记进 `sop_calls`。
- 工作区匹配：transcript 无 `cwd`，脚本把项目目录名和工作区路径都归一为“小写 + 连续非字母数字折叠成一个 `-`”后比较，命中的会话 `workspace` 置为传入的工作区，并在 warnings 里注明是按目录 slug 匹配。理论上 `my-repo` 与 `my repo` 会撞 slug，遇到时用 `--session-id` 指定。
- 显式输入：`--provider cursor --input <root.jsonl>` 直接按 Cursor 方言解析，会话 id 取自路径，不再哈希；嵌套布局下自动带入同目录子代理文件；`workspace` 置为 `--workspace`。
- 用户消息清洗：Cursor 会把 IDE 上下文（`<user_info>`、`<git_status>`、`<open_files>`、`<linter_errors>`、`<additional_data>`、`<attached_files>`、`<timestamp>` 等）和用户原文（`<user_query>`）拼在同一条 user 消息里。脚本只保留 `<user_query>` 内文；没有该标签时剥掉已知上下文标签，其余原样保留。
- 会话可能从中途开始：用户“清除上下文”后再续，同一 transcript 的第一条可见消息可能已是助手在接续旧任务，前面的 `Task` 不在此文件。脚本对此打 warning（`may start mid-task`），报告只能写“本文件缺此段”。
- IDE sidebar chats（`~/.cursor/chats/<md5>/<uuid>/` 的 `meta.json`、`prompt_history.json`）是另一私有存储，本脚本不解析；如果仓内已有 `bf-tools-CursorSessions`，可先用它列出会话，再把 transcript 路径传给 `--input`。
- IDE 零命中不代表没有使用 Cursor；只表示 agent transcripts 目录下没有匹配文件，或 Cursor 关闭了 transcript 记录。零命中 warning 会附带看到的其他项目 slug（前 3 个），用来判断是工作区路径写错还是根本没有记录。

## Generic / Other CLI Agents

- 使用 `--provider generic --input <json|jsonl|md>`。
- JSON/JSONL 优先识别通用 `role/content`（顶层或 `message` 内）、OpenAI `choices[].message`、`tool_calls` 以及 content 里的 `tool_use` 块。
- Markdown 识别 `## User`、`## Assistant`、`user:`、`assistant:` 等显式角色标记。
- Aider、Gemini CLI、OpenCode、Copilot CLI 等若能导出为上述格式即可使用；未提供稳定格式时不做私有目录自动发现承诺。
- `--provider auto` 下的显式输入按路径与首 30 行自动识别方言：路径含 `agent-transcripts` → cursor；`subagents/agent-*.jsonl` 或行内 `sessionId`+`cwd` → claude；`session_meta` → codex；否则 generic。

## 零命中诊断

脚本在 0 命中时会区分三种原因并写入 `warnings`，报告里必须原样转述，不得写成“没有发生”：

- `<provider> session root not found`：存储目录不存在，通常是没装或没用过该工具。
- `N transcript(s) parsed but none matched workspace`：有会话但工作区不同，附带看到的其他工作区（前 3 个）。
- `matched workspace but all were classified as child transcripts` / `all are empty`：会话在但判根失败或为空，改用 `--session-id`。

## ExpertAgent Optional Events

- 工作区存在 `.expertagent/tasks/*/events.jsonl` 时自动合并。
- 只取 sop.mjs 全部命令的编排字段：`init/dispatch/outcome/review/ask/answer/advance/sign/note/evidence/assume/overturn/retier/extend/wait/size/depends/finish`。`init` 保留 `mode/tier/modeBy/tierBy/ack/flow`，`dispatch` 保留 `purpose/nested/resume/coldStart/via`，`assume` 保留 `q/decision/basis/confidence/reversible`，`overturn` 保留 `answer/voided`，`retier` 保留 `stageFrom/stageTo`；白名单外的字段一律丢弃，未知 cmd 直接跳过，不猜含义。
- 事件按整个工作区扫描，不区分会话；同一工作区多个并行窗口各跑各的任务时会混在一起。不传 `--task-id` 时脚本从会话 `sop_calls` 里的 `--task` 推断并只保留这些任务（warning 会注明）；推断不到且有多个任务时提示传 `--task-id`。`expert_tasks` 汇总了每个任务的事件数与首末时间，便于和会话时间轴对齐。
- 事件记录用于补充事实，不替代宿主 session 的用户/模型消息。

## 产物命名

- 事实包：`<output-dir>/会话日志事实-<主题>-<provider>-<YYYYMMDD-HHMM>.json`（`--format markdown` 时为 `.md`）。
- 报告：`<output-dir>/会话日志审查-<主题>-<provider>-<YYYYMMDD-HHMM>.md`，路径由脚本摘要 `report_path` 给出。
- `<output-dir>` 默认 `<workspace>/session-audit`；`<主题>` 见 SKILL.md“产物命名”；`<provider>` 为纳入会话的 provider（多个用 `-` 连接）。
- 文件名中的非法字符（`\ / : * ? " < > |` 与空白）折叠成 `-`，主题最长 40 字。
