---
name: rust-coding
description: 叮答 Rust 编码范例。编写或修改 packages-rs/client/ 下 Rust 时必须遵循本 Skill 中的示例：文件头、函数注释、多实现插座、命名、生命周期日志。少写边界分支。
---

# Rust 编码范例（照抄结构）

写 `packages-rs/**/*.rs` 时**按下面示例的形状写**，不要自创风格。壳边界见 [layers.md](../layers.md)。

---

## 示例 A：文件头 + 函数注释 + 日志

目标路径：`packages-rs/python/src/lifecycle.rs`（目录已是 `python`，文件不要叫 `python_lifecycle_manager.rs`）

```rust
//! 拉起 / 停止 Python Server，并向前端发出就绪事件。

use tauri::{AppHandle, Emitter};

impl PythonLifecycle {
    /// 后台启动 Server：spawn → 探活 → emit ready/error，不阻塞窗口。
    pub async fn start_background(&self, app: AppHandle) -> Result<(), PythonLifecycleError> {
        log_shell("python server starting", Some(self.api_base_url().as_str()));
        self.spawn().await?;
        match self.wait_until_healthy().await {
            Ok(()) => {
                log_shell("python server ready", None);
                let _ = app.emit("server-ready", self.api_base_url());
                Ok(())
            }
            Err(error) => {
                log_shell("python server failed", Some(&error.to_string()));
                let _ = app.emit("server-error", error.to_string());
                Err(error)
            }
        }
    }
}
```

### 错误示范（禁止）

```rust
// ❌ 无 //!、无 ///、无日志
pub async fn start_background(&self, app: AppHandle) -> Result<(), PythonLifecycleError> {
    self.spawn().await?;
    self.wait_until_healthy().await
}
```

---

## 示例 B：多实现插座（Definition + registry）

### 插座类型 — `runtime/types.rs`（节选）

```rust
//! Runtime 公共类型：Definition 是各 CLI 插头必须填的插座。

/// 一个外部 CLI Agent 的静态定义（插座字段）。
pub struct RuntimeDefinition {
    pub id: &'static str,
    pub binary: &'static str,
    pub build_args: BuildArgsFn,
    pub discover_models: DiscoverModelsFn,
    // ...
}
```

### 插头 — `runtime/defs/codex.rs`

```rust
//! Codex CLI 插头：二进制、参数构建与模型发现。

use super::build_args::codex_build_args;
use crate::runtime::types::RuntimeDefinition;

pub const CODEX: RuntimeDefinition = RuntimeDefinition {
    id: "codex",
    name: "Codex",
    binary: "codex",
    build_args: codex_build_args,
    // ...
};
```

### 注册 — `runtime/registry.rs`

```rust
//! 外部 CLI Runtime 注册表：按 id 取插头，调用方禁止大 match。

use crate::runtime::defs::{CLAUDE, CODEX /* ... */};
use crate::runtime::types::RuntimeDefinition;

static RUNTIME_REGISTRY: &[&RuntimeDefinition] = &[&CODEX, &CLAUDE /* ... */];

/// 按 id 查找 Runtime 插头。
pub fn find_runtime(id: &str) -> Option<&'static RuntimeDefinition> {
    RUNTIME_REGISTRY.iter().copied().find(|def| def.id == id)
}
```

### 错误示范（禁止）

```rust
// ❌ 业务里堆 match
match runtime_id.as_str() {
    "codex" => launch_codex(...),
    "claude" => launch_claude(...),
    _ => Err("unknown".into()),
}

// ❌ 文件名重复：runtime/defs/codex_runtime_def.rs
```

新增 CLI：只加 `defs/<id>.rs` + registry 一行，不改调用方分支。

---

## 示例 C：探测流程日志

目标路径：`packages-rs/agent/src/probe.rs`

```rust
//! 按 Agent id 探测本机安装与鉴权状态。

/// 探测单个 Agent：解析路径 → 跑 version/login 探针 → 汇总结果。
pub async fn probe_agent_by_id(agent_id: &str) -> Result<AgentRuntimeProbeResult, String> {
    eprintln!("[agent] probe start id={agent_id}");
    let detection = detect_runtime(agent_id).await?;
    eprintln!(
        "[agent] probe done id={agent_id} available={} version={:?}",
        detection.available, detection.version
    );
    Ok(detection.into_probe_result())
}
```

少纠结边界：路径解析失败直接 `Err(message)` + 日志，不要为三种 Windows 盘符写特殊框架。

---

## 命名速查

| 位置 | 正确 | 错误 |
|------|------|------|
| `runtime/defs/` | `codex.rs` `claude.rs` | `codex_def.rs` `codex_lib.rs` |
| `runtime/parsers/` | `opencode.rs` | `opencode_parser_impl.rs` |
| `python/` | `lifecycle.rs` | `python_lifecycle_manager.rs` |

---

## 目录 README（树形，上层引用下层）

每个**有 `.rs` 的文件夹**必须有 `README.md`。`target/`、`gen/`、`icons/` 不要写。

形状照抄 `packages-rs/client/src/README.md`：

1. 一行总述本目录职责
2. **本目录文件**：每个 `.rs` 单独一小节，写清干什么、关键类型/函数、谁调用。`lib.rs` 必须写透
3. **子目录**：相对链接指向下层 `README.md`，不要把子目录每个文件抄进上层
4. 禁止另起一套地图；文件级细节以下层 README 为准

不要只写「`lifecycle.rs` — 起停 Python」。读者没看过代码也要能知道该打开哪个文件。

新增目录时：先写下层 README，再在上层「子目录」里加一行链接。

---

## 检查清单（交代码前）

- [ ] 文件顶有 `//!` 说明本文件职责
- [ ] `pub` 与关键私有函数有 `///`（解决什么问题）
- [ ] 多实现走 Definition/trait + registry，无业务大 `match`
- [ ] 文件名不重复目录语义，且一眼能懂
- [ ] 启动 / 进展 / 结束或失败有日志
- [ ] 没有为大边界情况堆防御代码
- [ ] 没有把产品 HTTP 业务塞进 Tauri command
- [ ] 本目录有 `README.md`；上层 README 已链接到本目录
