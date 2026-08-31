use sqlx::MySqlPool;

use crate::{
    error::{AppError, AppResult},
    models::dto::{
        SnapshotBatchRequest, SnapshotBatchResponse, SnapshotIngestResult, SnapshotIngestStatus,
    },
    repo::{crawl_tasks, snapshots, workspaces},
};

pub async fn ingest_batch(
    pool: &MySqlPool,
    user_id: u64,
    request: SnapshotBatchRequest,
) -> AppResult<SnapshotBatchResponse> {
    if request.snapshots.is_empty() {
        return Err(AppError::BadRequest("snapshots cannot be empty".into()));
    }

    let workspace_id = match request.workspace_id {
        Some(id) => id,
        None => workspaces::default_workspace_id(pool, user_id).await?,
    };
    workspaces::ensure_member(pool, workspace_id, user_id).await?;

    let platform = request
        .snapshots
        .first()
        .map(|snapshot| snapshot.platform.as_str())
        .unwrap_or("unknown");

    let crawl_task =
        crawl_tasks::resolve_for_batch(pool, workspace_id, &request.crawl_id, platform).await?;

    let mut accepted = 0usize;
    let mut duplicated = 0usize;
    let mut failed = 0usize;
    let mut results = Vec::with_capacity(request.snapshots.len());

    for snapshot in request.snapshots {
        let snapshot_id = snapshot.snapshot_id.clone();
        match snapshots::ingest_one(pool, crawl_task.id, &snapshot).await {
            Ok(snapshots::IngestOutcome::Created {
                product_snapshot_id,
                product_platform_id,
            }) => {
                accepted += 1;
                results.push(SnapshotIngestResult {
                    snapshot_id,
                    status: SnapshotIngestStatus::Created,
                    product_snapshot_id: Some(product_snapshot_id),
                    product_platform_id: Some(product_platform_id),
                    error: None,
                });
            }
            Ok(snapshots::IngestOutcome::Duplicate {
                product_snapshot_id,
                product_platform_id,
            }) => {
                duplicated += 1;
                results.push(SnapshotIngestResult {
                    snapshot_id,
                    status: SnapshotIngestStatus::Duplicate,
                    product_snapshot_id: Some(product_snapshot_id),
                    product_platform_id: Some(product_platform_id),
                    error: None,
                });
            }
            Err(error) => {
                failed += 1;
                results.push(SnapshotIngestResult {
                    snapshot_id,
                    status: SnapshotIngestStatus::Failed,
                    product_snapshot_id: None,
                    product_platform_id: None,
                    error: Some(error.to_string()),
                });
            }
        }
    }

    if accepted > 0 {
        crawl_tasks::bump_success(pool, crawl_task.id, accepted as u32).await?;
    }
    if failed > 0 {
        crawl_tasks::bump_failed(pool, crawl_task.id, failed as u32).await?;
    }

    Ok(SnapshotBatchResponse {
        accepted,
        duplicated,
        failed,
        results,
    })
}
