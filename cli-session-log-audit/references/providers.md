# Provider Stores and Limits

只读取与当前工作区或显式输入匹配的文件。下列路径均可被环境变量或用户参数覆盖。

## Codex

- 默认根：`${CODEX_HOME}/sessions`；未设置时 `~/.codex/sessions`。
- 常见文件：`rollout-*.jsonl`。
- 可取事实：`session_meta`、工作区、父子 session、user/assistant message、collaboration tool call。
- 限制：工具参数可能加密。此时只记录工具名、call id 和 `unavailable_encrypted`。

## Claude Code

- 默认根：`${CLAUDE_CONFIG_DIR}/projects`；未设置时 `~/.claude/projects`。
- 目录布局：
  - 根会话：`<projects>/<工作区 slug>/<sessionId>.jsonl`，slug 形如 `C--Users-me-repo`。
  - 子代理：`<projects>/<slug>/<sessionId>/subagents/agent-<agentId>.jsonl`，行内 `isSidechain=true`、`agentId=<agentId>`，且 `sessionId` 与父会话相同。
- 可取事实：`sessionId`、`cwd`、`isSidechain`、`agentId`、user/assistant message、`tool_use`。
- 根会话判定只看 `isSidechain`/`agentId`/是否位于 `subagents/` 目录。`parentUuid` 是同一会话内逐条消息的链式指针，不是跨会话父子关系，脚本不用它判根。
- 工作区匹配：先按目录 slug 缩小范围，再以行内 `cwd` 为准；slug 不命中时退回全量扫描。
- 限制：不同版本字段会变化；`mode`/`bridge-session`/`file-history-snapshot` 等非消息行被跳过；未知行保留 warning，不猜字段含义。

## Cursor

- 默认根：`${CURSOR_CONFIG_DIR}/projects`；未设置时 `~/.cursor/projects`。
- 目录布局（只扫 `agent-transcripts` 下的 `.jsonl`）：
  - 项目目录名是工作区路径的转义：去掉开头 `/`，非字母数字一律换成 `-`，例如 `C:\Dev\simulations\opc` → `c-Dev-simulations-opc`、`/Users/me/my repo` → `Users-me-my-repo`。
  - CLI 扁平布局：`<project>/agent-transcripts/<conversation_id>.jsonl`。
  - IDE 嵌套布局：`<project>/agent-transcripts/<conversation_id>/<conversation_id>.jsonl`。
  - 子代理：同一 `<conversation_id>/` 目录下的其他 `.jsonl`（含子目录），脚本记为该会话的子会话，`agent_path` 为相对路径。
- 行格式：每行只有 `role` 与 `message`，`message.content` 为 `text`/`tool_use` 块；**没有** `cwd`、时间戳、消息 id、tool result 与 usage。
- 工作区匹配：transcript 无 `cwd`，脚本把项目目录名和工作区路径都归一为“小写 + 连续非字母数字折叠成一个 `-`”后比较，命中的会话 `workspace` 置为传入的工作区，并在 warnings 里注明是按目录 slug 匹配。理论上 `my-repo` 与 `my repo` 会撞 slug，遇到时用 `--session-id` 指定。
- 用户消息清洗：Cursor 会把 IDE 上下文（`<user_info>`、`<git_status>`、`<open_files>`、`<linter_errors>`、`<additional_data>`、`<attached_files>` 等）和用户原文（`<user_query>`）拼在同一条 user 消息里。脚本只保留 `<user_query>` 内文；没有该标签时剥掉已知上下文标签，其余原样保留。
- IDE sidebar chats（`state.vscdb` / `store.db`）是另一私有存储，本脚本不解析；如果仓内已有 `bf-tools-CursorSessions`，可先用它导出，再把导出文件传给 `--input`。
- IDE 零命中不代表没有使用 Cursor；只表示 agent transcripts 目录下没有匹配文件，或 Cursor 关闭了 transcript 记录。

## Generic / Other CLI Agents

- 使用 `--provider generic --input <json|jsonl|md>`。
- JSON/JSONL 优先识别通用 `role/content`、`message.role/message.content`、OpenAI `choices[].message` 和 `tool_calls` 结构。
- Markdown 识别 `## User`、`## Assistant`、`user:`、`assistant:` 等显式角色标记。
- Aider、Gemini CLI、OpenCode、Copilot CLI 等若能导出为上述格式即可使用；未提供稳定格式时不做私有目录自动发现承诺。

## 零命中诊断

脚本在 0 命中时会区分三种原因并写入 `warnings`，报告里必须原样转述，不得写成“没有发生”：

- `<provider> session root not found`：存储目录不存在，通常是没装或没用过该工具。
- `N transcript(s) parsed but none matched workspace`：有会话但工作区不同，附带看到的其他工作区（前 3 个）。
- `matched workspace but all were classified as child transcripts` / `all are empty`：会话在但判根失败或为空，改用 `--session-id`。

## ExpertAgent Optional Events

- 工作区存在 `.expertagent/tasks/*/events.jsonl` 时自动合并。
- 只取 sop.mjs 全部命令的编排字段：`init/dispatch/outcome/review/ask/answer/advance/sign/note/evidence/assume/overturn/retier/extend/wait/size/depends/finish`。`assume` 保留 `q/decision/basis/confidence/reversible`，`overturn` 保留 `answer/voided`，`retier` 保留 `stageFrom/stageTo`；白名单外的字段一律丢弃，未知 cmd 直接跳过，不猜含义。
- 事件按整个工作区扫描，不区分会话；同一工作区多个并行窗口各跑各的任务时会混在一起。用 `--task-id <task>`（可重复）只保留目标会话实际执行的任务，`expert_tasks` 汇总了每个任务的事件数与首末时间，便于和会话时间轴对齐。
- 事件记录用于补充事实，不替代宿主 session 的用户/模型消息。
