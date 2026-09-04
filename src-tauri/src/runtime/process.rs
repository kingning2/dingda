//! 拉起外部 CLI 子进程，并按需完成 ACP JSON-RPC 握手。

use std::process::Stdio;

use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdout, Command};

use super::types::RuntimeInvocation;

/// spawn 结果：child + 已取走的 stdout（供流式解析）。
pub struct SpawnedProcess {
    pub child: Child,
    pub stdout: BufReader<ChildStdout>,
}

/// 启动 CLI；若带 `acp_mcp_servers` 则先 initialize / session/new / session/prompt。
pub async fn spawn_process(invocation: &RuntimeInvocation) -> Result<SpawnedProcess, String> {
    let mut command = Command::new(&invocation.executable);
    command
        .args(&invocation.args)
        .current_dir(&invocation.cwd)
        .envs(&invocation.env)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);

    let mut child = command
        .spawn()
        .map_err(|error| format!("无法启动 {}：{error}", invocation.executable.display()))?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "无法获取 stdout".to_string())?;
    let mut reader = BufReader::new(stdout);

    if let Some(servers) = &invocation.acp_mcp_servers {
        eprintln!(
            "[runtime/process] ACP 握手开始 runtime={} mcp={}",
            invocation.runtime_id,
            servers.len()
        );
        bootstrap_acp_session(&mut child, &mut reader, invocation, servers).await?;
        eprintln!(
            "[runtime/process] ACP 握手完成 runtime={}",
            invocation.runtime_id
        );
    } else if invocation.prompt_via_stdin {
        if let (Some(prompt), Some(mut stdin)) = (&invocation.prompt, child.stdin.take()) {
            stdin
                .write_all(prompt.as_bytes())
                .await
                .map_err(|error| format!("写入 stdin 失败：{error}"))?;
            stdin
                .shutdown()
                .await
                .map_err(|error| format!("关闭 stdin 失败：{error}"))?;
        }
    }

    Ok(SpawnedProcess {
        child,
        stdout: reader,
    })
}

/// ACP：initialize → session/new（带 mcpServers）→ session/prompt。
async fn bootstrap_acp_session(
    child: &mut Child,
    reader: &mut BufReader<ChildStdout>,
    invocation: &RuntimeInvocation,
    servers: &[Value],
) -> Result<(), String> {
    let stdin = child
        .stdin
        .as_mut()
        .ok_or_else(|| "无法获取 stdin".to_string())?;

    let init_params = json!({
        "protocolVersion": 1,
        "clientInfo": { "name": "dingda", "version": "0.1.0" },
        "clientCapabilities": {},
    });
    request_acp(reader, stdin, 1, "initialize", init_params).await?;

    let session_params = json!({
        "cwd": invocation.cwd.to_string_lossy(),
        "mcpServers": servers,
    });
    let session = request_acp(reader, stdin, 2, "session/new", session_params).await?;
    let session_id = session
        .get("sessionId")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "ACP session/new 未返回 sessionId".to_string())?;

    let prompt_text = invocation.prompt.as_deref().unwrap_or("");
    let prompt_params = json!({
        "sessionId": session_id,
        "prompt": [{ "type": "text", "text": prompt_text }],
    });
    // session/prompt 的最终 result 往往在整轮结束后才到；这里只发出请求，
    // 后续 session/update 由 stdout 流解析。
    write_acp(stdin, 3, "session/prompt", prompt_params).await?;
    Ok(())
}

async fn request_acp(
    reader: &mut BufReader<ChildStdout>,
    stdin: &mut tokio::process::ChildStdin,
    id: u64,
    method: &str,
    params: Value,
) -> Result<Value, String> {
    write_acp(stdin, id, method, params).await?;
    let id_str = id.to_string();
    let mut line = String::new();
    loop {
        line.clear();
        let read = reader
            .read_line(&mut line)
            .await
            .map_err(|e| format!("读取 ACP 响应失败：{e}"))?;
        if read == 0 {
            return Err(format!("ACP 在等待 {method} 时关闭 stdout"));
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let env: Value = serde_json::from_str(trimmed)
            .map_err(|e| format!("解析 ACP JSON 失败：{e}"))?;
        let env_id = env.get("id").map(|v| match v {
            Value::Number(n) => n.to_string(),
            Value::String(s) => s.clone(),
            _ => String::new(),
        });
        if env_id.as_deref() != Some(id_str.as_str()) {
            // 握手期间可能夹杂 notification，跳过
            continue;
        }
        if let Some(err) = env.get("error") {
            if !err.is_null() {
                return Err(format!("ACP {method} 错误：{err}"));
            }
        }
        return env
            .get("result")
            .cloned()
            .ok_or_else(|| format!("ACP {method} 无 result"));
    }
}

async fn write_acp(
    stdin: &mut tokio::process::ChildStdin,
    id: u64,
    method: &str,
    params: Value,
) -> Result<(), String> {
    let msg = json!({
        "jsonrpc": "2.0",
        "id": id,
        "method": method,
        "params": params,
    });
    let mut data = serde_json::to_vec(&msg).map_err(|e| format!("序列化 ACP 请求失败：{e}"))?;
    data.push(b'\n');
    stdin
        .write_all(&data)
        .await
        .map_err(|e| format!("写入 ACP 请求失败：{e}"))?;
    stdin
        .flush()
        .await
        .map_err(|e| format!("flush ACP 请求失败：{e}"))?;
    Ok(())
}

pub async fn read_stdout_lines<F>(
    mut reader: BufReader<ChildStdout>,
    mut on_line: F,
) -> Result<(), String>
where
    F: FnMut(&str),
{
    read_lines(&mut reader, &mut on_line).await
}

pub async fn read_stderr_lines<F>(
    mut reader: BufReader<tokio::process::ChildStderr>,
    mut on_line: F,
) -> Result<(), String>
where
    F: FnMut(&str),
{
    read_lines(&mut reader, &mut on_line).await
}

async fn read_lines<R, F>(reader: &mut BufReader<R>, on_line: &mut F) -> Result<(), String>
where
    R: tokio::io::AsyncRead + Unpin,
    F: FnMut(&str),
{
    let mut line = String::new();
    loop {
        line.clear();
        let read = reader
            .read_line(&mut line)
            .await
            .map_err(|error| format!("读取进程输出失败：{error}"))?;
        if read == 0 {
            break;
        }
        on_line(&line);
    }
    Ok(())
}
