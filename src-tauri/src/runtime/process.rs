use std::process::Stdio;

use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};

use super::types::RuntimeInvocation;

pub async fn spawn_process(invocation: &RuntimeInvocation) -> Result<Child, String> {
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

    if invocation.prompt_via_stdin {
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

    Ok(child)
}

pub async fn read_stdout_lines<F>(
    mut reader: BufReader<tokio::process::ChildStdout>,
    mut on_line: F,
) -> Result<(), String>
where
    F: FnMut(&str),
{
    let mut line = String::new();
    loop {
        line.clear();
        let read = reader
            .read_line(&mut line)
            .await
            .map_err(|error| format!("读取 stdout 失败：{error}"))?;
        if read == 0 {
            break;
        }
        on_line(&line);
    }
    Ok(())
}
