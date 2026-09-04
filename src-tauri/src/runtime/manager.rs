use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};

use tauri::{AppHandle, Emitter};

use crate::agent::log::{
    log_agent, log_agent_event, log_agent_prompt, truncate_for_log, StreamLogBuffer,
};

use super::event::{AgentEvent, AgentEventEnvelope};
use super::invocation::{build_invocation, invocation_context};
use super::parsers::create_parser;
use super::process::{read_stderr_lines, read_stdout_lines, spawn_process};
use super::registry::find_runtime;
use super::runs::{self, register, unregister};
use super::types::{RuntimeDefinition, RuntimeInvocation};

static RUN_COUNTER: AtomicU64 = AtomicU64::new(1);

pub fn next_run_id() -> String {
    format!("run-{}", RUN_COUNTER.fetch_add(1, Ordering::Relaxed))
}

pub struct RuntimeManager;

impl RuntimeManager {
    pub fn find(runtime_id: &str) -> Option<&'static RuntimeDefinition> {
        find_runtime(runtime_id)
    }

    pub fn build_invocation(
        runtime_id: &str,
        prompt: String,
        cwd: std::path::PathBuf,
        env: HashMap<String, String>,
        model: Option<String>,
        session_id: Option<String>,
        reasoning: Option<String>,
        extra_allowed_dirs: Vec<std::path::PathBuf>,
    ) -> Result<RuntimeInvocation, String> {
        let definition =
            find_runtime(runtime_id).ok_or_else(|| format!("未知 Runtime：{runtime_id}"))?;
        let session_id = if definition.capabilities.supports_resume {
            session_id
        } else {
            None
        };
        let context = invocation_context(
            definition,
            prompt,
            cwd,
            model,
            session_id,
            reasoning,
            extra_allowed_dirs,
        );
        build_invocation(definition, context, env)
    }

    /// 拉起 CLI：中文日志记录命令、提示词与流式事件，并向前端 emit。
    pub async fn launch_with_app(
        app: &AppHandle,
        invocation: RuntimeInvocation,
        definition: &RuntimeDefinition,
        run_id: String,
    ) -> Result<i32, String> {
        let command_line = format_command_line(&invocation);
        log_agent(
            "准备启动 CLI",
            Some(&format!(
                "runtime={} run={} cwd={}",
                invocation.runtime_id,
                run_id,
                invocation.cwd.display()
            )),
        );
        log_agent("启动命令", Some(&command_line));
        if let Some(session) = extract_session_from_args(&invocation.args) {
            log_agent("续聊会话", Some(&session));
        }
        if let Some(prompt) = invocation.prompt.as_deref() {
            log_agent_prompt(prompt);
        } else {
            log_agent("发送提示词", Some("（参数内嵌 / 无 stdin）"));
        }

        let mut child = spawn_process(&invocation).await?;
        log_agent(
            "进程已启动",
            Some("等待 CLI 首包（冷启动/模型推理可能要几秒到几十秒）…"),
        );
        if let Some(stderr) = child.stderr.take() {
            let run_label = run_id.clone();
            tauri::async_runtime::spawn(async move {
                let _ = read_stderr_lines(tokio::io::BufReader::new(stderr), |line| {
                    let text = line.trim_end();
                    if text.is_empty() {
                        return;
                    }
                    log_agent(
                        "CLI 诊断输出",
                        Some(&format!(
                            "run={} {}",
                            run_label,
                            truncate_for_log(text, 800)
                        )),
                    );
                })
                .await;
            });
        }

        let shared = register(&run_id, child);

        let stdout = {
            let mut guard = shared.lock().await;
            guard
                .as_mut()
                .and_then(|child| child.stdout.take())
                .ok_or_else(|| "无法获取 stdout".to_string())?
        };

        {
            let mut stream_log = StreamLogBuffer::new();
            let mut emit = |event: AgentEvent| {
                match &event {
                    AgentEvent::TextDelta { text } => stream_log.push_text(text),
                    AgentEvent::Thinking { text } => stream_log.push_thinking(text),
                    other => {
                        stream_log.flush_all();
                        log_agent_event(other);
                    }
                }

                let envelope = AgentEventEnvelope {
                    run_id: run_id.clone(),
                    event,
                };
                let _ = app.emit("agent-event", &envelope);
            };

            emit(AgentEvent::RunStarted {
                runtime_id: invocation.runtime_id.clone(),
                run_id: run_id.clone(),
            });

            let mut parser = create_parser(definition.stream_format, definition.id, &run_id);
            let stdout_result =
                read_stdout_lines(tokio::io::BufReader::new(stdout), |line| {
                    for event in parser.feed(line) {
                        emit(event);
                    }
                })
                .await;

            if let Err(error) = stdout_result {
                emit(AgentEvent::Error {
                    message: error.clone(),
                });
            }

            for event in parser.finish() {
                emit(event);
            }

            stream_log.flush_all();
        }

        let exit_code = {
            let mut guard = shared.lock().await;
            if let Some(mut child) = guard.take() {
                let status = child
                    .wait()
                    .await
                    .map_err(|error| format!("等待进程失败：{error}"))?;
                status.code().unwrap_or(-1)
            } else {
                -1
            }
        };

        unregister(&run_id);

        let emit_done = |event: AgentEvent| {
            log_agent_event(&event);
            let envelope = AgentEventEnvelope {
                run_id: run_id.clone(),
                event,
            };
            let _ = app.emit("agent-event", &envelope);
        };

        if exit_code != 0 {
            emit_done(AgentEvent::Error {
                message: format!("CLI 退出码 {exit_code}"),
            });
        }

        emit_done(AgentEvent::RunCompleted { exit_code });
        Ok(exit_code)
    }

    pub async fn cancel_run(run_id: &str) -> Result<(), String> {
        log_agent("取消运行", Some(run_id));
        runs::cancel(run_id).await
    }
}

fn format_command_line(invocation: &RuntimeInvocation) -> String {
    let exe = invocation.executable.display();
    if invocation.args.is_empty() {
        return exe.to_string();
    }
    let args = invocation
        .args
        .iter()
        .map(|arg| {
            if arg.chars().any(|c| c.is_whitespace()) {
                format!("\"{arg}\"")
            } else {
                arg.clone()
            }
        })
        .collect::<Vec<_>>()
        .join(" ");
    format!("{exe} {args}")
}

fn extract_session_from_args(args: &[String]) -> Option<String> {
    for (i, arg) in args.iter().enumerate() {
        if arg == "--session" || arg == "--resume" {
            return args.get(i + 1).cloned();
        }
        if arg == "resume" {
            return args
                .get(i + 1)
                .filter(|next| !next.starts_with('-'))
                .cloned();
        }
    }
    None
}
