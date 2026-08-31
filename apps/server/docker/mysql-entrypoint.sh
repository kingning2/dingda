#!/bin/bash
set -euo pipefail

detect_memory_mb() {
  local raw=""
  if [[ -f /sys/fs/cgroup/memory.max ]]; then
    raw="$(tr -d '[:space:]' < /sys/fs/cgroup/memory.max)"
    if [[ -n "$raw" && "$raw" != "max" ]]; then
      echo $((raw / 1024 / 1024))
      return
    fi
  fi
  if [[ -f /sys/fs/cgroup/memory/memory.limit_in_bytes ]]; then
    raw="$(tr -d '[:space:]' < /sys/fs/cgroup/memory/memory.limit_in_bytes)"
    if [[ -n "$raw" && "$raw" != "9223372036854771712" ]]; then
      echo $((raw / 1024 / 1024))
      return
    fi
  fi
  awk '/MemTotal:/ {print int($2 / 1024)}' /proc/meminfo
}

detect_cpu_count() {
  if command -v nproc >/dev/null 2>&1; then
    nproc
    return
  fi
  getconf _NPROCESSORS_ONLN
}

MEM_MB="$(detect_memory_mb)"
CPU_COUNT="$(detect_cpu_count)"

BUFFER_POOL_MB=$((MEM_MB * 35 / 100))
if (( BUFFER_POOL_MB < 64 )); then BUFFER_POOL_MB=64; fi
if (( BUFFER_POOL_MB > 512 )); then BUFFER_POOL_MB=512; fi

MAX_CONNECTIONS=$((MEM_MB / 64))
if (( MAX_CONNECTIONS < 20 )); then MAX_CONNECTIONS=20; fi
if (( MAX_CONNECTIONS > 100 )); then MAX_CONNECTIONS=100; fi

THREAD_CACHE=$((CPU_COUNT * 2))
if (( THREAD_CACHE < 4 )); then THREAD_CACHE=4; fi

export MYSQLD_EXTRA_FLAGS="\
--character-set-server=utf8mb4 \
--collation-server=utf8mb4_unicode_ci \
--performance-schema=OFF \
--max_connections=${MAX_CONNECTIONS} \
--innodb_buffer_pool_size=${BUFFER_POOL_MB}M \
--innodb_log_buffer_size=8M \
--innodb_redo_log_capacity=32M \
--table_open_cache=128 \
--thread_cache_size=${THREAD_CACHE} \
--tmp_table_size=16M \
--max_heap_table_size=16M"

echo "mysql autotune: cpus=${CPU_COUNT}, memory_mb=${MEM_MB}, buffer_pool=${BUFFER_POOL_MB}M, max_connections=${MAX_CONNECTIONS}"

exec docker-entrypoint.sh mysqld ${MYSQLD_EXTRA_FLAGS}
