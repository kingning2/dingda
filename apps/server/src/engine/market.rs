//! Server-side market analysis entry point (demand/competition scoring).

use crate::error::AppResult;

pub struct MarketEngine;

impl MarketEngine {
    pub fn new() -> Self {
        Self
    }

    pub async fn analyze_for_workspace(
        &self,
        _workspace_id: u64,
        _product_id: u64,
    ) -> AppResult<()> {
        Ok(())
    }
}
