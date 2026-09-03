use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};

use tauri::{AppHandle, Emitter};

use super::detection::{detect_runtime, is_runtime_available};
use super::event::{AgentEvent, AgentEventEnvelope};
use super::invocation::{build_invocation, invocation_context};
use super::parsers::create_parser;
use super::process::{read_stdout_lines, spawn_process};
use super::registry::{find_runtime, RUNTIME_REGISTRY};
use super::resolution::resolve_executable;
use super::runs::{self, register, unregister};
use super::types::{ResolvedExecutable, RuntimeDefinition, RuntimeDetection, RuntimeInvocation};

static RUN_COUNTER: AtomicU64 = AtomicU64::new(1);

pub fn next_run_id() -> String {
    format!("run-{}", RUN_COUNTER.fetch_add(1, Ordering::Relaxed))
}

pub struct RuntimeManager;

impl RuntimeManager {
    pub fn list_definitions() -> &'static [RuntimeDefinition] {
        RUNTIME_REGISTRY
    }

    pub fn find(runtime_id: &str) -> Option<&'static RuntimeDefinition> {
        find_runtime(runtime_id)
    }

    pub fn resolve(runtime_id: &str) -> Option<ResolvedExecutable> {
        find_runtime(runtime_id).and_then(resolve_executable)
    }

    pub fn is_available(runtime_id: &str) -> bool {
        find_runtime(runtime_id)
            .map(is_runtime_available)
            .unwrap_or(false)
    }

    pub async fn detect(runtime_id: &str) -> Result<RuntimeDetection, String> {
        let definition =
            find_runtime(runtime_id).ok_or_else(|| format!("未知 Runtime：{runtime_id}"))?;
        Ok(detect_runtime(definition).await)
    }

    pub fn build_invocation(
        runtime_id: &str,
        prompt: String,
        cwd: std::path::PathBuf,
        env: HashMap<String, String>,
        model: Option<String>,
    ) -> Result<RuntimeInvocation, String> {
        let definition =
            find_runtime(runtime_id).ok_or_else(|| format!("未知 Runtime：{runtime_id}"))?;
        let context = invocation_context(definition, prompt, cwd, model);
        build_invocation(definition, context, env)
    }

    pub async fn launch_with_app(
        app: &AppHandle,
        invocation: RuntimeInvocation,
        definition: &RuntimeDefinition,
        run_id: String,
    ) -> Result<i32, String> {
        let emit = |event: AgentEvent| {
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

        let child = spawn_process(&invocation).await?;
        let shared = register(&run_id, child);

        let stdout = {
            let mut guard = shared.lock().await;
            guard
                .as_mut()
                .and_then(|child| child.stdout.take())
                .ok_or_else(|| "无法获取 stdout".to_string())?
        };

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

        if exit_code != 0 {
            emit(AgentEvent::Error {
                message: format!("CLI 退出码 {exit_code}"),
            });
        }

        emit(AgentEvent::RunCompleted { exit_code });
        Ok(exit_code)
    }

    pub async fn cancel_run(run_id: &str) -> Result<(), String> {
        runs::cancel(run_id).await
    }
}
