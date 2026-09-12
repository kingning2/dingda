# runtime

本机 CLI Agent：**找二进制 → 探测 → 模型列表 → 托管下载**。

启动与取消在 Python：`packages-py/cli/src/cli/` + `/v1/agent/runtimes/...` SSE。

```text
RuntimeDefinition (defs/)
  → resolution → detection / model_discover
  → install（托管下载/安装，部分 CLI）
```

禁止在探测路径里 `if runtime_id == "codex"`。差异放 `defs/<id>.rs`。

## 本目录文件

### `mod.rs`

子模块声明；对外 re-export：`find_runtime`、`resolve_executable`、`RuntimeDefinition`。

### `types.rs`

插座与快照：`RuntimeDefinition`、`RuntimeDetection`、`ResolvedExecutable`、`RuntimeModel` 等。

### `registry.rs`

`RUNTIME_REGISTRY` + `find_runtime(id)`。新增 CLI：defs 里 `pub const` 后必须在这里加一行。

### `resolution.rs`

`resolve_executable`：环境变量 → 托管目录 → PATH → 已知安装目录。

### `detection.rs`

`detect_runtime`：resolve 后跑 `version_args` / auth probe。

### `install.rs`

托管下载 / 安装：`download_managed` + 下载 / 解压 / 落盘 / 版本读取。各插头只填
`managed_download: Some(ManagedDownloadSpec { .. })`，不要复制下载代码。

## 子目录

- [defs/](defs/README.md) — 每个 CLI 一份 `RuntimeDefinition`
- [model_discover/](model_discover/README.md) — 模型列表 helper

与 [../agent/README.md](../agent/README.md)：那边是 IPC DTO / 探测编排，这边是定义表与路径解析。
