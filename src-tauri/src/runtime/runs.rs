use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use tokio::process::Child;

type SharedChild = std::sync::Arc<tokio::sync::Mutex<Option<Child>>>;

static RUNS: OnceLock<Mutex<HashMap<String, SharedChild>>> = OnceLock::new();

fn runs() -> &'static Mutex<HashMap<String, SharedChild>> {
    RUNS.get_or_init(|| Mutex::new(HashMap::new()))
}

pub fn register(run_id: &str, child: Child) -> SharedChild {
    let shared = std::sync::Arc::new(tokio::sync::Mutex::new(Some(child)));
    runs()
        .lock()
        .expect("run registry lock")
        .insert(run_id.to_string(), std::sync::Arc::clone(&shared));
    shared
}

pub async fn cancel(run_id: &str) -> Result<(), String> {
    let shared = runs()
        .lock()
        .expect("run registry lock")
        .remove(run_id);
    if let Some(shared) = shared {
        if let Some(mut child) = shared.lock().await.take() {
            child
                .kill()
                .await
                .map_err(|error| format!("终止进程失败：{error}"))?;
        }
    }
    Ok(())
}

pub fn unregister(run_id: &str) {
    runs().lock().expect("run registry lock").remove(run_id);
}
