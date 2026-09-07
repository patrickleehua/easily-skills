# 日报转可视化 HTML

生成本地报告文件，默认不发布网站。三套模板采用克制配色、清晰层次与中文系统字体；每份报告内嵌 CSS，无 CDN、字体下载、第三方脚本或构建依赖。模板切换不改变事实、行业措辞和条目顺序，也不按视觉风格重写报告。

## 模板选择

| 模板参数 | 视觉与版式 | 推荐场景 |
| --- | --- | --- |
| `executive`（默认） | 商务蓝；白底、结论条、指标卡、双栏事项 | 日常管理汇报、客户进展 |
| `editorial` | 暖白简报；衬线标题、宽留白、单栏分节 | 正式归档、咨询与文字较多的日报 |
| `briefing` | 深色侧栏；左侧报告信息、右侧结论与工作分区 | 项目例会、研发与运营进展 |

首次选模板可打开 `assets/previews/index.html`。此处使用同一份**明确标注为虚构**的示例数据；切换可比较真实版式。模板真源为 `assets/html/report.html`、`base.css` 及三个主题 CSS；预览页是脚本生成的产物，不直接维护。

## 两种转换路径

### 已有 Markdown：直接排版

从技能目录执行（其他工作目录请改用脚本和输入的实际路径）：

```powershell
python scripts/render_report.py "日报.md" --theme executive --output "output/日报.html"
python scripts/render_report.py "日报.md" --all --output "output/日报模板"
```

支持 UTF-8 的 `.md`、`.markdown`、`.txt`。识别标题、段落与列表，保持正文顺序；未知标题照常呈现，不会只保留预设的四个分区。表格、链接、强调和代码等复杂 Markdown 保留为可读原文，**不是完整 Markdown 富文本解析器**。页尾提供原文展开以便核对。若需表格或复杂内容进一步视觉化，由 agent 按下述结构整理并检查原文覆盖情况。

直接转换不从标题猜作者、日期，不推断状态、完成率或指标，不把列表条数当作产出。用户需要摘要或指标卡时，采用结构化路径。

### 结构化呈现：提取后渲染

由 agent 根据日报生成 UTF-8 JSON；schema 见下表和 `assets/examples/daily-report.json`。与原文逐项核对后执行：

```powershell
python scripts/render_report.py "output/日报.json" --theme editorial --output "output/日报.html"
python scripts/render_report.py "output/日报.json" --all --output "output/日报模板"
```

`--all` 生成 `executive.html`、`editorial.html`、`briefing.html` 和 `index.html`。预览入口依赖同目录的三个报告；每个报告本身可独立发送、离线打开。输出已存在时默认停止，确认需要替换自己的生成文件后可加 `--force`。

| 字段 | 类型 / 要求 | 展示含义 |
| --- | --- | --- |
| `title` | 非空字符串，必填 | 报告标题 |
| `subtitle`、`date`、`report_type`、`footer` | 可选字符串 | 作者/部门、日期、报告类型、页脚；未知不猜 |
| `summary` | 可选字符串 | 一至两句核心结论；无材料则省略 |
| `demo` | 可选布尔值，默认 false | 示例必须为 true，首屏显示虚构提示 |
| `metrics` | 可选数组 | 指标卡，无真实数据时不传或传空数组 |
| `metrics[]` | `label`、`value`、`source` 为非空字符串；`unit`、`note` 可选 | 数值沿用原文精度、单位和统计范围；source 指向用户材料或日志位置 |
| `sections` | 可选数组 | 原报告各章节，按原文或已确认的行业结构排序 |
| `sections[]` | `title` 非空字符串，`items` 数组 | 常见今日完成/进行中/明日计划/风险；也可用任意行业章节 |
| `items[]` | `title` 非空字符串；`detail` 可选字符串 | 具体事项与结果，保留未完成原因和计划验收条件 |
| `items[].status` | 可选枚举 `done / active / risk / planned` | 仅在原文有对应证据时设置状态标签 |
| `items[].progress` | 可选 0–100 的有限数字，必须同时有非空 `source` | 展示进度条；缺数据就省略，不从措辞猜百分比 |
| `items[].source` | 可选字符串 | 原文位置、日志条目或数据来源，不渲染为可执行链接 |
| `items[].impact`、`support` | 可选字符串 | 风险影响与所需支持；未知写待补充，不写成无风险 |
| `source_text` | 可选字符串 | 完整原文，建议转换已有日报时保留，折叠展示，不打印 |

所有内容字段按纯文本转义，用户素材中的 HTML/脚本不会执行。渲染器校验类型与来源字段是否存在；来源的真实性、结论是否忠于原文由 agent 核对。不要把示例 JSON 的事实、部门、日期或数据带入用户日报。不要绘制原材料不支持的趋势图、环比或占比；也不要为了填满模板而补条目。

## 交付检查

1. 逐项核对原日报的成果、未完成原因、计划、风险和来源；没有数据时确认指标区与进度条省略。已有明确结论放入首屏摘要。
2. 用浏览器打开生成文件，检查桌面与约 390px 窄屏，无横向溢出、遮挡或内容丢失；长标题、长链接按行折断。
3. 查看打印预览：A4 白底、工具栏隐藏、内容分页可读；长报告允许多页，不压缩到一页。浏览器打印可选择存为 PDF。原文折叠区不参与打印，正式正文应已包含全部必要信息。
4. 交付 HTML 文件链接，并说明采用哪个模板；生成多套时同时交付 `index.html` 入口。报告会把提供的素材写入 HTML，对外场景应先按原技能原则脱敏。

修改模板后重新生成演示：

```powershell
python scripts/render_report.py assets/examples/daily-report.json --all --output assets/previews --force
```
