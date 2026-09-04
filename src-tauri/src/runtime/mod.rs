pub mod defs;
pub mod detection;
pub mod event;
pub mod invocation;
pub mod manager;
pub mod mcp;
pub mod model_discover;
pub mod parsers;
pub mod process;
pub mod prompts;
pub mod registry;
pub mod resolution;
pub mod runs;
pub mod types;

pub use registry::{find_runtime, RUNTIME_REGISTRY};
pub use resolution::resolve_executable;
pub use types::{ExecutableSource, RuntimeDefinition};
