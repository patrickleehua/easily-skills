# 场景模板

按场景只读取对应小节。花括号是生成阶段变量，最终文案中必须替换或删除。省略没有真实内容的可选小节，不制造“无”“暂无”等空分类。

目录：

- [Commit / squash](#commit--squash)
- [MG / merge / PR / MR](#mg--merge--pr--mr)
- [Tag annotation](#tag-annotation)
- [Release / changelog](#release--changelog)
- [审查模式](#审查模式)

## Commit / squash

格式：`type(scope): summary`；破坏性变更采用 `type(scope)!: summary`。

- 采用仓库现有 Conventional Commit 类型、scope 和语言约定；若仓库另有格式，以已有规范为准。
- 默认标题尽量控制在 72 个字符内，精确表述优先；仓库有明确长度门禁时遵守门禁。
- 单一小变更只需标题。仅在原因、行为、兼容性或验证需要说明时添加正文。
- 多个无关主题应指出并建议适当拆分；不要未经请求重新暂存或重组提交。
- 对 squash 使用整个最终 patch 的主旨，不照搬最后一个中间 commit。

```text
{type}({scope}): {动作与具体行为变化}

{必要的原因、前后行为和实际影响}

{可选：实际验证命令及结果}

{可选：真实 issue/PR trailer}
```

破坏性变更的格式示例（虚构场景，不能当作当前仓库事实）：

```text
fix(api)!: 将未观测字段返回为 null

此前将未观测值填充为空数组，客户端无法区分未观测与已观测为空。
现在保留这一区别，消费者需要显式处理 null。

BREAKING CHANGE: observations.items 可能返回 null；只接受数组的消费者需更新解析逻辑。
```

## MG / merge / PR / MR

先解析 mg 的真实定义，再选择它实际涉及的模板。项目没有定义时，不把本 skill 变成同名命令。

PR/MR 标题采用仓库约定；通常可使用 `type(scope): {最终效果}`。普通 merge commit 保留项目现有标题习惯，如 `Merge branch 'SOURCE' into TARGET`，将规范说明放入正文；squash 则使用 commit 模板。

```markdown
## 摘要
{触发问题或需求，以及合并后的具体行为}

## 变更
- {scope}: {最终变化及必要影响}
- {scope}: {另一个独立变化}

## 兼容性与迁移
{有实际兼容性影响时才保留；写清旧行为、新行为及消费者动作}

## 验证
- {真实执行的命令/CI 检查与结果，或明确未执行及原因}

## 关联
{已确认的 issue/PR/设计文档；没有来源时删除}
```

只有变化较多时才在“变更”下按 Features、Bug Fixes 等继续分类。合并冲突的实质解决、残留限制或操作注意事项有证据时才添加，不为模板填满段落。

对于 fast-forward 合并，不凭空生成 merge commit；需要说明时交付 PR/MR 或变更摘要。多源集成或跨版本合并写清实际范围，不暗示该结果已经发布。

## Tag annotation

保留仓库 tag 命名规则。目标 commit、版本号、组件和 annotation 分别核实；用户只要求文案时不创建 tag。

```text
{component}: v{version}

{一至两句版本主要变化}

Breaking changes:
- {仅在存在 breaking 时保留；具体变化及迁移要求}

Changes:
- {scope}: {主要独立变化}
- {scope}: {另一变化}

{可选：已存在且核实的 release 或比较链接}
```

使用适合命令行阅读的文本，通常一屏左右；关键兼容性说明不能为了缩短而省略。无组件前缀时使用项目既有版本标题。不将 release 的所有实现条目塞入短 annotation。已要求 lightweight tag 时保持轻量标签，将说明交付为独立文案，不自行改成 annotated tag。

## Release / changelog

默认参考 rea 的“版本身份 → breaking → 分类条目 → 真实来源”结构。标题与正文分别提供给平台时，不在正文重复平台标题；项目现有 changelog 结构需要版本节时保留版本节。

```markdown
## {version} ({已确认的发布日期；未知时省略日期及括号})

### ⚠ BREAKING CHANGES
- {scope}: {旧行为 → 新行为；受影响对象；必须采取的迁移动作} ({来源})

### Features
- {scope}: {新增能力及使用者效果} ({来源})

### Bug Fixes
- {scope}: {触发条件下修复后的行为} ({来源})

### Performance Improvements
- {scope}: {性能相关变化；数值仅在有测量记录时提供} ({来源})

### Code Refactoring
- {scope}: {具体内部结构调整及必要原因} ({来源})

### Documentation
- {scope}: {文档新增或修正的内容} ({来源})

### Tests
- {scope}: {独立测试体系或覆盖变化} ({来源})

### Continuous Integration
- {scope}: {CI 检查、选择或执行方式变化} ({来源})

### Build System
- {scope}: {构建、依赖或打包变化} ({来源})

### Miscellaneous
- {scope}: {其余有价值的维护变化} ({来源})

{可选：已核实的完整比较链接}
```

生成时仅保留非空分类，按上述顺序排列。来源默认用可点击的短 commit hash 和可用的 PR 编号；正文不采用聊天专用 citation 标记。没有已核实来源时删除来源括号，并在草稿外说明依据限制。

breaking 复杂时先写简短条目，再在同节补充迁移段落或已核实指南链接。不要把 breaking 包装为“增强稳定性”。只有有独立说明价值的行为变化才单列，完整性以独立最终效果计，不以 commit 数量计。

更新 changelog 时保持既有历史与排序，只编辑请求的版本/Unreleased 段；已授权发布时按项目工具规则移动条目，不重写无关版本。复用自动生成结果后仍核对 breaking、净变化、重复项、组件范围及迁移说明。

## 审查模式

```text
{通过；或需要修正的具体事实/范围/格式问题及依据}

修订稿：
{按对应场景提供可直接采用的完整文本}

{正文外的证据缺口；不存在时省略}
```

审查以范围、事实、兼容性、证据和可读性为主。不要单纯为了换一种措辞改写已经准确的说明。
