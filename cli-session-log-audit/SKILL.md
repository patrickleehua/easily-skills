---
name: cli-session-log-audit
description: 跨 Codex、Claude Code、Cursor 和其他 CLI Agent 导出会话中的用户输入、模型输出及 Agent 调用关系，并按指定 Skill/SOP 审查重复询问、越权编排和模式失效。用户要求会话日志、session 审查、agent 调用链或对话复盘时使用；不用于读取业务文档内容。
compatibility: Python 3.10+；适用于能加载 SKILL.md 并访问本地文件的 Codex、Claude Code、Cursor 及其他 CLI Agent
---

# 会话日志审查

把会话事实还原成可复核日志，再单独写审查结论。目标不是总结业务内容，而是回答：用户说了什么、主会话如何回应、创建或续派了哪些 Agent、流程为何重复或停住。

## 输入与范围

优先使用用户给出的工作区、日期、会话 ID、transcript 路径、输出目录和审查基准。未给出时：

- 工作区取当前仓根。
- 会话取该工作区最近更新的主会话及其子会话。
- 输出目录取 `<工作区>/session-audit/`，文件名由脚本按“业务主题 + provider + 会话时间”生成（见下文“产物命名”）。
- 只读取会话存储与编排事件，不打开会话中提到的 PRD、代码、数据库或附件。

如果用户点名某个 Skill/SOP 作为审查基准，完整读取该规则；否则只输出事实，不自行发明流程规范。

## 必做流程

1. 确定 provider：`auto | codex | claude | cursor | generic`。不确定时用 `auto`。用户点名“这个 cursor 会话”就用 `cursor`。
2. 阅读 [providers.md](references/providers.md) 中对应 provider 的存储与限制。
3. 运行确定性脚本，先生成 JSON 事实包：

   ```bash
   python <skill-root>/scripts/session_log_audit.py --provider auto --workspace <absolute-workspace> --format json
   ```

   常用参数：
   - `--session-id <id>`：指定会话（根会话或子代理 id 的片段；命中子代理会自动带出其根会话）。
   - `--input <path>`：用户给出 transcript 时传入，可重复；给了 `--input` 就不再扫描本机存储，只读这些文件及其子代理。方言跟随 `--provider`，`auto` 下按路径和首行自动识别；传入 Cursor/Claude 根 transcript 时会自动带上同目录 `subagents/` 下的子代理文件。**不要**为了让脚本读到内容而手工改写 transcript（改字段名、拆文件、另存“规范化副本”）：那会使 `source_ref` 行号失去可追溯性；解析不到就把它当成解析器缺陷报告，再修脚本。
   - `--task-id <task>`：工作区里有多个 ExpertAgent 任务并行时只保留目标任务；不传时脚本会从会话里实际执行的 `sop.mjs --task` 命令推断。
   - `--topic <名称>`：覆盖文件名中的业务主题。
   - `--output-dir <dir>` / `--output <file>`：改输出位置；`--output` 只改事实包路径。
4. 读脚本打印的摘要：`sessions`、`messages`、`human_turns`、`calls`、`sop_calls`、`expert_events`、`task_ids`、`warnings`、`report_path`。
   - 零命中时先看 `warnings` 区分“存储根目录不存在”“有会话但工作区不匹配”“判根失败/为空”（见 providers.md 的零命中诊断），原样报告，不得把“未找到”写成“没有发生”。
   - `human_turns` 是主会话里真人输入的条数（`origin` 为 `human`/`command`）。`origin=system` 的 user 行是宿主注入（task-notification、本地命令输出、system-reminder、非人工的排队命令），不能算成“用户调用”。
   - `expert_tasks` 列出的任务多于目标会话实际执行的任务时，用 `--task-id` 重跑，或在报告中注明哪些任务不属于此会话。
   - 会话 `warnings` 里出现 “transcript may start mid-task” 表示该文件第一条可见消息就是助手：前面的轮次不在这份文件里，只能写成“本文件缺此段”，不能写成“当时没派”。
5. 需要纯事实日志时，可让脚本直接渲染 Markdown（`--format markdown`）；需要流程审查时，由当前 Agent 基于 JSON 事实包和指定规则生成最终报告，写到摘要里的 `report_path`。
6. 写完后验证文件存在、必需章节齐全、事实编号能追溯到 `source_ref`。

## 产物命名

脚本按会话内容生成文件名，报告与事实包成对放在同一目录：

```text
<output-dir>/会话日志事实-<主题>-<provider>-<YYYYMMDD-HHMM>.json   # 脚本写
<output-dir>/会话日志审查-<主题>-<provider>-<YYYYMMDD-HHMM>.md     # 当前 Agent 写审查报告
```

- 主题优先级：`--topic` > 会话实际执行的 ExpertAgent 任务 id（多个用 `-` 连接）> 主会话第一条真人输入去掉斜杠命令后的前 24 字。不满意就用 `--topic` 重跑，不要手工改名，否则报告与事实包对不上。
- 时间取被审会话本身的时间（主会话第一条消息的本地时间；Cursor 无时间戳时退回 transcript 修改时间），不是审查执行时间。审查执行时间写在报告正文和事实包 `generated_at`。
- 事实包 `naming` 字段记录了主题与时间各自的依据（`topic_basis`、`session_time_basis`），报告“范围与数据源”要转述。
- 同一会话多次审查会覆盖同名文件；需要保留历史版本时用 `--output-dir` 分目录。
- 只允许写这两个文件；不得把产物写到仓根或改名成固定的 `日志审查.md`。

