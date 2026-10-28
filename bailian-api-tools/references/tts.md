# TTS 接口与来源

核对日期：2026-10-28。模型与音色清单会变化，`models` 是随包维护的已支持列表，
不代表当前账户已开通全部模型。区域、音色与高级指令以官方文档为准。

## 接口路由

| 模型族 | HTTP 路径（`/api/v1` 之后） | 地域 | 本工具的音色默认值 |
|---|---|---|---|
| `qwen3-tts-flash` | `/services/aigc/multimodal-generation/generation` | 北京、新加坡 | `Cherry` |
| `qwen-audio-3.0-tts-*`、`qwen-audio-3.1-tts-*` | `/services/audio/tts/SpeechSynthesizer` | 北京、新加坡 | 须指定 `--voice` |
| `cosyvoice-v2`、`cosyvoice-v3-*`、`cosyvoice-v3.5-*` | `/services/audio/tts/SpeechSynthesizer` | 北京 | 须指定 `--voice` |

带业务空间的主机：`{workspace}.{region}.maas.aliyuncs.com`。
Qwen3 未设置 workspace 时使用官方共享域名：北京 `dashscope.aliyuncs.com`、
新加坡 `dashscope-intl.aliyuncs.com`。密钥、业务空间和地域必须匹配，不自动换地域。

请求为 `{"model":"...","input":{"text":"...","voice":"..."}}`；
Qwen3 添加 `language_type`，其他两族添加实际使用的音频控制字段。
响应从 `output.audio.url` 提取完整音频链接，并保留 `request_id`、`usage`、
`output.audio.id` 和 `expires_at`。不依赖 SDK 的全局配置或预览接口。

## 参数与模型区别

- Qwen3 默认 `Auto` 识别语言；也可 `--language Chinese` / `English` 等。
  本实现只处理该接口返回的 WAV 文件，不提供音频转码。
- Qwen-Audio/CosyVoice 支持 `--format wav|mp3|pcm|opus`、`--sample-rate`、
  `--rate 0.5..2`、`--pitch 0.5..2`、`--volume 0..100`、`--language-hint zh`。
  未提供的控制字段不发送，由服务端使用默认值；输出格式默认 WAV。
- `--instruction` 仅向 Qwen-Audio/CosyVoice 转发。方言、情感和角色控制是否生效，
  取决于所选模型与音色，不承诺任意组合有效。
- 音色是模型相关的 ID，不能在模型族之间混用。官方示例：
  Qwen-Audio `qwen-audio-3.0-tts-flash` / `longanhuan_v3.6`；
  CosyVoice `cosyvoice-v3-plus` / `longanyang`。
- `--voice` 可接受已存在、与模型绑定的自定义音色，但本工具不创建/更新/删除音色。
- 输入长度受服务端模型限制；工具不猜测所有模型共有的长度阈值，不拆分文本。
  超长内容先根据官方对应模型限制处理，避免无意增加计费次数。
- 非流式音频链接通常 24 小时有效，应立即下载；PCM 没有容器头，不能用文件头确认格式，
  需要按请求的采样率和服务端编码信息播放。WAV/MP3/Opus 只做基本容器特征检查，
  不等于完整解码或音质验收。

## 官方来源与示例复用

本工具参考以下官方 HTTP 示例的请求/响应协议，重写了可复用 CLI，
新增参数校验、超时、结构化输出、凭证保护、文件保护和下载恢复。
没有整段复制或捆绑 SDK 源码，也不把官方示例当成已完成的生产验收。

- [Qwen3-TTS API：官方 curl 请求与字段](https://help.aliyun.com/zh/model-studio/qwen-tts-api)
- [Qwen-Audio-TTS HTTP API：格式、语速、音调等控制](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api)
- [CosyVoice HTTP API：北京地域与模型列表](https://help.aliyun.com/zh/model-studio/cosyvoice-tts-http-api)
- [非实时合成：官方 Python 请求与下载示例](https://help.aliyun.com/zh/model-studio/non-realtime-tts-user-guide)
- [Qwen-Audio 音色列表](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list)
- [CosyVoice 音色列表](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)
- [Qwen3-TTS 音色列表](https://help.aliyun.com/zh/model-studio/qwen-tts-voice-list)
- [模型与能力总览](https://help.aliyun.com/zh/model-studio/tts-model)
- [API Key](https://help.aliyun.com/zh/model-studio/get-api-key)
- [官方 DashScope SDK 仓库与示例](https://github.com/dashscope/dashscope-sdk-python)

若后续确实复制 SDK 示例源码，先固定源码 commit，按其 Apache-2.0 许可证保留版权、
许可证和适用 NOTICE，并记录修改点。当前实现只使用 Python 标准库，无 SDK 依赖。

## 后续扩展

实时 WebSocket、SSE、声音复刻、声音设计、ASR、图像等在用户提出需求后添加独立命令，
共用凭证、地域、错误与结果契约；不要把其他能力参数塞进 `tts`。
需要持久化任务和远程多宿主调用时再考虑共享核心与 MCP，不在此 skill 内建立 Harness。
