# 标准组件目录

HTML 报告由组件积木拼成。每个组件有唯一名字，在 JSON 的 `blocks` 数组里写 `{"type": "<名字>", ...}`，或在 Markdown 里写一个以组件名为语言的代码块（块内为 JSON）。两种写法渲染结果一致。

- **完整可运行示例**：`assets/examples/component-gallery.json`（全部 38 个组件各用至少一次），渲染结果见 `assets/previews/components.html`。
- **命令行速查**：`python scripts/render_report.py --list-components`。
- **校验**：`python scripts/render_report.py 报告.json --check`，出错会给出完整路径，如 `sections[2].blocks[0].columns[1][0]（bar）：data 必须是 1–12 项的数组`。

## 通用约定

| 约定 | 说明 |
| --- | --- |
| 公共字段 | 所有组件都可写 `title`（组件标题）、`note`（一句说明）、`source`（来源）、`id`（锚点，字母开头） |
| 必须写来源 | 全部图表和 `scorecard` 必须写 `source`；`kpis` 每项写 `source` 或在组件上统一写 |
| 语气色 `tone` | `accent` 结论/下一步 · `good` 达成/进展 · `warn` 需关注 · `risk` 阻塞/风险 · `info` 说明 · `muted` 未开始/已归档。一义一色，全报告一致 |
| 状态 `status` | `done` 已完成 · `active` 进行中 · `planned` 计划 · `risk` 需协调 · `blocked` 阻塞 · `delayed` 延期 · `open` 待处理 · `cancelled` 已取消 · `na` 不适用；也接受中文 |
| 等级 `level` | `high` / `medium` / `low`，或 高 / 中 / 低 |
| 文本 | 所有文本支持行内 Markdown：`**粗体**`、`==高亮==`、`` `代码` ``；标 md 的字段支持整段 Markdown |
| Markdown 简写 | 代码块内容是数组时，等同于 `{"items": [...]}`；语言写 `chart` 或 `component` 时数组表示多个组件 |
| 分栏 | 任意组件都能放进 `columns` 并排；图表放两栏时字号自动放大 |

## 一、结论与强调

| 组件 | 用途 | 必填 | 可选 |
| --- | --- | --- | --- |
| `summary` | 首屏核心结论条 | `text`(md) | `label` |
| `highlights` | 2–4 条语气色块：进展 / 阻塞 / 下一步 | `items[].text` | `items[].label` `items[].tone` |
| `callout` | 跳出正文的提示框 | `text`(md) | `tone`（默认 info）`label` |
| `markdown` | 富文本正文 | `text`(md) | — |
| `glossary` | 术语表 | `items[].term` `items[].desc` | — |
| `checklist` | 检查清单，自动统计完成数 | `items[].text` | `items[].state`：done / open / blocked / na，`items[].note` |

顶层字段 `summary` / `highlights` 会自动渲染到首屏，不必再写进 `blocks`。

## 二、指标与数据

| 组件 | 用途 | 必填 | 可选 |
| --- | --- | --- | --- |
| `kpis` | 指标卡 | `items[].label` `items[].value` 来源 | `unit` `note` `delta`（原文已有的变化说明）`target` `tone` |
| `scorecard` | 目标达成表，自动算达成率并按判据着色 | `source` `items[].label/target/actual` | `unit` `note` `lower_is_better` `thresholds`（默认 good 100 / warn 90） |
| `table` | 数据表 | `columns` `rows` | 列 `kind`：text / number / status / progress / tag / level / markdown；行 `_tone` 整行着色；`caption` `compact` |
| `evidence` | 证据台账：来源 → 证明了什么 → 边界 | `items[].source/proves` | `boundary`；`kind`：observed 已核查 / inferred 推断 / proposed 建议 / unknown 待确认 |

```json
{"type": "table", "columns": [{"key": "m", "label": "模块"}, {"key": "p", "label": "进度", "kind": "progress"}, {"key": "s", "label": "状态", "kind": "status"}],
 "rows": [{"m": "支付", "p": 80, "s": "active"}, {"m": "对账", "p": 35, "s": "blocked", "_tone": "risk"}]}
```

`columns` 也可以直接写字符串数组，`rows` 写二维数组。

## 三、图表（全部必须写 `source`）

| 组件 | 回答什么问题 | 数据写法 |
| --- | --- | --- |
| `bar` | 类别之间谁多谁少 | `data[{label, value}]`；分组：`x` + `series[{name, points}]` |
| `column` | 各周期的量 | 同上，分组柱适合“计划 vs 实际” |
| `line` | 指标怎么变化 | `x` + `series`（1–4 条），纵轴自动取整 |
| `donut` | 由哪几部分构成（2–6 项） | `data`；`center` 为中心文字 |
| `stacked` | 一个总量的状态构成 | `data`（2–6 项） |
| `progress` | 多项任务各完成多少 | `data[{label, value 0–100, note}]` |
| `funnel` | 阶段转化 | `data` 按阶段顺序，右侧自动算相对上一层转化率 |
| `gauge` | 1–6 个整体完成度 | `items[{label, value 0–100, note}]` |
| `waterfall` | 变化由哪些增减构成 | `start{label, value}` + `data`（正负数）+ `end_label` |
| `heatmap` | 两个维度交叉的强度 | `x` 列名 + `y` 行名 + `values` 二维数组（`null` 为无数据） |

公共可选：`unit`、`max`（固定上限）、`data[].color`（语义色名）、`data[].note`。选图规则见 `html-visualization.md` 的“图表红线”。

## 四、管理与决策

