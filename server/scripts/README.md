# scripts

开发与验收辅助脚本，不属于产品运行时。

## 本目录文件

- `agent_acceptance.py` — 外部 Agent 端到端验收：OpenCode 使用 hy3，
  检查直播帧、Skill/历史压缩、切换 Agent 后的上下文承接、前端历史回退，
  并把失败归因成「本机代理配置错误」或「Agent 链路失败」。
- `e2e_dom_repair.py` — DOM 修复链路端到端调试。
- `prefetch_ocr.py` — OCR 预热。
- `probe_xianyu_detail_dom.py` — 闲鱼详情 DOM 探针。
- `probe_xianyu_detail_dom_wait.py` — 带等待时间线的闲鱼详情 DOM 探针。
- `probe_xianyu_detail_struct.py` — 闲鱼详情结构探针。
- `probe_xiaohongshu_detail.py` — 小红书详情探针。

## Agent 验收

```bash
uv run python scripts/agent_acceptance.py --case compression --case rollback
uv run python scripts/agent_acceptance.py --case preview
uv run python scripts/agent_acceptance.py --case search
uv run python scripts/agent_acceptance.py --case context
uv run python scripts/agent_acceptance.py --case proxy
```

### 失败归因：代理配置 vs Agent 链路

脚本跑前会扫一遍代理环境变量（大小写都看），把畸形 URL（如
`http://1270.0.01:7897` 这种非法 IPv4）清掉，并让本机回环绕开代理。

每条失败结果都带 `failure_kind`：

| failure_kind | 含义 |
| --- | --- |
| `proxy-misconfigured` | 连接类报错，且环境里确有畸形代理 → 本机代理配置错误 |
| `network-unreachable` | 连接类报错，但环境干净 → 网络不通，不是代理写错 |
| `agent-chain` | 非连接类报错 → Agent 链路自身问题 |

`--case proxy` 会做实证归因：同一个 runtime 先注入畸形代理（应失败并归为
`proxy-misconfigured`），再清掉代理（应成功）。第二轮成功即证明模型可达、
链路完好，第一轮的失败纯粹是代理配置造成的。默认用 `--proxy-runtime opencode`，
可用 `--proxy-timeout` 调单轮超时。
