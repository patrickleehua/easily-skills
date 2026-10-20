# 设计来源与适用边界

编写日期：2026-10-20，Asia/Singapore。下列资料解释设计依据，不是执行前必须联网读取的依赖，也不自动授权资料中的命令或副作用。

## 公开实现

1. [Anthropic：Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)，2025-11-26。结构化文字功能步骤、限制改写验收内容、真实浏览器端到端验证、逐功能推进；属于公开实验，非通用效果保证。本技能细分未验、受阻与失败，不直接沿用二值 passes 表示全部状态。
2. [Anthropic：Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)，2026-03-24。先明确可验证完成标准，再由评估角色操作产品并反馈；作者同时报告浅测、错误放行、成本与残留缺陷。本技能保留判据和证据，不强制多 Agent 或完整架构。
3. [Playwright Test Agents](https://playwright.dev/docs/test-agents)。Markdown 测试计划与脚本生成、运行修复分离。启发文字资产与执行资产分层；本技能不依赖 Playwright，也不把自动修复或跳过测试视为产品通过。
4. [Cucumber Introduction](https://cucumber.io/docs/) 与 [Gherkin Reference](https://cucumber.io/docs/gherkin/reference/)。通过场景描述前置、事件和预期，执行层承接动作；本技能借用表达方式，不要求 Gherkin 格式或步骤代码。

## 本技能的建议与限制

文字场景是业务协作和验收依据，不是“AI 已读所以不会出错”的保证。文字先行、SDD、TDD 和界面验收各有作用，可组合而非等同。按风险分配验证和永久资产，不设业务／测试代码比例。

规范和工具文档说明公开设计，不能单独证明实际项目的检出率、稳定性、成本优势或跨平台兼容。本包创建后的结构校验与案例走查也不替代在具体宿主、账号、服务和设备上的真实试用。
