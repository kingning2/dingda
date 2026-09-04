# channels/ali1688

1688 **官方找货**：AK 签名 HTTP + clawhub 扫码取 AK。

```text
账号扫码弹窗
  → Ali1688QrChannel（browser.sync）
  → clawhub 登录二维码 → save_ak
  → crawler/sources/ali1688 调 find_product
```

## 本目录文件

| 文件 | 职责 |
|------|------|
| `ak.py` | 读/写/探活/清除 `ALI_1688_AK` 与 `~/.dingda/v2/ali1688/ak.json` |
| `sign.py` | HMAC `x-csk-*` 签名头 |
| `client.py` | `find_product` 网关客户端 |
| `login.py` | clawhub 开登录弹窗 / 截码 / 抽 AK |
| `channel.py` | `QrLoginChannel` 扫码状态机 |
| `__init__.py` | 包标记 |

渠道后缀默认 `dingda`（`ALI_1688_CHANNEL` 可覆盖）。
