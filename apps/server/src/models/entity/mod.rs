//! 数据库实体（FromRow），供 Repository 层使用。

mod analysis;
mod product;
mod task;
mod tenant;

pub use analysis::*;
pub use product::*;
pub use task::*;
pub use tenant::*;
