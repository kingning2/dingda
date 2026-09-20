/**
 * 模型凭据编辑回填 E2E。
 *
 * 职责：
 *   预置一条真实落库的凭据，打开编辑弹窗，验证安全回填边界：模型带回来，
 *   API Key 原文绝不带回来，只显示掩码。
 *
 * 设计说明：
 *   - 模型列表接口由浏览器层 mock，避免测试 key 真的去请求上游
 *   - 凭据本体走真实 HTTP，覆盖“保存后后端掩码 → 前端编辑态”的完整边界
 *   - 用后删除测试凭据，减少对本地开发库的影响
 */

import { expect, test } from "@playwright/test";

const MODEL = "deepseek-e2e-edit";
const API_KEY = "sk-e2e-abcdef123456";
const MASKED_KEY = "sk-e2e****3456";
const LABEL = `E2E 编辑回填 ${Date.now()}`;
let credentialId: string | undefined;

test.afterEach(async ({ request }) => {
  if (credentialId) {
    await request.delete(`http://127.0.0.1:8787/v1/llm/credentials/${credentialId}`);
    credentialId = undefined;
  }
});

test("编辑凭据：模型回填，API Key 只回填掩码", async ({ page, request }) => {
  const created = await request.post("http://127.0.0.1:8787/v1/llm/credentials", {
    data: {
      provider: "deepseek",
      api_key: API_KEY,
      model: MODEL,
      label: LABEL,
      activate: false,
    },
  });
  expect(created.ok()).toBe(true);
  credentialId = ((await created.json()) as { item: { credential_id: string } }).item.credential_id;

  await page.route(/\/v1\/llm\/credentials\/[^/]+\/models$/, async (route) => {
    await route.fulfill({
      json: {
        ok: true,
        provider: "deepseek",
        models: ["deepseek-flash", MODEL],
        default_model: "deepseek-flash",
        current_model: MODEL,
        message: null,
      },
    });
  });

  await page.goto("/#/model-config");
  await expect(page.locator("#boot-splash")).toHaveCount(0);
  const card = page.locator(`[data-testid="model-credential-card-${credentialId}"]`);
  await expect(card).toContainText(LABEL);
  await card.getByRole("button", { name: "编辑" }).click();

  const apiKey = page.locator("#credential-api-key");
  await expect(apiKey).toHaveValue("");
  await expect(page.getByText(`当前 Key：${MASKED_KEY}`)).toBeVisible();
  await expect(page.getByLabel("备注名")).toHaveValue(LABEL);

  const modelPicker = page.locator("button[aria-pressed='true']").filter({ hasText: MODEL });
  await expect(modelPicker).toHaveCount(1);
  await expect(modelPicker).toContainText("已选");

  await page.getByRole("button", { name: "手动填写" }).click();
  await expect(page.locator("#credential-model")).toHaveValue(MODEL);
});
