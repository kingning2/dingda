/**
 * 验证前端“编辑历史消息并从该处重发”的真实 reducer 行为。
 *
 * 职责：
 *   用 Vite SSR 加载 src/lib/agent-event-reducer.ts，不复制实现。
 *
 * 使用示例：
 *   node scripts/agent-rollback-check.mjs
 */

import assert from "node:assert/strict";
import { createServer } from "vite";

const vite = await createServer({
  appType: "custom",
  logLevel: "silent",
  server: { middlewareMode: true },
});

try {
  const reducer = await vite.ssrLoadModule("/src/lib/agent-event-reducer.ts");
  const detail = {
    work_id: "rollback-check",
    title: "rollback",
    status: {},
    messages: [
      { id: "u1", role: "user", content: "第一问", created_at: "2026-01-01T00:00:00Z" },
      { id: "a1", role: "assistant", content: "第一答", created_at: "2026-01-01T00:00:01Z" },
      { id: "u2", role: "user", content: "第二问", created_at: "2026-01-01T00:00:02Z" },
      { id: "a2", role: "assistant", content: "第二答", created_at: "2026-01-01T00:00:03Z" },
      { id: "u3", role: "user", content: "第三问", created_at: "2026-01-01T00:00:04Z" },
      { id: "a3", role: "assistant", content: "第三答", created_at: "2026-01-01T00:00:05Z" },
    ],
    products: { items: [], total: 0, status: {} },
    recommendations: { items: [], total: 0, status: {} },
    comparison: { kind: "price_compare" },
    browser_live: {},
    browser_history: [],
    can_send: true,
    composer_agent_id: "codex",
    composer_model_id: "gpt-5.5",
    composer_agents: [],
    cli_session_id: "cli-session-1",
    cli_session_runtime_id: "codex",
  };

  const truncated = reducer.truncateBeforeUserMessage(detail, "u2");
  assert.ok(truncated, "must find the target user message");
  assert.deepEqual(
    truncated.messages.map((message) => message.id),
    ["u1", "a1"],
    "must remove the edited message and every later message",
  );
  assert.equal(truncated.cli_session_id, null, "must clear stale CLI session");
  assert.equal(truncated.cli_session_runtime_id, null, "must clear stale runtime id");
  assert.equal(truncated.comparison, null, "must clear result snapshot");
  assert.equal(truncated.can_send, true, "must allow resending");

  const resent = reducer.createOptimisticSendDetail(truncated, "第二问已修改", "codex", "gpt-5.5");
  assert.deepEqual(
    resent.detail.messages.map((message) => [message.role, message.id]),
    [
      ["user", "u1"],
      ["assistant", "a1"],
      ["user", resent.detail.messages[2].id],
      ["assistant", resent.assistantMessageId],
    ],
    "must append the edited turn after retained history",
  );
  assert.equal(resent.detail.cli_session_id, null, "resent turn must start a fresh session");

  const sameRuntime = reducer.createOptimisticSendDetail(detail, "继续", "codex", "gpt-5.5");
  assert.equal(
    sameRuntime.detail.cli_session_id,
    "cli-session-1",
    "same runtime must keep its CLI session before an edit",
  );

  const switchedRuntime = reducer.createOptimisticSendDetail(detail, "切换", "opencode", "hy3");
  assert.equal(
    switchedRuntime.detail.cli_session_id,
    null,
    "switching runtime must not resume the old CLI session",
  );

  console.log(
    JSON.stringify({
      ok: true,
      retained: truncated.messages.map((message) => message.id),
      resent_messages: resent.detail.messages.length,
      session_cleared: resent.detail.cli_session_id === null,
      runtime_switch_clears_session: switchedRuntime.detail.cli_session_id === null,
    }),
  );
} catch (error) {
  console.log(
    JSON.stringify({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    }),
  );
  process.exitCode = 1;
} finally {
  await vite.close();
}
