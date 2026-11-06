# 火山引擎工具调研

2026-11-06 检索 skills.sh、Skills CLI、GitHub 和官方文档。安装数、星标为当时快照，不作为功能正确性证明。

| 项目 | 类型 / 来源 | 核对结果 |
| --- | --- | --- |
| [volcengine/volcengine-agent-toolkit](https://github.com/volcengine/volcengine-agent-toolkit) | 官方 skills，26 stars | 云资源、CLI、文档检索等；已查看的技能目录未见可直接运行的 TTS skill |
| [volcengine/mcp-server](https://github.com/volcengine/mcp-server) | 官方 MCP，333 stars，MIT | 通用云服务工具；已查看的文件树未发现 TTS/speech/voice 实现 |
| [calesthio/OpenMontage doubao-tts](https://github.com/calesthio/OpenMontage/tree/main/.agents/skills/doubao-tts) | 社区 skill，约 1.2K installs；仓库约 77.2K stars，AGPL-3.0 | 具备新版 Key 和 2.0 接入，但 provider 依赖 tools.base_tool、工具注册与其他 OpenMontage 模块；不是可单独复制运行的 CLI |
| [geekjourneyx/doubao-skills](https://github.com/geekjourneyx/doubao-skills/tree/main/skills/doubao-tts) | 社区，1 install / 1 star | 脚本向 V3 endpoint 发送旧版 app/audio/request 和 Authorization 请求，且把流响应直接当音频保存，与当前 V3 JSON/base64 契约不符，不原样采用 |
| [cinience/volcengine-skills](https://github.com/cinience/volcengine-skills) | 社区，TTS skill 1 install / 仓库 1 star | 检索到的 TTS 入口主要为操作提示，未提供本次所需独立可运行接入 |
| skills.volces.com doubao-tts-http | Skills CLI 索引，79 installs | 索引有条目，但访问其公开路径及 well-known 索引返回 NotFound，未取得可核对安装包，不能认定当前可用 |

结论：相关项目存在；本仓库需要的独立、当前 V3 协议、可在 Windows 直接调用的 TTS 工具仍有缺口，因此依据官方 HTTP 文档实现本技能。没有安装整套云工具或复制其他项目运行框架。需要更广的云资源管理时优先考虑官方 toolkit；已使用 OpenMontage 时可直接评估其现成 provider。
