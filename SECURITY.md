# 安全政策

## 支持版本

仅支持 `main` 分支的最新发布（见 [Releases](https://github.com/kingning2/dingda/releases)）。

## 报告漏洞

**请不要在公开 Issue / PR / 讨论区描述漏洞细节。**

请使用 GitHub 的「私下报告漏洞」通道：
`https://github.com/kingning2/dingda/security/advisories/new`

包含以下信息能显著加快处理：

- 漏洞类型与影响面（例如：本地提权 / 信息泄漏 / 爬虫越权）
- 复现步骤或 PoC（最小化）
- 影响版本（安装包版本号或 commit）
- 你期望的修复方向（可选）

## 范围界定

**属于安全漏洞：**

- 桌面客户端 IPC / Tauri 命令未授权访问
- 本地 API（`http://127.0.0.1:8787`）越权或 CSRF
- 账号 Cookie / 凭据存储与传输泄漏
- Python Server 反序列化、命令注入、路径穿越
- 安装包被替换或签名失效

**不属于安全漏洞：**

- 爬虫目标站点自身的业务风控
- 自行修改源码或使用非官方安装包导致的问题
- 对已登录第三方平台账号的常规限制

## 处理承诺

- 72 小时内确认收到
- 修复发布前与你同步进展
- 修复发布后在 Release Notes 中致谢（除非你希望匿名）
