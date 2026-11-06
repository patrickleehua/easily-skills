---
name: volcengine-api-tools
description: 调用火山引擎豆包语音 API，将文字合成为音频并保存到本地。首批支持 Doubao Seed TTS 2.0 的音色、语速、音量、语气指令与字幕元数据。用户提到火山引擎 TTS、豆包配音、doubao-seed-tts-2-0 或要求使用这些服务文字转语音时使用；不用于其他厂商、语音识别、音色克隆训练或实时语音通话。
---

# 火山引擎 API Tools

首批能力为 Seed TTS 2.0，通过官方 V3 HTTP 单向流式接口生成本地音频。Python 3.10+，仅使用标准库。命令从本技能目录执行；也可以使用 `run.py` 的绝对路径。

## 配置

新版豆包语音控制台的 API Key 放入环境变量 `VOLCENGINE_SPEECH_API_KEY`。不要把方舟聊天模型的 `ARK_API_KEY`、云账号 AK/SK 或旧版 Access Token 当作这个 Key。

PowerShell：

```powershell
$env:VOLCENGINE_SPEECH_API_KEY = '你的语音服务 API Key'
python run.py tts --text '你好，欢迎使用豆包语音。' --output ./output/hello.mp3
```

也可以复制 `.env.example` 为本技能目录的 `.env`，填入 Key，然后用 uv 加载：

```powershell
uv run --env-file .env python run.py tts --text '你好，欢迎使用豆包语音。' --output ./output/hello.mp3
```

直接 `python run.py` 不自动读取 `.env`。密钥不放入命令参数、输出、提交或对话；缺少凭据时，说明需要在本地配置，不要求用户把 Key 发到聊天。

## 调用

```powershell
# 离线查看本批模型和示例音色，不调用 API
python run.py models
python run.py voices

# 检查请求参数，无需凭据，不调用 API
python run.py tts --text '这是一段试听。' --dry-run

# 正式合成，默认 Vivi 2.0，MP3，24000 Hz
python run.py tts --text '今天，我们一起探索新的可能。' --output ./output/narration.mp3

# UTF-8 文本文件；语气指令通过 additions.context_texts 传入
python run.py tts --text-file ./narration.txt --speaker zh_female_vv_uranus_bigtts --instruction '请用温柔、自然的语气朗读。' --speech-rate -10 --loudness-rate 0 --subtitle --output ./output/narration.mp3

# WAV 在本地由 PCM 封装，避免服务端流式 WAV 的重复文件头
python run.py tts --text '你好。' --format wav --output ./output/hello.wav
```

| 参数 | 含义 |
| --- | --- |
| `--text` / `--text-file` | 必选其一，文本文件为 UTF-8（可带 BOM） |
| `--model` | 当前仅 `doubao-seed-tts-2-0`，映射资源 `seed-tts-2.0` |
| `--speaker` | 默认环境变量 `VOLCENGINE_TTS_SPEAKER`，否则 Vivi 2.0；可传官方列表的其他 2.0 音色 ID |
| `--format` | `mp3`、`ogg_opus`、`pcm`、`wav`；默认 mp3 |
| `--sample-rate` | 8000 / 16000 / 22050 / 24000 / 32000 / 44100 / 48000；默认 24000 |
| `--speech-rate` / `--loudness-rate` | -50 到 100；0 正常，-50 为 0.5 倍，100 为 2 倍 |
| `--instruction` | 单条自然语言语气指令，不拼接进朗读正文 |
| `--subtitle` | 开启 2.0 的 `enable_subtitle`，把服务端返回的 sentence 元数据保存到旁车 JSON |
| `--output` | 默认生成唯一文件名到当前目录的 output/；已存在的文件不覆盖 |
| `--timeout` | 每次网络阻塞的超时秒数，默认 120；不自动重试收费请求 |

音色列表命令只显示经文档核对的默认示例，不代表账号已授权音色或完整在线目录。其他音色从[官方音色表](https://www.volcengine.com/docs/6561/1257544)选择，必须与 TTS 2.0 资源匹配。

## 执行与交付

1. 使用用户给定的文本、音色、路径和参数；未指定时使用默认值。仅要接入代码或查看参数时，不额外生成收费音频。
2. 合成命令退出码为 0，且输出 JSON 的 `status` 为 `complete` 才表示成功。API 返回 HTTP 200 仍可能包含业务错误；流中断不算完成。
3. 返回音频的绝对路径及旁车 JSON 路径。旁车包含模型、音色、请求 ID、logid、文件大小、用量和服务端实际返回的字幕，不含密钥和 base64 音频。PCM/WAV 可返回计算时长；MP3/Ogg 时长不猜测。
4. 向用户展示本地音频时，用 Markdown 音频媒体嵌入并使用绝对路径。不要把离线测试通过写成真实合成成功。

首批不包含双向 WebSocket、长文本异步任务、声音复刻训练或 MCP 常驻服务。用户提供的双向流文档与本次使用的 HTTP 接口属于同一 V3 API 家族，不能把两者的协议报文混用。

鉴权、资源与错误排查见 [references/tts-api.md](references/tts-api.md)；现成方案调研见 [references/ecosystem.md](references/ecosystem.md)。
