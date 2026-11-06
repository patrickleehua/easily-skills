# CLI 契约 1.0

运行入口：`python scripts/bailian.py`。`--help`、`--version` 输出人类可读文本，退出 0。
其他调用 stdout 仅一条 UTF-8 JSON；错误摘要写 stderr，退出码非零。
入口参数由 argparse 严格验证；可用 `tts --help` 检查完整参数，未知字段拒绝执行。

输入采用 CLI 参数，文本可从 `--text`、UTF-8（允许 BOM）文件 `--text-file` 或
`--text-file -` 的标准输入获取，三者互斥。环境变量提供凭证与默认地域/空间。
不提供 stdin JSON 模式；未来 CLI/MCP 适配层可以共用同一实现，协议不因宿主而变。

机器可读输出定义见 [result.schema.json](result.schema.json)。
`schema_version` 变更涉及兼容性时更新主版本；新增可选数据字段不改变既有字段语义。

| 字段 | 含义 |
|---|---|
| `schema_version` / `tool_version` | 输出协议 / 工具版本 |
| `run_id` / `started_at` / `elapsed_ms` | 本地运行 ID、UTC 开始时间、总耗时 |
| `runtime` | 实际 OS 与 Python 版本；宿主名称由上层执行记录补充 |
| `command` | 成功解析后的命令；解析失败时可能缺省 |
| `status` | `ok`、`dry_run` 或 `error` |
| `data` | 命令相关字段；失败时保留已经获得的证据 |
| `error` | 失败时的 `code`、`message`、`details` |

`tts` 的 `data` 包括模型、音色、地域、输出格式、目标绝对路径、文本长度及 SHA-256，
不输出文本正文。成功提交后加入服务端 request_id、usage、audio_url、audio_id、expires_at。
下载完成时 `file` 包含本地绝对路径、字节数、SHA-256。
`dry_run` 包含实际 endpoint 和去掉正文的 input_options，既不发网络请求也不写文件。

`models` 返回带模型族、地域与默认音色的随包清单，`live_query=false`。
`doctor` 返回环境配置是否存在，`network_checked=false`、`credential_validated=false`；
`status=ok` 只表示检查执行成功，不代表密钥/配置有效。
`download` 只 GET 现有链接并写盘，不调用合成 API。

## 退出码与恢复

| 退出码 | 含义 | 处理 |
|---|---|---|
| 0 | 成功 / dry-run / help / version | 检查 status 和对应字段 |
| 2 | 参数或模型组合错误 | 修正输入后再执行 |
| 3 | 缺少凭证或业务空间 | 通过环境配置 |
| 4 | HTTP、网络、服务响应或音频格式错误 | 检查 http_status / api_code / request_id |
| 5 | 网络超时 | 已提交的合成结果可能未知，不自动重提 |
| 6 | 本地文件或编码错误 | 检查路径、权限、格式和覆盖意图 |
| 130 | 用户中断 | 检查已提交请求，不假设远端被取消 |

`DOWNLOAD_FAILED` 且 `details.synthesis_completed=true` 时，音频已生成，
返回的链接可用于 `download`。429、5xx 和网络中断均不自动重试合成 POST，
因为远端不提供本工具可确认的去重保障。

`--timeout` 是每次 HTTP 操作的 socket 等待超时，默认 60 秒，允许 `(0,600]`。
POST 和 GET 分别计时，不是整个命令的总截止时间；持续缓慢传输可能超过该值。
Agent 宿主应为整个命令另设总时限。工具不启动后台任务或子进程，Ctrl+C 关闭当前连接。
远端请求无法靠关闭本地进程保证撤销。

JSON 响应最多 1 MiB；音频最多 128 MiB，完整下载后才发布目标文件。
文件默认不覆盖，显式 `--overwrite` 时通过同目录临时文件与 replace 替换；
否则使用同文件系统的排他 hard-link 发布，避免并发写入覆盖。
要求输出文件系统支持 hard-link（常见 NTFS、APFS、ext4 支持）；不支持时返回文件错误，
不降低为可能覆盖已有文件的写入方式。临时文件在正常失败/中断后清理；强杀可能残留 `.part`。

下载不带 API Key，不允许合成 POST 重定向。音频 GET 仅接受 HTTPS，
官方返回的 HTTP `*.aliyuncs.com` 链接升级为 HTTPS，GET 重定向也执行该规则。
错误输出不包含远端 message 或原始响应正文，防止泄漏文本与凭证。
签名音频 URL 仅作为结构化结果用于取回音频，勿公开或提交到版本库。

## 验证方式

```sh
uv sync --locked --group test
uv run --locked --no-sync python -m unittest discover -s tests -v
```

`test` 依赖组仅安装锁定的 JSON Schema 检查器与其依赖，普通使用不需要安装。
测试用本地 HTTP fixture 检查请求、鉴权隔离、错误与文件结果；CLI 子进程以
result.schema.json 校验输出，并检查退出码、中文/空格路径、stdin、凭证缺失和 dry-run；不消耗百炼额度。
模拟通过不代表云端通过，也不代表三系统均已实测。

真实验收需在用户已配置环境变量的机器生成短文本，核对 request_id、文件及实际试听。
三系统记录实际 OS、运行时、命令、退出码和 JSON 结果；安装测试依赖、执行测试不计入
使用者运行依赖。新适配器必须分别完成对应接口的真实验证。

当前验证记录见 [validation.md](validation.md)。
