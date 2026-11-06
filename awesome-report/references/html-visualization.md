# 可视化 HTML 报告

生成本地单文件 HTML，离线可开、可打印、可存 PDF，默认不发布网站。内嵌 CSS 与内联 SVG，无 CDN、外部字体、第三方脚本或构建依赖。**Markdown 产物不放图表**；图表、指标卡、重点色块只在 HTML 中出现。

组件字段与用法见 `components.md`；写作与证据规则见 `writing-core.md`；体裁对应的组件配方见 `genres/` 下各文件末尾。

## 模板选择

| 主题 | 视觉与版式 | 推荐场景 |
| --- | --- | --- |
| `executive`（默认） | 商务蓝；白底、结论条、指标卡 | 日常管理汇报、客户进展、技术验证 |
| `editorial` | 暖白；衬线标题、宽留白、章节标题在左 | 审查报告、复盘、正式归档、文字较多的报告 |
| `briefing` | 深色侧栏；左侧报告信息，右侧内容 | 项目例会、月报、会议展示 |

品牌色用文档字段 `brand` 覆盖（`accent` / `palette` / `ink`），三套主题都生效。预览入口：`assets/previews/index.html`（组件库 + 5 类体裁示例 + 日报三主题）。

## 两种输入

### 路径 A：Markdown 直接排版

一级标题作报告标题，二级标题切章节，正文按安全 Markdown 子集渲染（表格、列表、任务清单、引用、提示框、代码、行内高亮）。**任何组件都能用代码块引用**，块内写 JSON：

    ```risks
    [{"title": "验收账号未开通", "level": "high", "impact": "验收顺延 1 天", "support": "环境负责人 9/18 前开通"}]
    ```

    ```chart
    {"type": "bar", "title": "各端工作包", "unit": "个", "source": "工作包清单",
     "data": [{"label": "服务端", "value": 9}, {"label": "客户端", "value": 4}]}
    ```

提示框写法：`> [!风险]`、`> [!重点]`、`> [!建议]`、`> [!注意]`、`> [!说明]`、`> [!结论]`，也支持 GitHub 的 `[!NOTE]` `[!TIP]` `[!IMPORTANT]` `[!WARNING]` `[!CAUTION]`。`md` / `markdown` / `text` 代码块、以及内容不是 JSON 的代码块，始终按普通代码显示。

直接转换不猜作者、日期，不推断状态、完成率或指标。

### 路径 B：结构化 JSON（推荐用于正式汇报）

由 agent 从素材提取成 JSON：首屏（`summary` / `highlights` / `metrics` / `charts`）+ 章节（`sections[].lead` + `blocks`）。字段见 `components.md` 末尾“文档级字段”。示例都在 `assets/examples/`：

| 示例 | 体裁 | 用到的主要组件 |
| --- | --- | --- |
| `daily-report.json` / `.md` | 日报 | items、stacked、progress、actions |
| `weekly-status.json` | 研发周报 | rag、table、分组 column、gantt、risks、actions |
| `audit-review.json` | 审查报告 | decisions、evidence、table、donut、checklist |
| `tech-validation.json` | 技术验证 | comparison、line、bar、steps、callout |
| `monthly-manufacturing.json` | 制造月报 | scorecard、heatmap、fishbone、8D table、brand |
| `retrospective.json` | 复盘 | scorecard、timeline、waterfall、evidence、grid |
| `component-gallery.json` | 组件库 | 全部 38 个组件 |

## 命令

从技能目录执行（其他目录改用实际路径）：

```powershell
python scripts/render_report.py "报告.json" --check                              # 只校验，报错带完整路径
python scripts/render_report.py "报告.json" --theme editorial --output "out/报告.html"
python scripts/render_report.py "报告.md" --all --output "out/报告模板"            # 三套主题 + index.html
python scripts/render_report.py --list-components                                # 组件速查
python scripts/build_previews.py                                                 # 重建 assets/previews
python -m unittest discover -s scripts                                           # 自检
```

输出已存在时默认停止，确认替换自己的生成文件再加 `--force`。图片 `path` 相对输入文件所在目录解析。

## 选组件：按内容动态生成

不套固定模板。拿到素材后按这个顺序决定用什么：

1. **首屏三件套**：一句结论（`summary`）+ 2–4 条重点色块（`highlights`：进展 / 阻塞 / 下一步 / 需要的决策）+ 有来源的关键数字（`metrics`）。没有真实数字就不放指标卡。
2. **按体裁取配方**：命中体裁文件末尾的“HTML 组件配方”给出每一章的首选组件。
3. **按内容形态微调**：并列对比 → `table` / `comparison`；数量关系 → 图表；时间 → `timeline` / `gantt`；状态 → `rag` / `status` 列；风险 → `risks`；决定 → `decisions`；下一步 → `actions`；证据边界 → `evidence`。
4. **按行业补指标图**：行业文件末尾的“HTML 组件映射”。
5. **排版**：相关的两个组件用 `columns` 并排（如表格 + 图表 `3:2`）；长报告设 `"numbering": "cn"` 并保留导航。

## 图表红线

1. **只画素材里有的数**。不补周期、不估占比、不画趋势线；`source` 不能空，也不能写“推测”。
2. 一张图只回答一个问题；一份报告一般 2–6 张，章节内最多 1–2 张。少于 3 个数据点优先用指标卡或表格。
3. 图旁用一句话写“说明了什么”，不复述数字；图不能是唯一证据。
4. 数量级悬殊或单位不同的指标不放同一张图。
5. 状态色有判据：`rag` 必须写 `criteria`，`scorecard` 自动显示判据。

## 重点高亮

- 语气色一义一色：`good` 进展 / 达成，`warn` 需关注，`risk` 阻塞 / 风险，`accent` 结论 / 下一步 / 决策，`info` 说明，`muted` 未开始 / 已归档。
- 行内 `==关键结论==` 标记色底、`**关键名词**` 加粗；一段里高亮不超过一处。
- 需要跳出正文的风险、决策建议、口径说明用 `callout`。
- 表格里的阻塞行用 `"_tone": "risk"` 整行着色，而不是整张表上色。

## 控制篇幅

HTML 是汇报版，不是原文的网页化：

1. 每章事实导语 2 句，正文不超过 3 段、单段不超过 120 字；更细的内容进表格、列表或折叠原文。
2. 能用表格表达的并列关系不写成排比段落；能用图表表达的数量关系不写成数字罗列。
3. 转换已有长报告时做**结构化压缩**：保留事实、结论、风险、来源，删重复铺陈和过渡句；完整原文放 `source_text` 折叠区。
4. 列表条目一行讲清一件事。

## 交付检查

1. 逐项核对原材料的成果、未完成原因、计划、风险和来源；无数据时确认指标卡、图表、进度条都已省略。
2. `--check` 通过；浏览器打开检查桌面与约 390px 窄屏，无横向溢出、遮挡或内容丢失。
3. 打印预览：A4 白底、工具栏与导航隐藏、色块和图表正常着色、分页可读。原文折叠区不打印。
4. 每张图有 `source`，数值与正文一致，无素材外推算。
5. 交付 HTML 文件路径并说明所用主题；生成多套时附 `index.html`。对外场景先脱敏。