| 组件 | 用途 | 必填 | 可选 |
| --- | --- | --- | --- |
| `rag` | 红黄绿状态板 | `criteria`（每种已用颜色的判据）`items[].name/status` | `summary` `owner` `due` `progress` |
| `risks` | 风险清单 | `items[].title` | `level` `impact`（缺省显示“待补充”）`mitigation` `support` `owner` `due` `status` |
| `actions` | 行动项 / 下期计划，空列自动隐藏 | `items[].task` | `priority`（P0–P3）`owner` `due` `acceptance` `status` |
| `decisions` | 决策记录 | `items[].decision` | `status`：approved / proposed / pending / rejected；`reason` `alternatives` `condition` `owner` `date` |
| `items` | 事项列表（旧版日报格式） | `items[].title` | `detail`(md) `status` `tags` `progress`（须有 `source`）`impact` `support` `highlight` |

```json
{"type": "rag", "criteria": {"green": "里程碑按期", "yellow": "延期 ≤2 天", "red": "延期 >2 天或 P0 阻塞"},
 "items": [{"name": "支付改造", "status": "green", "summary": "回归 80%", "owner": "张三", "progress": 80}]}
```

## 五、进度与流程

| 组件 | 用途 | 必填 | 可选 |
| --- | --- | --- | --- |
| `timeline` | 里程碑 / 事件时间线 | `items[].date/title` | `desc` `status`；`layout`：vertical / horizontal |
| `gantt` | 计划 vs 实际排期 | `items[].task/start/end`（YYYY-MM-DD） | `actual_start` `actual_end` `progress` `status` `group` `owner` `milestone`；组件级 `start` `end` `today` |
| `steps` | 流程 / 阶段门进行到哪一步（2–10 步） | `items[].title` | `desc` `status` |
| `kanban` | 按状态分列的任务池（2–6 列） | `columns[].title` `columns[].cards` | 列 `tone`；卡片可写字符串或 `{title, meta, tags}` |

复杂流程图、泳道图、架构图不在本组件库内：用 `archify` skill 生成独立图，或在飞书文档里用画板（`lark-whiteboard`）。

## 六、分析框架

| 组件 | 用途 | 必填 | 可选 |
| --- | --- | --- | --- |
| `comparison` | 方案对比矩阵，标推荐项 | `options`（2–6）`criteria[].label/values` | `options[].recommended/tag`；单元格可写 `{text, tone}`；`criteria[].weight`；`verdict`(md) |
| `quadrant` | 四象限定位（重要-紧急、价值-投入） | `x{label}` `y{label}` `items[].label/x/y`（0–10） | `x/y.low/high` `quadrants{tl,tr,bl,br}` `items[].tone` |
| `risk-matrix` | 可能性 × 影响热力格 | `items[].label/likelihood/impact` | `scale`：5（默认）或 3 |
| `fishbone` | 鱼骨图根因分析（2–6 类，每类 ≤5 条，总数 ≤24） | `effect` `categories[].name/causes` | — 自动附“文字版” |
| `pyramid` | 结论 → 论据 → 事实 / 目标 → 策略 → 动作 | `levels[].title`（2–6，自顶向下） | `desc` `tone` |
| `grid` | 并列框架：SWOT、KISS、4Ls、优劣对照 | `cells[].title` + `items` 或 `text` | `cells[].tone`；`columns` 1–4 |

框架只在能改变判断时使用，不为“显得专业”套 SWOT。

## 七、版式与素材

| 组件 | 用途 | 必填 | 可选 |
| --- | --- | --- | --- |
| `columns` | 并排放任意组件（可嵌套） | `columns`：2–4 个组件数组 | `ratio`：如 `2:1`、`1:1:1` |
| `image` | 截图 / 照片 / 原型图 | `alt` + `path`（本地文件，自动内嵌）或 `src`（仅 data URI） | `caption`；`width`：full / wide / half / third |
| `pagebreak` | 打印时在此换页 | — | — |

图片只允许本地文件或内嵌数据，禁止外链，保证离线可看、可转发；单张不超过 5MB。

## 文档级字段

| 字段 | 说明 |
| --- | --- |
| `title` | 必填 |
| `subtitle` `date` `report_type` `footer` | 报告头与页脚 |
| `genre` `industry` `audience` `author` | 报告身份，显示为标题下的小标签 |
| `summary` `highlights` `metrics` `charts` | 首屏：结论 → 重点 → 指标 → 图表 |
| `blocks` | 首屏之后、章节之前的自由组件 |
| `sections[]` | `title` + `summary`（一句话小结）+ `lead`（事实导语，md）+ `body`（md）+ `blocks` |
| `layout` | `cards`（双栏卡片）/ `flow`（单栏长文）；有 `body` 或 `blocks` 时默认 flow |
| `numbering` | `auto`（默认，标题已编号则不加序号）/ `cn`（自动加 一、二、）/ `none` |
| `toc` | 是否生成导航，flow 且 ≥3 章时默认开 |
| `indent` | 正文首行缩进两字（公文、正式归档常用） |
| `brand` | 品牌色：`{"accent": "#1F6FEB", "palette": ["#..", ".."], "ink": "#.."}` |
| `demo` | 示例必须为 true，首屏显示虚构提示 |
| `source_text` | 原文全文，折叠在页尾，不打印 |

## 新增组件

在 `scripts/components/` 对应模块里用 `@component(name, group=..., summary=..., source=是否必须带来源)` 注册一个函数，函数接收 `(block, ctx)`、返回 HTML 字符串，校验失败抛 `ValueError`。样式写进 `assets/html/components.css`，只用主题变量。然后在 `component-gallery.json` 加一个用例、在本目录登记，并运行 `python -m unittest discover -s scripts`（组件库测试会检查每个注册组件都出现在画廊里）。