## 报告结构

保持用户偏好的叙事格式，至少包含：

```markdown
# 会话日志审查：<主题>（<会话时间>）

## 范围与数据源
- 审查对象 / provider / 会话 id / transcript 路径
- 事实包路径、生成时间、命名依据
- 脚本摘要（sessions / human_turns / calls / sop_calls / expert_events）与 warnings 原文
- 限制（据实记录，不补写）

## Agent 调用关系

### 用户调用 1
- <用户实际请求>（M 编号 + source_ref）

### 现象 1
- <主会话动作>
- <Agent 调用或返回>

### 主会话输出
> <用户可见输出>

## 事件清单
## 审查结论
## 改进建议
```

事实与判断必须分开：

- “发生了什么”引用 session/message/call/sop_call/event 的编号或源路径。
- “哪里有问题”引用对应事实及被违反的规则条款。
- 无法读取、参数加密、日志缺失均写成限制，不补写缺失对话。
- 审查动作本身（用户说“审查这个会话”那一轮，以及为此派出的审查子代理）不纳入业务编排评分，但要在范围里注明。

## 事实包里可用的编排线索

- `sessions[].messages[].origin`：`human` / `command` / `system` / `assistant`。“用户调用 N”只从 `human`/`command` 里取；`phase=queued` 表示用户在 Agent 忙时排队输入。
- `sessions[].calls[]`：Agent/Task/SendMessage 等派发调用，含 `target`、`task_name`、`extra`（resume、name、run_in_background 等标量参数）和 `prompt_preview`（前 200 字）。用它核对“说派了”和“真派了”。
- `sessions[].sop_calls[]`：主会话或子代理**实际执行**的 `sop.mjs <cmd> --task ...` 命令（只从 Shell/Bash 类工具入参提取；写在派发 prompt 里的指令不算）。用它核对 `evidence --by`、`sign --by`、`answer` 等是谁跑的。
- `sessions[].agent`：Claude Code 子代理的 `meta.json`（`type`、`name`、`description`、`parent_agent_id`、`spawn_depth`）。`parent_agent_id` 非空说明是领衔自己派的同事，`agent_path` 写成 `父/子`。
- `sessions[].row_types`：被跳过的非消息行计数（如 `queue-operation`、`attachment`、`bridge-session`），只作缺口说明，不猜含义。
- `expert_events[]` / `expert_tasks[]` / `task_ids`：ExpertAgent 台账及本次实际纳入的任务。

## Agent 编排审查

只有用户要求审查时才评判。重点检查：

- 主会话是否把整个任务交给领衔，还是逐个问题直接派同事。
- 同一问题是否在用户、主会话和多个专家之间重复流转。
- `auto/assist/strict` 等模式的实际人工触点是否符合其承诺：开工是否等了人回话、`init` 的 `modeBy/tierBy/ack` 与用户原话是否一致。
- “以后由某人提供”是否被错误登记为问题已经解决。
- 文档完成、实施输入齐备、代码完成和上线批准是否被混成一个“完成”。
- 评审、返修、复审是否有真实调用与结果（`calls` + 子代理 transcript + `review` 事件），而非模型自述。
- 签核类触点（`sign --by`、`answer`）是否对应用户原话；用户只回“确认”而台账写了人名时要指出。
- 用户说“清除上下文/重新开始”后，主会话是接续磁盘上的旧任务还是新开；对用户的说法与台账是否一致。
- Cursor 宿主：`Task` 的 `subagent_type` 是否按专家卡派（能枚举 `ea-*` 时不应全是 `generalPurpose`）、`dispatch --nested` 与实际能否嵌套是否一致。

不要因为看到多个 Agent 就判定有问题；阶段门独立 reviewer、写审分离和失败返修通常是正当调用。

## 隐私与真实性

- 默认只保留用户可见的 `user`/`assistant` 文本和编排元数据。
- 排除 system/developer 指令、模型推理、tool result、技能全文、环境块及附件正文。
- 对疑似 token、password、secret、API key 和 Bearer 值进行脱敏。
- 不运行 `agent --resume`、不恢复旧会话、不修改原始 session。
- 不把 IDE/CLI 零命中当作用户未使用该工具的证据。
- 脚本只写事实包；当前 Agent 只写 `report_path` 指向的报告。

## 跨 CLI 边界

Codex、Claude Code 与 Cursor agent transcript 有内置适配。Cursor 只覆盖 `~/.cursor/projects/<项目>/agent-transcripts/`，按项目目录名与工作区路径的 slug 匹配，用户消息只保留 `<user_query>` 内文；IDE sidebar 私有存储不解析。其他 CLI 使用 `generic` 加显式导出文件；不得声称支持未验证的私有数据库格式。新 provider 应作为独立解析器加入脚本，并用脱敏 fixture 验证后再列为内置支持。

本目录是工具中立真源。Codex/Claude/Cursor 可把该目录加入各自 Skill 搜索路径或建立目录链接；不要复制并分别维护多份 `SKILL.md`。不支持 Skills 的 CLI 可直接读取本文件并运行同一脚本。改脚本后运行 `python -m unittest scripts/test_session_log_audit.py`。
