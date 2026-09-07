---
name: cli-session-log-audit
description: 跨 Codex、Claude Code、Cursor 和其他 CLI Agent 导出会话中的用户输入、模型输出及 Agent 调用关系，并按指定 Skill/SOP 审查重复询问、越权编排和模式失效。用户要求会话日志、session 审查、agent 调用链或对话复盘时使用；不用于读取业务文档内容。
compatibility: Python 3.10+；适用于能加载 SKILL.md 并访问本地文件的 Codex、Claude Code、Cursor 及其他 CLI Agent
---

# 会话日志审查

把会话事实还原成可复核日志，再单独写审查结论。目标不是总结业务内容，而是回答：用户说了什么、主会话如何回应、创建或续派了哪些 Agent、流程为何重复或停住。

## 输入与范围

优先使用用户给出的工作区、日期、会话 ID、输出路径和审查基准。未给出时：

- 工作区取当前仓根。
- 会话取该工作区最近更新的主会话及其子会话。
- 输出取仓根 `日志审查.md`。
- 只读取会话存储与编排事件，不打开会话中提到的 PRD、代码、数据库或附件。

如果用户点名某个 Skill/SOP 作为审查基准，完整读取该规则；否则只输出事实，不自行发明流程规范。

## 必做流程

1. 确定 provider：`auto | codex | claude | cursor | generic`。不确定时用 `auto`。
2. 阅读 [providers.md](references/providers.md) 中对应 provider 的存储与限制。
3. 运行确定性脚本，先生成 JSON 事实包：

   ```bash
   python <skill-root>/scripts/session_log_audit.py --provider auto --workspace <absolute-workspace> --format json --output <facts.json>
   ```

   用户给出 transcript 时追加一个或多个 `--input <path>`；指定会话时加 `--session-id <id>`（可以是根会话或子代理 id 的片段，命中子代理会自动带出其根会话）；工作区里有多个 ExpertAgent 任务并行时加 `--task-id <task>` 只保留目标会话跑的任务。
4. 检查 `sessions`、`warnings`、`expert_events` 与 `expert_tasks`。零命中时先看 `warnings` 区分是“存储根目录不存在”“有会话但工作区不匹配”还是“判根失败/为空”（见 providers.md 的零命中诊断），原样报告，不得把“未找到”写成“没有发生”。`expert_tasks` 列出的任务多于目标会话实际执行的任务时，用 `--task-id` 重跑，或在报告中注明哪些任务不属于此会话。
5. 需要纯事实日志时，可让脚本直接渲染 Markdown；需要流程审查时，由当前 Agent 基于 JSON 事实包和指定规则生成最终报告。
6. 写完后验证文件存在、必需章节齐全、事实编号能追溯到 `source_ref`。

## 报告结构

保持用户偏好的叙事格式，至少包含：

```markdown
# 会话日志审查

## 范围与数据源
## Agent 调用关系

### 用户调用 1
- <用户实际请求>

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

- “发生了什么”引用 session/message/call/event 的编号或源路径。
- “哪里有问题”引用对应事实及被违反的规则条款。
- 无法读取、参数加密、日志缺失均写成限制，不补写缺失对话。

## Agent 编排审查

只有用户要求审查时才评判。重点检查：

- 主会话是否把整个任务交给领衔，还是逐个问题直接派同事。
- 同一问题是否在用户、主会话和多个专家之间重复流转。
- `auto/assist/strict` 等模式的实际人工触点是否符合其承诺。
- “以后由某人提供”是否被错误登记为问题已经解决。
- 文档完成、实施输入齐备、代码完成和上线批准是否被混成一个“完成”。
- 评审、返修、复审是否有真实调用与结果，而非模型自述。

不要因为看到多个 Agent 就判定有问题；阶段门独立 reviewer、写审分离和失败返修通常是正当调用。

## 隐私与真实性

- 默认只保留用户可见的 `user`/`assistant` 文本和编排元数据。
- 排除 system/developer 指令、模型推理、tool result、技能全文、环境块及附件正文。
- 对疑似 token、password、secret、API key 和 Bearer 值进行脱敏。
- 不运行 `agent --resume`、不恢复旧会话、不修改原始 session。
- 不把 IDE/CIL 零命中当作用户未使用该工具的证据。
- 脚本只允许写用户明确指定的输出文件。

## 跨 CLI 边界

Codex、Claude Code 与 Cursor agent transcript 有内置适配。Cursor 只覆盖 `~/.cursor/projects/<项目>/agent-transcripts/`，按项目目录名与工作区路径的 slug 匹配，用户消息只保留 `<user_query>` 内文；IDE sidebar 私有存储不解析。其他 CLI 使用 `generic` 加显式导出文件；不得声称支持未验证的私有数据库格式。新 provider 应作为独立解析器加入脚本，并用脱敏 fixture 验证后再列为内置支持。

本目录是工具中立真源。Codex/Claude/Cursor 可把该目录加入各自 Skill 搜索路径或建立目录链接；不要复制并分别维护多份 `SKILL.md`。不支持 Skills 的 CLI 可直接读取本文件并运行同一脚本。
