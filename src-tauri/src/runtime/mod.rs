pub mod defs;
pub mod detection;
pub mod model_discover;
pub mod registry;
pub mod resolution;
pub mod types;

pub use registry::{find_runtime, RUNTIME_REGISTRY};
pub use resolution::resolve_executable;
pub use types::{ExecutableSource, RuntimeDefinition};
