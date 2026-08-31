//! Server-side profit calculation entry point.
//! Client must never submit profit/opportunity scores.

use crate::error::AppResult;

pub struct ProfitEngine;

impl ProfitEngine {
    pub fn new() -> Self {
        Self
    }

    pub async fn calculate_for_workspace(
        &self,
        _workspace_id: u64,
        _product_id: u64,
    ) -> AppResult<()> {
        // Reserved for server-side profit analysis pipeline.
        Ok(())
    }
}
