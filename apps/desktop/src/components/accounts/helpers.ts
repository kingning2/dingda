/**
 * 账号模块共享助手 — 本地存储解析 / 串行写入。
 */

/** 解析本地存储的账号 id JSON 数组（脏数据安全）。 */
export function parseAccountIds(raw: string | null): string[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is string => typeof item === "string" && item.length > 0);
  } catch {
    return [];
  }
}

let writeChain: Promise<void> = Promise.resolve();

/** 串行化异步写入（避免并发覆盖本地存储）。 */
export function enqueueWrite<T>(task: () => Promise<T>): Promise<T> {
  const result = writeChain.then(task, task);
  writeChain = result.then(
    () => undefined,
    () => undefined,
  );
  return result;
}
