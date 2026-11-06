# 0.1.0 验证记录

日期：2026-10-28，Asia/Singapore。执行宿主：Codex desktop / PowerShell。

| 检查 | 实际环境与结果 |
|---|---|
| 运行时 | Windows，CPython 3.12.14，uv 0.12.7 |
| 依赖 | `uv sync --locked --group test` 成功；运行依赖为零，test 组单独锁定 |
| CLI / HTTP / JSON Schema | `python -m unittest discover -s tests -v`，16 项通过 |
| Skill 格式 | skill-creator 的 `quick_validate.py` 通过 |
| 目录登记 | `uv run scripts/sync_readme.py --check` 通过，无待登记技能 |
| 云端密钥 | 当前进程未配置，不执行真实合成 |
| Linux / macOS | 已添加 CI 矩阵，本次未运行 |
| 真实音频与试听 | 待配置凭证后验证；fixture 音频不作为音质证据 |

运行测试时使用本机 HTTP fixture，测试凭证为固定虚构值。
已验证合成 POST 的请求体与请求路径、GET 不带密钥、401/429/500 不重试、
HTTP 200 业务错误、错误 JSON、音频缺失、损坏/截断响应、下载恢复、并发文件保护、
显式覆盖、写盘中断清理、重定向限制，以及带 BOM/CRLF/中文/空格路径输入。
CLI 子进程的结果按随包 `result.schema.json` 校验。

本地配置检查证据（不代表云端连通）：

```json
{
  "schema_version": "1.0",
  "tool_version": "0.1.0",
  "run_id": "3bd37856-7431-4e17-b2fb-c11545feef0d",
  "started_at": "2026-10-28T05:27:22.361773+00:00",
  "runtime": {"os": "Windows", "python": "3.12.14"},
  "data": {
    "api_key_present": false,
    "region": "cn-beijing",
    "workspace_present": false,
    "network_checked": false,
    "credential_validated": false
  },
  "command": "doctor",
  "status": "ok",
  "elapsed_ms": 31
}
```

真实验收：在本地通过环境变量注入同地域的 API Key，需要时设置业务空间；
执行 SKILL.md 中的短文本合成命令，检查服务端 request_id、实际文件及试听结果。
每类模型分别验证，不能用某一类的成功推断其他模型或地域也已通过。
