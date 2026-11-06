<div align="center">

# 🧩 Easily Skills

**开箱即用的 Agent Skills 合集 —— 研发、写作、AIGC、音视频，覆盖真实工作场景。**

放进一个文件夹，Agent 就多会一门手艺。

<!-- BEGIN:badges -->
<!-- 本区块由 scripts/sync_readme.py 自动生成，请勿手改 -->
![技能](https://img.shields.io/badge/%E6%8A%80%E8%83%BD-23-6366f1?style=flat-square) ![分类](https://img.shields.io/badge/%E5%88%86%E7%B1%BB-7-0ea5e9?style=flat-square)
<!-- END:badges -->
![Claude Code](https://img.shields.io/badge/Claude_Code-ready-d97757?style=flat-square)
![Codex](https://img.shields.io/badge/Codex-ready-10a37f?style=flat-square)
![Cursor](https://img.shields.io/badge/Cursor-ready-000000?style=flat-square)

[English](./README.md) · **简体中文**

</div>

---

## ✨ 为什么选它

- **来自实战，不是玩具** —— 每个技能都源于日常工作：写代码、写报告、做内容。
- **标准 `SKILL.md` 格式** —— Claude Code、Codex、Cursor 以及任何支持 Agent Skills 的工具都能直接用。
- **讲证据，不瞎编** —— 技能要求标注来源、区分假设，禁止编造事实。
- **该用脚本就用脚本** —— 标 ⚙️ 的技能自带可执行脚本，结果稳定可复现；标 📝 的是纯提示词，零配置。

## 🗂️ 分类速览

<!-- BEGIN:overview -->
<!-- 本区块由 scripts/sync_readme.py 自动生成，请勿手改 -->
| 分类 | 数量 | 技能 |
|---|:---:|---|
| 🛠️ [研发工程](#cat-engineering) | 6 | `analysis-projects` `code-test-boundaries` `extract-ui` `git-change-notes` `redesign-ui` `scenario-acceptance` |
| 🤖 [Agent 与 Skill 生态](#cat-agent) | 3 | `agent-skills-helper` `cli-session-log-audit` `openclaw-helper` |
| ✍️ [写作与报告](#cat-writing) | 3 | `awesome-report` `project-to-cv` `wechat-article-writer` |
| 🎨 [AIGC 创作](#cat-aigc) | 6 | `bailian-api-tools` `minimax-api-tools` `nano-banana-pro-prompter` `seedance-prompt-helper` `v36-api-tools` `volcengine-api-tools` |
| 🎬 [音视频工具](#cat-media) | 2 | `bili-download` `ffmpeg-tools` |
| 📚 [学习与教育](#cat-learning) | 2 | `answer-check` `notes2questions` |
| 💹 [金融交易](#cat-finance) | 1 | `hyperliquid-trading` |
<!-- END:overview -->

## 📦 技能清单

<!-- BEGIN:catalog -->
<!-- 本区块由 scripts/sync_readme.py 自动生成，请勿手改 -->
<a id="cat-engineering"></a>

### 🛠️ 研发工程

> 读懂代码、定投入、写验收、管提交 —— 覆盖研发交付全流程。

| 技能 | 简介 | 特性 |
|---|---|---|
| [**analysis-projects**](./analysis-projects/) | 深度解析代码库：架构总览、核心模块、关键流程、依赖与改进建议。 | 📝 纯提示 |
| [**code-test-boundaries**](./code-test-boundaries/) | 按契约、风险和证据决定写多少代码、做哪些测试、何时停手。 | 📝 纯提示 |
| [**extract-ui**](./extract-ui/) | 从现有代码提取界面结构、交互模式、视觉资源与业务流程，生成 UI/UX 现状规格。 | ⚙️ 脚本 |
| [**git-change-notes**](./git-change-notes/) | 统一 commit、PR、tag 与 Release Notes 写法：破坏性变更优先、可追溯。 | 📝 纯提示 |
| [**redesign-ui**](./redesign-ui/) | 基于体验现状输出 UI/UX 改版规格、视觉设计系统与原型生成提示词。 | ⚙️ 脚本 |
| [**scenario-acceptance**](./scenario-acceptance/) | 从 PRD / 需求写验收用例，并通过真实界面、接口或命令实测与回归。 | 📝 纯提示 |

<a id="cat-agent"></a>

### 🤖 Agent 与 Skill 生态

> 编写、调试、审计 Agent Skill 与 Agent 工具链本身。

| 技能 | 简介 | 特性 |
|---|---|---|
| [**agent-skills-helper**](./agent-skills-helper-skills/) | 设计、编写、调试与迁移 Agent Skill：目录结构、触发描述、脚本与工具集成。 | 📝 纯提示 |
| [**cli-session-log-audit**](./cli-session-log-audit/) | 导出 Codex、Claude Code、Cursor 等会话日志，按 Skill / SOP 审查调用链问题。 | ⚙️ 脚本 |
| [**openclaw-helper**](./openclaw-helper-skills/) | OpenClaw / ClawBot 安装、配置与故障排查，优先查本地文档。 | 📝 纯提示 |

<a id="cat-writing"></a>

### ✍️ 写作与报告

> 报告、文章、简历 —— 结论先行、事实可追溯的结构化写作。

| 技能 | 简介 | 特性 |
|---|---|---|
| [**awesome-report**](./awesome-report/) | 15 类体裁 × 14 个行业的报告生成器，输出 Markdown、可视化 HTML 或飞书文档。 | ⚙️ 脚本 |
| [**project-to-cv**](./project-to-cv/) | 读懂项目代码，生成简历项目经历、技术栈、职责与面试问答。 | 📝 纯提示 |
| [**wechat-article-writer**](./wechat-article-writer/) | 公众号文章撰写、润色与质检，融合「热点情绪」与「技术干货」两种风格。 | 📝 纯提示 |

<a id="cat-aigc"></a>

### 🎨 AIGC 创作

> 图像 / 视频提示词工程，以及语音、图像生成类模型 API 调用。

| 技能 | 简介 | 特性 |
|---|---|---|
| [**bailian-api-tools**](./bailian-api-tools/) | 百炼 Qwen 与 CosyVoice 文字转语音，生成音频及结构化执行结果。 | ⚙️ 脚本 · 🔑 需 Key |
| [**minimax-api-tools**](./minimax-api-tools/) | MiniMax 语音合成、声音克隆、音色设计与音色管理。 | ⚙️ 脚本 · 🔑 需 Key |
| [**nano-banana-pro-prompter**](./nano-banana-pro-prompter/) | 把创意需求翻译成高质量的 Nano Banana Pro 图像提示词。 | 📝 纯提示 |
| [**seedance-prompt-helper**](./seedance-helper-skills/) | Seedance 2.0 视频提示词设计、优化与诊断（T2V / I2V / R2V）。 | 📝 纯提示 |
| [**v36-api-tools**](./v36-api-tools/) | 通过 v36 API 文生图、改图（NanoBanana / GPT-Image-2）与 Whisper 语音转文字。 | ⚙️ 脚本 · 🔑 需 Key |
| [**volcengine-api-tools**](./volcengine-api-tools/) | 火山引擎豆包 Seed TTS 2.0 文字转语音，生成本地音频、用量与字幕元数据。 | ⚙️ 脚本 · 🔑 需 Key |

<a id="cat-media"></a>

### 🎬 音视频工具

> 本地音视频剪辑、转换与下载。

| 技能 | 简介 | 特性 |
|---|---|---|
| [**bili-download**](./media-download-bilibili/) | B 站视频下载、音频提取与人声分离。 | ⚙️ 脚本 |
| [**ffmpeg-tools**](./ffmpeg-tools/) | 基于 FFmpeg 的视频按时间剪切、画面裁切、调整分辨率与音频提取。 | ⚙️ 脚本 |

<a id="cat-learning"></a>

### 📚 学习与教育

> 出题、批改、错因诊断，帮助主动回忆与查漏补缺。

| 技能 | 简介 | 特性 |
|---|---|---|
| [**answer-check**](./answer-check-skills/) | 批改作业与试卷，输出正确率、错题解析与知识盲点诊断。 | 📝 纯提示 |
| [**notes2questions**](./notes2questions-skills/) | 把学习笔记变成单选、多选、判断题，附答案与解析。 | 📝 纯提示 |

<a id="cat-finance"></a>

### 💹 金融交易

> 行情查询、账户管理与交易执行。

| 技能 | 简介 | 特性 |
|---|---|---|
| [**hyperliquid-trading**](./hyperliquid-trading/) | 通过 hl CLI 查询 Hyperliquid 行情与账户，下单、调杠杆、转账与质押。 | ⚙️ 脚本 · 🔑 需 Key |
<!-- END:catalog -->

> **图例** —— ⚙️ 自带脚本 · 📝 纯提示词、免配置 · 🔑 需要 API Key（见技能目录下的 `.env.example`）

## 🚀 快速开始

**方式一：用 [`skills`](https://github.com/vercel-labs/skills) 命令行安装（推荐）**

```bash
# 交互式挑选
npx skills add patrickleehua/easily-skills

# 只装某一个
npx skills add patrickleehua/easily-skills --skill awesome-report
```

**方式二：手动复制**

```bash
git clone https://github.com/patrickleehua/easily-skills.git

# Claude Code：用户级（所有项目可用）或项目级
cp -r easily-skills/awesome-report ~/.claude/skills/
cp -r easily-skills/awesome-report .claude/skills/
```

其他 Agent 复制到各自的 skills 目录即可。装好后直接描述任务，Agent 会根据 `description` 自动选用对应技能。

**带 ⚙️ / 🔑 的技能** 需要先装 [uv](https://docs.astral.sh/uv/)，必要时配置 Key：

```bash
cd ~/.claude/skills/minimax-api-tools
cp .env.example .env   # 填入你的 Key
uv sync                # 仅当技能目录里有 pyproject.toml 时需要
```

## 🧱 技能长什么样

```text
my-skill/
├── SKILL.md        # 必需：frontmatter（name、description）+ 使用说明
├── references/     # 可选：按需加载的参考资料
├── scripts/        # 可选：可执行脚本（⚙️）
├── assets/         # 可选：模板、示例、样式
└── .env.example    # 可选：所需的 Key（🔑）
```

## 🔄 新增技能，清单自动更新

上面的清单是**自动生成**的，不用手动维护：

1. 新建一个带 `SKILL.md` 的文件夹，推送到仓库。
2. GitHub Actions 自动运行 [`scripts/sync_readme.py`](./scripts/sync_readme.py)，给新技能归类并提交更新后的 README。
3. *（可选）* 想要更准确的分类和中英文简介，在 [`catalog.yml`](./catalog.yml) 里补一条记录。

归类全靠规则，不依赖 AI：`catalog.yml` 登记 → `SKILL.md` 里的 `category` → 关键词匹配 → 「其他」。
想让 AI 帮忙整理？对 Agent 说一句「按 AGENTS.md 把新技能登记到 catalog.yml」即可。

```bash
uv run scripts/sync_readme.py          # 本地重新生成
uv run scripts/sync_readme.py --check  # 只检查不修改（CI 使用）
```

可选：开启本地钩子，每次提交前自动同步：

```bash
git config core.hooksPath .githooks
```

## 🤝 参与贡献

欢迎提 Issue 和 PR。新增技能时，`description` 要写清楚**什么时候用**和**什么时候不用**，这决定了 Agent 能不能准确触发它。

## 📄 许可证

每个技能各自声明许可证，详见其目录下的 `LICENSE.txt`。
