# TTS V3 接入要点

核对日期：2026-11-06。实现以官方文档为依据，未复制社区工具代码。

- 用户提供的[体验页](https://exp.volcengine.com/ark/voice?model=doubao-seed-tts-2-0)：模型展示名 `doubao-seed-tts-2-0`。
- 用户提供的 [WebSocket 双向流式 V3](https://www.volcengine.com/docs/6561/1329505)：实时文本输入/音频输出，首批 CLI 未实现此协议。
- 本次实现的 [HTTP Chunked / SSE 单向流式 V3](https://www.volcengine.com/docs/6561/1598757)：完整文本输入，流式返回音频；首批使用其中的 Chunked 接口。
- [音色列表](https://www.volcengine.com/docs/6561/1257544)。默认 `zh_female_vv_uranus_bigtts` 为 Vivi 2.0，不能与 1.0 资源混用。

## 请求

`POST https://openspeech.bytedance.com/api/v3/tts/unidirectional`

新版控制台鉴权为 `X-Api-Key`，资源选择为 `X-Api-Resource-Id: seed-tts-2.0`。请求还带唯一的 `X-Api-Request-Id` 和 `X-Control-Require-Usage-Tokens-Return: *`，响应追踪 ID 为 `X-Tt-Logid`。

正文使用 `user.uid`、`req_params.text`、`req_params.speaker`、`req_params.audio_params`。语气指令放入 `req_params.additions` 的 `context_texts` 列表；`additions` 必须序列化成 JSON 字符串，当前仅第一个指令有效。

2.0 的字幕参数为 `audio_params.enable_subtitle`；`enable_timestamp` 是 1.0 参数，不能用它替代 2.0 字幕。2.0 常规合成按资源 ID 选择模型，正文 `model=seed-tts-2.0-standard/expressive` 属于声音复刻 2.0 的选项，本 CLI 不传。

## 响应与保存

响应是逐行 JSON。`code=0` 的 `data` 为 base64 音频；也可能返回 `sentence` 元数据。只有收到 `code=20000000` 且音频非空才完成，最后一条可能带 `usage.text_words`。不能将 JSON 或 base64 字符串原样写成音频。

MP3/Ogg/PCM 按顺序拼接解码后的字节。WAV 请求使用 PCM，在本地封装单声道 16-bit WAV，避免流式 WAV 重复 header。失败时删除临时文件，保留既有输出。流中断后不自动重试，以免重复计费。

## 故障定位

| 现象 | 检查 |
| --- | --- |
| `load grant` / `requested grant not found`、HTTP 401/403 | 是否为豆包语音新版控制台 API Key、是否已开通服务；旧版 App ID + Access Token 不能直接当作 API Key。首批 CLI 只实现新版鉴权 |
| `45000000` / `speaker permission denied` | 音色 ID 是否有效、账号是否有权限、是否匹配 seed-tts-2.0 |
| `quota exceeded` / concurrency | 额度、余额、并发限制；不盲目重复提交 |
| `40402003` / `TTSExceededTextLimit` | 超过所选服务的文本限制，按语义拆分或另接官方异步长文本接口；本 CLI 不擅自拆分 |
| HTTP 200，但无音频或未收到结束码 | 视为失败；提供 request_id / logid 排查，不展示为完整文件 |

字幕能力与语言、音色有关。只报告服务端实际返回的信息，不生成估算时间戳。
