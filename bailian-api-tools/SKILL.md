---
name: bailian-api-tools
description: >-
  调用阿里云百炼（Alibaba Cloud Model Studio / DashScope）的文字转语音接口，
  生成并下载 Qwen3-TTS、Qwen-Audio-TTS 或 CosyVoice 音频。用户提到百炼 TTS、
  通义语音合成、千问配音，或明确要求使用这些模型将文字变成音频时使用。
  不用于其他厂商、本地音频剪辑、语音识别、实时通话或创建复刻音色。
metadata:
  version: "0.1.0"
---

# 百炼 API 工具

当前交付文字转语音（HTTP 非流式）：文本 → 百炼 → 本地音频与 JSON 执行结果。
入口负责选参数，脚本负责校验、请求和保存；其他百炼能力按需增加独立命令。

## 环境与调用

- Python 3.12+；参考运行时固定在 `.python-version`，uv 项目不含第三方运行依赖。
- 进入本 skill 目录，先执行 `uv sync --locked`；之后使用 `uv run --locked --no-sync python scripts/bailian.py ...`。
- 已有 Python 环境时也可直接 `python scripts/bailian.py ...`，不依赖业务项目环境。
- 凭证仅从环境变量 `DASHSCOPE_API_KEY` 读取，不能放入命令参数、文档或对话。
  `.env.example` 仅为配置模板，脚本**不会自动加载 .env**。
- `DASHSCOPE_REGION` 默认 `cn-beijing`，另支持 `ap-southeast-1`；密钥须与地域一致。
  `DASHSCOPE_WORKSPACE` 可设置业务空间 ID；Qwen-Audio-TTS / CosyVoice 必须设置。

Agent 应先确定本 skill 的绝对路径，把它作为命令工作目录。下列命令均在该目录运行，
输出文件使用用户指定的路径；未指定时保存到调用目录的 `output/`。

```sh
uv run --locked --no-sync python scripts/bailian.py doctor
uv run --locked --no-sync python scripts/bailian.py models
uv run --locked --no-sync python scripts/bailian.py tts --text "你好，欢迎使用百炼。" --output output/hello.wav --dry-run
uv run --locked --no-sync python scripts/bailian.py tts --text "你好，欢迎使用百炼。" --output output/hello.wav
```

## 选择与执行

1. 保留用户指定的模型、音色、地域与文本。未指定时用 `qwen3-tts-flash` / `Cherry` / `Auto`；
   这是配置最少的默认值。若需要语速、音调或指令控制，选择 Qwen-Audio-TTS，
   根据 [TTS 参考](references/tts.md) 设置模型与对应音色。
2. `doctor` 仅检查本地配置，不验证密钥、额度或模型权限。缺少密钥时给出环境变量名称，
   不要求用户把密钥发到聊天中。
3. 先用 `--dry-run` 检查参数和目标路径；它不会发请求、不会写文件，也不要求密钥。
   用户已要求生成语音时可直接完成实际调用，无需额外确认。
4. 运行 `tts`。长文本或包含换行的内容优先用 `--text-file` 读取 UTF-8 文件，
   `--text-file -` 可从标准输入读取；不自动截断、拆单或重复提交。
5. 只有 `status=ok` 且返回本地文件后，才报告音频生成并保存成功。
   在支持媒体的宿主中用绝对路径展示或播放音频；主观音质仍需要试听。

```sh
# Qwen-Audio-TTS；业务空间也可通过 DASHSCOPE_WORKSPACE 设置。
uv run --locked --no-sync python scripts/bailian.py tts --model qwen-audio-3.0-tts-flash --voice longanhuan_v3.6 --workspace YOUR_WORKSPACE_ID --text-file narration.txt --format mp3 --rate 1.1 --output output/narration.mp3

# CosyVoice HTTP 仅支持北京；音色必须与模型对应。
uv run --locked --no-sync python scripts/bailian.py tts --model cosyvoice-v3-plus --voice longanyang --region cn-beijing --workspace YOUR_WORKSPACE_ID --text "欢迎收听。" --output output/cosy.wav
```

## 失败与交付

- 默认不覆盖文件；只有用户允许覆盖时才加 `--overwrite`。
- 合成 POST 不自动重试。超时或中断意味着远端结果可能未知，不能把重跑当成无成本恢复。
- 若 `error.details.synthesis_completed=true`，合成已返回音频链接，只是下载/写盘失败。
  使用返回的 `audio_url` 调用 `download`，不要重新合成。临时签名 URL 具有访问能力，
  仅供本次恢复使用，不提交仓库、不贴入公开日志。

```sh
uv run --locked --no-sync python scripts/bailian.py download --url "RETURNED_AUDIO_URL" --output output/recovered.wav
```

结果包括工具/协议版本、运行 ID、UTC 时间、OS、Python 版本、耗时、文本长度与摘要、
模型、音色、请求 ID、服务端 usage、文件大小及 SHA-256。没有服务端用量时不推算费用。
stdout 只输出一个 JSON 结果，诊断写 stderr；`--help` / `--version` 除外。
字段、退出码及超时边界见 [CLI 契约](references/contract.md)；
官方接口和示例来源、扩展边界见 [TTS 参考](references/tts.md)。
