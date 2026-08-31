use serde::Serialize;

/// 启动时探测到的机器/容器资源，用于推导默认运行参数。
#[derive(Clone, Copy, Debug, Serialize)]
pub struct ResourceProfile {
    pub cpus: usize,
    pub memory_bytes: u64,
}

impl ResourceProfile {
    pub fn detect() -> Self {
        let cpus = std::thread::available_parallelism()
            .map(|value| value.get())
            .unwrap_or(2)
            .max(1);

        let memory_bytes = detect_memory_bytes().max(256 * 1024 * 1024);

        Self { cpus, memory_bytes }
    }

    pub fn memory_mb(&self) -> u64 {
        self.memory_bytes / (1024 * 1024)
    }

    pub fn tokio_workers(&self) -> usize {
        self.cpus.clamp(1, 8)
    }

    pub fn db_pool_max_connections(&self) -> u32 {
        let mem_mb = self.memory_mb();
        (mem_mb / 256).clamp(4, 32) as u32
    }

    pub fn db_pool_min_connections(&self) -> u32 {
        if self.memory_mb() < 4096 {
            1
        } else {
            2
        }
    }

    pub fn bulk_batch_size(&self) -> usize {
        (self.memory_mb() / 40).clamp(20, 200) as usize
    }

    pub fn bulk_max_items(&self) -> usize {
        (self.memory_mb() / 4).clamp(100, 5000) as usize
    }

    pub fn http_max_body_mb(&self) -> usize {
        (self.memory_mb() / 1024).clamp(1, 8) as usize
    }
}

fn detect_memory_bytes() -> u64 {
    #[cfg(target_os = "linux")]
    if let Some(bytes) = linux_cgroup_memory_limit() {
        return bytes;
    }

    let mut system = sysinfo::System::new();
    system.refresh_memory();
    system.total_memory()
}

#[cfg(target_os = "linux")]
fn linux_cgroup_memory_limit() -> Option<u64> {
    use std::fs;

    if let Ok(raw) = fs::read_to_string("/sys/fs/cgroup/memory.max") {
        if let Some(bytes) = parse_cgroup_bytes(raw.trim()) {
            return Some(bytes);
        }
    }

    if let Ok(raw) = fs::read_to_string("/sys/fs/cgroup/memory/memory.limit_in_bytes") {
        return parse_cgroup_bytes(raw.trim());
    }

    None
}

#[cfg(target_os = "linux")]
fn parse_cgroup_bytes(raw: &str) -> Option<u64> {
    if raw.eq_ignore_ascii_case("max") {
        return None;
    }
    raw.parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn profile_scales_for_two_gb() {
        let profile = ResourceProfile {
            cpus: 2,
            memory_bytes: 2 * 1024 * 1024 * 1024,
        };

        assert_eq!(profile.tokio_workers(), 2);
        assert_eq!(profile.db_pool_max_connections(), 8);
        assert_eq!(profile.bulk_batch_size(), 51);
        assert_eq!(profile.http_max_body_mb(), 2);
    }
}
